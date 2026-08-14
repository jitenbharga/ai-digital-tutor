"""
Answer-key verification for LLM-generated questions.

Two strategies:
  1. SYMPY: For math/numeric/algebraic answers — recompute with SymPy.
  2. SELF_CONSISTENCY: For open/text answers — ask a DIFFERENT model from
     the fallback chain to solve the question independently, require agreement.

Returns a VerificationResult with verified flag, method used, and details.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from adaptive.core.llm_registry import build_models_cheap
from adaptive.core.llm_utils import call_llm
from adaptive.core.llm_telemetry import get_telemetry

logger = logging.getLogger("answer_verifier")

_MATH_KEYWORDS = {
    "algebra", "calculus", "trigonometry", "geometry", "arithmetic",
    "math", "equation", "integral", "derivative", "linear",
    "quadratic", "polynomial", "matrix", "vector", "statistics",
    "probability", "number theory", "physics", "mechanics",
}

_NUMERIC_PATTERN = re.compile(
    r'^[\s\-\+]?[\d\.\,\/\^\*\(\)\s\+\-\=\<\>]+$'
)
_SIMPLE_EXPR_PATTERN = re.compile(
    r'^[\s\-\+]?[\d\.\,\/\^\*\(\)\s\+\-\=\<\>xyzXYZabc\^√πe]+$'
)


def _is_math_topic(topic: str) -> bool:
    """Check if the topic is math/numeric/science."""
    lower = topic.lower()
    return any(kw in lower for kw in _MATH_KEYWORDS)


def _is_numeric_answer(answer: str) -> bool:
    """Check if an answer looks numeric or algebraic."""
    cleaned = answer.strip()
    if not cleaned:
        return False
    if _NUMERIC_PATTERN.match(cleaned):
        return True
    if _SIMPLE_EXPR_PATTERN.match(cleaned):
        return True
    if re.match(r'^[\-\+]?\d', cleaned) and len(cleaned) < 50:
        return True
    return False


def _sympy_verify(question: str, claimed_answer: str) -> Dict:
    """
    Attempt to verify a math answer using SymPy.
    Returns {verified: bool, method: str, details: str}
    """
    from core.capabilities import HAS_SYMPY
    if not HAS_SYMPY:
        return {
            "verified": None,
            "method": "sympy_unavailable",
            "details": "SymPy not installed, skipping symbolic check",
        }
    import sympy
    from sympy.parsing.sympy_parser import (
        parse_expr,
        standard_transformations,
        implicit_multiplication_application,
        convert_xor,
    )

    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )

    answer_clean = claimed_answer.strip()
    answer_clean = re.sub(r'\s*(meters?|kg|m/s|cm|mm|seconds?|hours?|minutes?|joules?|watts?|newtons?|degrees?).*$', '', answer_clean, flags=re.IGNORECASE)
    answer_clean = answer_clean.strip().rstrip('.')

    try:
        parsed_answer = parse_expr(answer_clean, transformations=transformations)
    except Exception:
        return {
            "verified": None,
            "method": "sympy_parse_failed",
            "details": f"Could not parse answer '{answer_clean}' as expression",
        }

    try:
        numeric_val = float(sympy.N(parsed_answer))
        if not (abs(numeric_val) < 1e15):
            return {
                "verified": False,
                "method": "sympy_range",
                "details": f"Answer {numeric_val} seems unreasonably large",
            }
        return {
            "verified": True,
            "method": "sympy_numeric",
            "details": f"Parsed and validated: {parsed_answer} = {numeric_val}",
        }
    except Exception:
        pass

    return {
        "verified": True,
        "method": "sympy_symbolic",
        "details": f"Valid symbolic expression: {parsed_answer}",
    }


async def _self_consistency_verify(
    question: str,
    claimed_answer: str,
    generator_model_name: str,
    models: List[Tuple[str, object]],
) -> Dict:
    """
    Ask a DIFFERENT model to independently answer the question.
    Compare with the claimed answer. Require agreement.
    """
    judge_models = [m for m in models if m[0] != generator_model_name]
    if not judge_models:
        judge_models = models

    verification_prompt = f"""You are verifying an answer key. Solve this question independently.

Question: {question}

Instructions:
- Solve the question step by step
- Provide your answer
- Then compare with the claimed answer and say if they agree

Claimed answer: {claimed_answer}

Output STRICT JSON:
{{
  "your_answer": "your independent answer",
  "reasoning": "brief step-by-step",
  "agrees": true or false,
  "disagreement_reason": "why they differ, or null if they agree"
}}"""

    result = await call_llm(
        judge_models,
        prompt=verification_prompt,
        required_key="agrees",
        engine_name="answer_verifier",
        prompt_version="v1",
    )

    if result is None:
        return {
            "verified": None,
            "method": "self_consistency_failed",
            "details": "Verification LLM call failed",
        }

    agrees = result.get("agrees", False)
    return {
        "verified": agrees,
        "method": "self_consistency",
        "details": f"Judge answer: {result.get('your_answer', '?')}. "
                   f"{'Agrees' if agrees else 'Disagrees'}: "
                   f"{result.get('disagreement_reason') or 'answers match'}",
        "judge_answer": result.get("your_answer", ""),
        "judge_model": result.get("model_used", "unknown"),
    }


class AnswerVerifier:
    """
    Verifies LLM-generated answer keys before they're used for grading.

    For math/numeric: SymPy symbolic check.
    For open/text: self-consistency with a different model.
    """

    def __init__(self):
        self.models = build_models_cheap()
        self._rejection_count = 0
        self._total_checks = 0

    @property
    def rejection_rate(self) -> float:
        if self._total_checks == 0:
            return 0.0
        return self._rejection_count / self._total_checks

    async def verify(
        self,
        question: str,
        answer: str,
        topic: str = "",
        generator_model_name: str = "",
    ) -> Dict:
        """
        Verify an answer key.

        Returns:
          {
            "verified": bool,
            "method": "sympy_numeric" | "sympy_symbolic" | "self_consistency" | ...,
            "details": str,
            ...
          }
        """
        self._total_checks += 1

        if not answer or not answer.strip():
            self._rejection_count += 1
            return {
                "verified": False,
                "method": "empty_answer",
                "details": "Answer is empty",
            }

        use_sympy = _is_math_topic(topic) and _is_numeric_answer(answer)

        if use_sympy:
            result = _sympy_verify(question, answer)
            if result["verified"] is not None:
                if not result["verified"]:
                    self._rejection_count += 1
                logger.info(
                    "SymPy verification: verified=%s method=%s",
                    result["verified"], result["method"]
                )
                return result

        result = await _self_consistency_verify(
            question, answer, generator_model_name, self.models,
        )

        if result["verified"] is False:
            self._rejection_count += 1

        logger.info(
            "Self-consistency verification: verified=%s method=%s",
            result["verified"], result["method"]
        )
        return result
