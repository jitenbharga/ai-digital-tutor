from typing import List

from adaptive.core.llm_registry import build_models_cheap
from adaptive.core.llm_utils import call_llm
from adaptive.core.prompts import prerequisite as prompt_tmpl


class PrerequisiteEngine:

    def __init__(self):
        self.models = build_models_cheap()  # P3.1: classification uses cheap tier

    async def get_prerequisites(self, topic: str) -> List[str]:

        prompt = prompt_tmpl.build(topic)

        data = await call_llm(
            self.models, prompt, required_key="prerequisites",
            engine_name="prerequisite",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return self._clean_topics(data["prerequisites"])

        return [f"basics of {topic}"]

    def _clean_topics(self, topics: List[str]) -> List[str]:
        cleaned = []
        for t in topics:
            t = str(t).strip().lower()
            if t and t not in cleaned:
                cleaned.append(t)
        return cleaned[:5]
