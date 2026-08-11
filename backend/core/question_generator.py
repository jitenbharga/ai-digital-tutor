import logging
from typing import Dict, Any

from core.llm_registry import build_models
from core.llm_utils import call_llm
from core.llm_cache import build_cache_key
from core.prompts import question_generator as prompt_tmpl
from core.answer_verifier import AnswerVerifier
from core.retriever import retrieve, format_grounding_context

logger = logging.getLogger("question_generator")

# Max regeneration attempts when verification fails
MAX_VERIFY_RETRIES = 3


class QuestionGenerator:

    def __init__(self):
        self.models = build_models()
        self.verifier = AnswerVerifier()

    async def generate_question(
        self,
        topic: str,
        difficulty: str,
        frustration: float,
        knowledge: float,
        explanation: Dict[str, Any],
        tone_directive: str = "",
        language_directive: str = "",
        force_fresh: bool = False,
        mentor_directive: str = "",
        last_misconception: str = "",
    ) -> Dict:

        # RAG: retrieve grounding context
        chunks = retrieve(topic, query=topic, k=3)
        grounding_context = format_grounding_context(chunks)
        if not chunks:
            logger.info("UNGROUNDED question generation for topic=%s", topic)

        profile_bucket = {
            "frustration": frustration,
            "knowledge": knowledge,
        }

        for attempt in range(MAX_VERIFY_RETRIES):
            # Force fresh on retries (skip cache for regeneration)
            fresh = force_fresh or (attempt > 0)

            cache_key = build_cache_key(
                engine_name="question_generator",
                topic=topic,
                difficulty=difficulty,
                profile_bucket=profile_bucket,
                prompt_version=prompt_tmpl.VERSION,
            ) if attempt == 0 else None  # Don't cache retries

            prompt = prompt_tmpl.build(
                topic, difficulty, frustration, knowledge, explanation,
                tone_directive, grounding_context=grounding_context,
                mentor_directive=mentor_directive,
                language_directive=language_directive,
                last_misconception=last_misconception,
            )

            data = await call_llm(
                self.models, prompt, required_key="question",
                cache_key=cache_key, force_fresh=fresh,
                engine_name="question_generator",
                prompt_version=prompt_tmpl.VERSION,
            )

            if not data:
                continue

            question_text = data.get("question", "")
            answer_text = data.get("answer", "")
            model_used = data.get("model_used", "unknown")

            # --- G2: Verify the answer key ---
            verification = await self.verifier.verify(
                question=question_text,
                answer=answer_text,
                topic=topic,
                generator_model_name=model_used,
            )

            verified = verification.get("verified")

            if verified is False:
                logger.warning(
                    "Answer verification FAILED (attempt %d/%d): method=%s, details=%s",
                    attempt + 1, MAX_VERIFY_RETRIES,
                    verification.get("method", "?"),
                    verification.get("details", "?"),
                )
                # If the judge provided a better answer, use it on last attempt
                if attempt == MAX_VERIFY_RETRIES - 1 and verification.get("judge_answer"):
                    answer_text = verification["judge_answer"]
                    verified = True
                    verification["method"] = "judge_corrected"
                    logger.info("Using judge's corrected answer on final attempt")
                else:
                    continue  # regenerate

            return {
                "topic": topic,
                "difficulty": difficulty,
                "question": question_text,
                "answer": answer_text,
                "explanation": data.get("explanation", ""),
                "model_used": model_used,
                "verified": bool(verified) if verified is not None else None,
                "verification_method": verification.get("method", "none"),
            }


        # All attempts failed -- fall back to a simple known-good question
        logger.warning(
            "All %d verification attempts failed for topic=%s. Using fallback. Rejection rate=%.1f%%",
            MAX_VERIFY_RETRIES, topic, self.verifier.rejection_rate * 100,
        )
        return {
            "topic": topic,
            "difficulty": difficulty,
            "question": f"Explain the concept of {topic}",
            "answer": "",
            "explanation": "",
            "model_used": "fallback",
            "verified": None,
            "verification_method": "fallback",
        }
