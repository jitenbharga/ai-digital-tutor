from typing import Dict

from adaptive.core.llm_registry import build_models
from adaptive.core.llm_utils import call_llm
from adaptive.core.prompts import progressive_challenge as prompt_tmpl


class ProgressiveChallengeEngine:

    def __init__(self):
        self.models = build_models()

    async def generate_challenge(
        self,
        topic: str,
        mastery: float,
        difficulty: str = "medium",
        tone_directive: str = "",
        language_directive: str = "",
    ) -> Dict:

        prompt = prompt_tmpl.build(topic, mastery, difficulty, tone_directive, language_directive=language_directive)

        data = await call_llm(
            self.models, prompt, required_key="steps",
            engine_name="progressive_challenge",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            steps = data.get("steps", [])
            normalized_steps = []
            for i, s in enumerate(steps):
                normalized_steps.append({
                    "step": s.get("step", i + 1),
                    "sub_problem": s.get("sub_problem", ""),
                    "checkpoint_answer": s.get("checkpoint_answer", ""),
                    "hint_if_stuck": s.get("hint_if_stuck", ""),
                    "concept_tested": s.get("concept_tested", ""),
                })
            return {
                "topic": topic,
                "difficulty": difficulty,
                "problem_statement": data.get("problem_statement", ""),
                "steps": normalized_steps,
                "final_answer": data.get("final_answer", ""),
                "learning_arc": data.get("learning_arc", ""),
                "model_used": data.get("model_used", "unknown"),
            }

        return {
            "topic": topic,
            "difficulty": difficulty,
            "problem_statement": f"Solve a multi-step {topic} problem.",
            "steps": [
                {"step": 1, "sub_problem": f"Recall the basic definition of {topic}.", "checkpoint_answer": "", "hint_if_stuck": f"Think about what {topic} means at its core.", "concept_tested": f"Basic recall of {topic}"},
                {"step": 2, "sub_problem": f"Apply the core idea of {topic} to a simple case.", "checkpoint_answer": "", "hint_if_stuck": "Try using the definition from step 1.", "concept_tested": f"Application of {topic}"},
                {"step": 3, "sub_problem": f"Combine what you learned to solve a harder variation.", "checkpoint_answer": "", "hint_if_stuck": "Use the results from steps 1 and 2 together.", "concept_tested": f"Synthesis of {topic} concepts"},
            ],
            "final_answer": "",
            "learning_arc": f"Building from basics to applied understanding of {topic}.",
            "model_used": "fallback",
        }
