import logging
from typing import Dict

from core.llm_registry import build_models
from core.llm_utils import call_llm
from core.llm_cache import build_cache_key
from core.prompts import explainer as prompt_tmpl
from core.retriever import retrieve, format_grounding_context

logger = logging.getLogger("adaptive_explainer")


class AdaptiveExplainer:

    EXPLANATION_STYLES = [
        "visual",
        "verbal",
        "example_first",
        "theory_first",
        "analogy",
    ]

    def __init__(self):
        self.models = build_models()

    @staticmethod
    def select_style(student_profile: Dict) -> str:
        knowledge = student_profile.get("knowledge", 0.5)
        mastery = student_profile.get("mastery", 0.5)
        curiosity = student_profile.get("curiosity", 0.5)
        frustration = student_profile.get("frustration", 0.1)
        confidence = student_profile.get("confidence", 0.5)
        retention = student_profile.get("retention", 0.6)

        if frustration > 0.6 or knowledge < 0.3:
            return "example_first"
        if retention < 0.4:
            return "visual"
        if curiosity > 0.7 and knowledge > 0.4:
            return "analogy"
        if confidence > 0.7 and mastery > 0.6:
            return "theory_first"
        return "verbal"

    async def generate_explanation(
        self,
        topic: str,
        student_profile: Dict,
        tone_directive: str = "",
        language_directive: str = "",
        style: str = "",
        force_fresh: bool = False,
        mentor_directive: str = "",
    ) -> Dict:

        if not style:
            style = self.select_style(student_profile)

        # RAG: retrieve grounding context
        chunks = retrieve(topic, query=topic, k=3)
        grounding_context = format_grounding_context(chunks)
        if not chunks:
            logger.info("UNGROUNDED generation for topic=%s (no content found)", topic)

        profile_bucket = {
            k: v for k, v in student_profile.items()
            if isinstance(v, (int, float))
        }
        cache_key = build_cache_key(
            engine_name="explainer",
            topic=topic,
            profile_bucket=profile_bucket,
            prompt_version=prompt_tmpl.VERSION,
            extra={"style": style},
        )

        prompt = prompt_tmpl.build(
            topic, student_profile, tone_directive,
            style=style, grounding_context=grounding_context,
            mentor_directive=mentor_directive,
            language_directive=language_directive,
        )

        data = await call_llm(
            self.models, prompt, required_key="core_concept",
            cache_key=cache_key, force_fresh=force_fresh,
            engine_name="explainer",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return data

        return {
            "intuition": f"Basic idea of {topic}",
            "prerequisites": [],
            "core_concept": f"{topic} explanation",
            "step_by_step": [],
            "practice": [],
            "next_topics": [],
            "references": [],
            "model_used": "fallback"
        }
