"""
Hardened answer evaluator (G3).

Grading hierarchy:
  1. Deterministic: For math/numeric/code — SymPy equivalence check, no LLM.
  2. Reference-guided LLM: For open answers — grade against verified reference answer.
  3. Adaptive self-consistency (R7): Take 1 sample first. If high-confidence
     correct/incorrect, return immediately. Otherwise escalate to max_samples
     (default 3) with majority vote.
  4. Judge != generator: Use a different provider from the one that generated the question.

Output: coarse rubric (correct / partially_correct / incorrect) + confidence.
Preserves diagnostic fields (error_type, misconception, remediation).
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from core.llm_registry import build_models_cheap, get_llm_config
from core.llm_utils import call_llm
from core.prompts import answer_evaluator as prompt_tmpl

logger = logging.getLogger("answer_evaluator")

_eval_total = 0
_eval_escalated = 0

_NUMERIC_PATTERN = re.compile(r'^[\s\-\+]?[\d\.\,\/\s]+$')


def _extract_number(text: str) -> Optional[float]:
    """Try to extract a single numeric value from text."""
    if not text:
        return None
    cleaned = text.strip().replace(',', '')
    cleaned = re.sub(r'\s*(meters?|kg|m/s|cm|mm|seconds?|hours?|minutes?|joules?|watts?|newtons?|degrees?|%|units?).*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().rstrip('.')
    try:
        return float(cleaned)
    except ValueError:
        pass
    frac_match = re.match(r'^([\-\+]?\d+)\s*/\s*(\d+)$', cleaned)
    if frac_match:
        num, den = float(frac_match.group(1)), float(frac_match.group(2))
        if den != 0:
            return num / den
    return None


def _sympy_equivalent(expr_a: str, expr_b: str) -> Optional[bool]:
    """Check if two expressions are symbolically equivalent using SymPy."""
    from core.capabilities import HAS_SYMPY
    if not HAS_SYMPY:
        return None
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application, convert_xor,
        )
        transformations = standard_transformations + (
            implicit_multiplication_application, convert_xor,
        )
        a = parse_expr(expr_a.strip(), transformations=transformations)
        b = parse_expr(expr_b.strip(), transformations=transformations)
        diff = sympy.simplify(a - b)
        return diff == 0
    except Exception:
        return None


def _deterministic_grade(
    student_answer: str,
    correct_answer: str,
) -> Optional[Dict]:
    """
    Grade math/numeric answers deterministically (no LLM).
    Returns None if answers aren't numeric/grading isn't possible.
    """
    if not student_answer or not correct_answer:
        return None

    student_num = _extract_number(student_answer)
    correct_num = _extract_number(correct_answer)

    if student_num is not None and correct_num is not None:
        if correct_num == 0:
            is_match = abs(student_num) < 1e-6
        else:
            rel_error = abs(student_num - correct_num) / max(abs(correct_num), 1e-10)
            is_match = rel_error < 0.01

        if is_match:
            return {
                "grade": "correct",
                "score": 1.0,
                "correct": True,
                "confidence": 1.0,
                "method": "deterministic_numeric",
                "reasoning": f"Numeric match: student={student_num}, expected={correct_num}",
                "error_type": "none",
                "misconception": None,
                "root_concept": None,
                "targeted_feedback": "Correct!",
                "remediation": "",
                "mistakes": [],
                "improvement": "",
            }
        else:
            return {
                "grade": "incorrect",
                "score": 0.0,
                "correct": False,
                "confidence": 1.0,
                "method": "deterministic_numeric",
                "reasoning": f"Numeric mismatch: student={student_num}, expected={correct_num}",
                "error_type": "procedural",
                "misconception": None,
                "root_concept": None,
                "targeted_feedback": f"Your answer {student_num} doesn't match the expected {correct_num}.",
                "remediation": "Review your calculation steps.",
                "mistakes": [f"Got {student_num} instead of {correct_num}"],
                "improvement": "Double-check your arithmetic.",
            }

    sympy_result = _sympy_equivalent(student_answer, correct_answer)
    if sympy_result is not None:
        if sympy_result:
            return {
                "grade": "correct",
                "score": 1.0,
                "correct": True,
                "confidence": 1.0,
                "method": "deterministic_sympy",
                "reasoning": "Symbolically equivalent expressions",
                "error_type": "none",
                "misconception": None,
                "root_concept": None,
                "targeted_feedback": "Correct!",
                "remediation": "",
                "mistakes": [],
                "improvement": "",
            }
        else:
            return {
                "grade": "incorrect",
                "score": 0.0,
                "correct": False,
                "confidence": 1.0,
                "method": "deterministic_sympy",
                "reasoning": "Expressions are not symbolically equivalent",
                "error_type": "procedural",
                "misconception": None,
                "root_concept": None,
                "targeted_feedback": "Your expression doesn't simplify to the expected answer.",
                "remediation": "Re-derive the expression step by step.",
                "mistakes": [],
                "improvement": "Verify each algebraic step.",
            }

    return None


async def _llm_judge_once(
    models: List[Tuple[str, object]],
    prompt: str,
    generator_model_name: str = "",
) -> Optional[Dict]:
    """Single LLM judgment call, preferring a different model than the generator."""
    if generator_model_name:
        judge_first = [m for m in models if m[0] != generator_model_name]
        judge_rest = [m for m in models if m[0] == generator_model_name]
        judge_models = judge_first + judge_rest
    else:
        judge_models = models

    return await call_llm(
        judge_models, prompt, required_key="grade",
        engine_name="answer_evaluator",
        prompt_version=prompt_tmpl.VERSION,
    )


def _majority_vote(results: List[Dict]) -> Dict:
    """
    Take majority vote from multiple judgment samples.
    Returns the winning result with agreement-based confidence.
    """
    if not results:
        return {}

    grade_counts = {}
    for r in results:
        g = r.get("grade", "incorrect")
        grade_counts[g] = grade_counts.get(g, 0) + 1

    majority_grade = max(grade_counts, key=grade_counts.get)
    agreement = grade_counts[majority_grade] / len(results)

    winner = next(r for r in results if r.get("grade") == majority_grade)
    winner["confidence"] = round(agreement, 2)
    winner["method"] = f"self_consistency_{len(results)}x"
    winner["agreement"] = f"{grade_counts[majority_grade]}/{len(results)}"

    return winner


class LLMAnswerEvaluator:

    def __init__(self):
        self.models = build_models_cheap()

    async def evaluate(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        start_time: float,
        end_time: float,
        topic: str = "",
        knowledge: float = 0.5,
        difficulty: str = "medium",
        student_profile: Dict = None,
        generator_model: str = "",
    ) -> Dict:

        response_time = end_time - start_time

        det_result = _deterministic_grade(student_answer, correct_answer)
        if det_result is not None:
            logger.info("Deterministic grade: %s (method=%s)", det_result["grade"], det_result["method"])
            ux_score = self._calculate_ux_score(
                score=det_result["score"],
                response_time=response_time,
                difficulty=difficulty,
                student_profile=student_profile or {},
            )
            det_result["ux_score"] = ux_score
            det_result["response_time"] = response_time
            det_result["model_used"] = "deterministic"
            return det_result

        llm_result = await self._llm_evaluate_robust(
            question, student_answer, correct_answer,
            topic=topic, knowledge=knowledge,
            generator_model=generator_model,
        )

        grade = llm_result.get("grade", "incorrect")
        if grade == "correct":
            score = 1.0
            correct = True
        elif grade == "partially_correct":
            score = 0.5
            correct = False
        else:
            score = 0.0
            correct = False

        ux_score = self._calculate_ux_score(
            score=score,
            response_time=response_time,
            difficulty=difficulty,
            student_profile=student_profile or {},
        )

        return {
            "correct": correct,
            "score": score,
            "grade": grade,
            "ux_score": ux_score,
            "response_time": response_time,
            "confidence": llm_result.get("confidence", 0.0),
            "method": llm_result.get("method", "unknown"),
            "agreement": llm_result.get("agreement", ""),
            "reasoning": llm_result.get("reasoning"),
            "error_type": llm_result.get("error_type", "none"),
            "misconception": llm_result.get("misconception"),
            "root_concept": llm_result.get("root_concept"),
            "targeted_feedback": llm_result.get("targeted_feedback", ""),
            "remediation": llm_result.get("remediation", ""),
            "mistakes": llm_result.get("mistakes", []),
            "improvement": llm_result.get("improvement", ""),
            "model_used": llm_result.get("model_used", "unknown"),
        }

    @staticmethod
    def _get_evaluator_config() -> dict:
        """Return evaluator config from llm config, with defaults."""
        cfg = get_llm_config()
        ev = cfg.get("evaluator", {})
        return {
            "confidence_threshold": ev.get("confidence_threshold", 0.75),
            "max_samples": ev.get("max_samples", 3),
        }

    async def _llm_evaluate_robust(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
        topic: str = "",
        knowledge: float = 0.5,
        generator_model: str = "",
    ) -> Dict:
        """
        Adaptive self-consistency grading (R7).

        1. Take one LLM judgment.
        2. If the grade is "correct" or "incorrect" AND confidence >= threshold,
           return immediately (fast path — 1 sample).
        3. Otherwise escalate: sample (max_samples - 1) more, then majority-vote.

        Escalation rate is logged at INFO level.
        """
        global _eval_total, _eval_escalated

        ev_cfg = self._get_evaluator_config()
        confidence_threshold = ev_cfg["confidence_threshold"]
        max_samples = ev_cfg["max_samples"]

        prompt = prompt_tmpl.build(question, student_answer, correct_answer, topic, knowledge)

        first = await _llm_judge_once(
            self.models, prompt,
            generator_model_name=generator_model,
        )

        _eval_total += 1

        if first is None:
            logger.warning("First evaluation sample failed; escalating to %d samples", max_samples - 1)
            _eval_escalated += 1
            return await self._escalate(prompt, generator_model, [], max_samples - 1)

        grade = first.get("grade", "")
        confidence = float(first.get("confidence", 0.0))

        if grade in ("correct", "incorrect") and confidence >= confidence_threshold:
            first["method"] = "adaptive_single"
            logger.debug(
                "Adaptive fast path: grade=%s confidence=%.2f (threshold=%.2f)",
                grade, confidence, confidence_threshold,
            )
            self._log_escalation_rate()
            return first

        _eval_escalated += 1
        logger.info(
            "Escalating to %dx sampling: grade=%s confidence=%.2f (threshold=%.2f) "
            "[escalation rate: %d/%d = %.1f%%]",
            max_samples, grade, confidence, confidence_threshold,
            _eval_escalated, _eval_total,
            (_eval_escalated / _eval_total * 100) if _eval_total else 0,
        )
        return await self._escalate(prompt, generator_model, [first], max_samples - 1)

    async def _escalate(
        self,
        prompt: str,
        generator_model: str,
        existing_results: List[Dict],
        extra_samples: int,
    ) -> Dict:
        """Sample `extra_samples` more judgments, majority-vote with existing results."""
        results = list(existing_results)

        for _ in range(extra_samples):
            result = await _llm_judge_once(
                self.models, prompt,
                generator_model_name=generator_model,
            )
            if result:
                results.append(result)

        if not results:
            return {
                "grade": "incorrect",
                "score": 0.0,
                "correct": False,
                "confidence": 0.0,
                "method": "llm_failed",
                "error_type": "none",
                "misconception": None,
                "root_concept": None,
                "reasoning": "All evaluation attempts failed",
                "targeted_feedback": "",
                "remediation": "",
                "mistakes": [],
                "improvement": "",
                "model_used": "fallback",
            }

        if len(results) == 1:
            r = results[0]
            r["method"] = "adaptive_single_fallback"
            return r

        return _majority_vote(results)

    def _log_escalation_rate(self):
        """Periodically log escalation stats (every 50 evaluations)."""
        if _eval_total > 0 and _eval_total % 50 == 0:
            rate = (_eval_escalated / _eval_total * 100)
            logger.info(
                "Adaptive grading stats: %d/%d escalated (%.1f%%)",
                _eval_escalated, _eval_total, rate,
            )

    def _calculate_ux_score(
        self,
        score: float,
        response_time: float,
        difficulty: str = "medium",
        student_profile: Dict = None,
    ) -> float:
        """UX display score (0-3). NOT the RL reward — see core/reward.py::compute_reward."""

        profile = student_profile or {}
        frustration = profile.get("frustration", 0.5)
        knowledge = profile.get("knowledge", 0.5)
        focus = profile.get("focus", 0.5)

        reward = score * 2.0

        base_ranges = {
            "easy":   (5,  20),
            "medium": (10, 40),
            "hard":   (20, 90),
        }
        lower, upper = base_ranges.get(difficulty, (10, 40))

        upper = upper * (1.0 - 0.3 * knowledge)
        upper = upper * (1.0 + 0.3 * (1.0 - focus))
        upper = upper * (1.0 + 0.4 * frustration)
        lower = lower * (1.0 - 0.2 * frustration)

        if response_time < lower:
            reward -= 0.2
        elif response_time <= upper:
            time_ratio = 1.0 - ((response_time - lower) / (upper - lower))
            reward += 0.3 * time_ratio * score
        else:
            overtime_ratio = (response_time - upper) / upper
            penalty = overtime_ratio * 0.5
            penalty = penalty * (1.0 - 0.5 * frustration)
            reward -= penalty

        reward = max(0.0, min(3.0, reward))
        return round(reward, 4)
