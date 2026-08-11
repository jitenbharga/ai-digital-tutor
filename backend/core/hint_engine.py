from core.llm_registry import build_models
from core.llm_utils import call_llm_text
from core.prompts import hint as prompt_tmpl


class HintGenerator:

    def __init__(self):
        self.models = build_models()

    async def generate_hint(self, question: str, tone_directive: str = "", language_directive: str = "", mentor_directive: str = "") -> str:

        prompt = prompt_tmpl.build(question, tone_directive, mentor_directive=mentor_directive, language_directive=language_directive)

        result = await call_llm_text(
            self.models, prompt, min_length=10,
            engine_name="hint",
            prompt_version=prompt_tmpl.VERSION,
        )

        if result:
            return result

        return "- Break the problem into smaller parts\n- Identify known formulas\n- Try solving step by step"
