from typing import Dict, List

from adaptive.core.llm_registry import build_models
from adaptive.core.llm_utils import call_llm
from adaptive.core.prompts import socratic as prompt_tmpl


class SocraticEngine:
    """Multi-mode teaching engine controlled by RL."""

    def __init__(self):
        self.models = build_models()

    # MODE 1: SOCRATIC PROBE
    async def generate_socratic_probe(
        self,
        topic: str,
        core_concept: str,
        knowledge_level: float,
        frustration: float,
        curiosity: float,
        conversation_context: List[Dict],
        tone_directive: str = "",
        language_directive: str = "",
        mentor_directive: str = "",
    ) -> Dict:

        last_turns = ""
        if conversation_context:
            recent = conversation_context[-2:]
            for turn in recent:
                role = turn.get("role", "system")
                content = turn.get("content", "")[:200]
                last_turns += f"- {role}: {content}\n"
        if not last_turns:
            last_turns = "No previous exchange (first interaction)"

        prompt = prompt_tmpl.build_probe(
            topic, core_concept, knowledge_level,
            frustration, curiosity, last_turns, tone_directive,
            mentor_directive=mentor_directive,
            language_directive=language_directive,
        )

        data = await call_llm(
            self.models, prompt, required_key="probe",
            engine_name="socratic_probe",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "type": "socratic_probe",
                "question": data["probe"],
                "expected_insight": data.get("expected_insight", ""),
                "follow_up_if_stuck": data.get("follow_up_if_stuck", ""),
                "thinking_direction": data.get("thinking_direction", ""),
                "answer": data.get("expected_insight", ""),
                "model_used": data.get("model_used", "unknown")
            }

        return {
            "type": "socratic_probe",
            "question": f"What do you think happens when we apply {core_concept} to a new situation?",
            "expected_insight": f"Understanding of {core_concept}",
            "follow_up_if_stuck": f"Let's start simpler -- can you explain {core_concept} in your own words?",
            "thinking_direction": "Think about the fundamental principle",
            "answer": f"Understanding of {core_concept}",
            "model_used": "fallback"
        }

    # MODE 2: REVEAL STEP
    async def generate_reveal_step(
        self,
        topic: str,
        core_concept: str,
        knowledge_level: float,
        difficulty: str,
        conversation_context: List[Dict],
        tone_directive: str = "",
        language_directive: str = "",
        mentor_directive: str = "",
    ) -> Dict:

        prompt = prompt_tmpl.build_reveal_step(
            topic, core_concept, knowledge_level, difficulty, tone_directive,
            mentor_directive=mentor_directive,
            language_directive=language_directive,
        )

        data = await call_llm(
            self.models, prompt, required_key="step_2_question",
            engine_name="socratic_reveal",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            revealed_content = (
                f"{data.get('problem_context', '')}\n\n"
                f"Here's Step 1 (solved for you):\n{data.get('step_1_revealed', '')}\n\n"
                f"Now your turn -- {data.get('step_2_question', '')}"
            )
            return {
                "type": "reveal_step",
                "question": data.get("step_2_question", ""),
                "revealed_step": data.get("step_1_revealed", ""),
                "problem_context": data.get("problem_context", ""),
                "answer": data.get("step_2_answer", ""),
                "checkpoint_hint": data.get("checkpoint_hint", ""),
                "full_solution": data.get("full_solution", ""),
                "explanation": revealed_content,
                "model_used": data.get("model_used", "unknown")
            }

        return {
            "type": "reveal_step",
            "question": f"Given what we know about {core_concept}, what would be the next step?",
            "revealed_step": f"Step 1: We start with the definition of {core_concept}",
            "problem_context": f"Working through {topic}",
            "answer": "",
            "checkpoint_hint": "Check if your approach uses the concept correctly",
            "full_solution": "",
            "explanation": f"Let's work through {topic} step by step.",
            "model_used": "fallback"
        }

    # MODE 3: CHALLENGE
    async def generate_challenge(
        self,
        topic: str,
        core_concept: str,
        knowledge_level: float,
        mastery: float,
        difficulty: str,
        conversation_context: List[Dict],
        tone_directive: str = "",
        language_directive: str = "",
        mentor_directive: str = "",
    ) -> Dict:

        prompt = prompt_tmpl.build_challenge(
            topic, core_concept, mastery, difficulty, tone_directive,
            mentor_directive=mentor_directive,
            language_directive=language_directive,
        )

        data = await call_llm(
            self.models, prompt, required_key="challenge_question",
            engine_name="socratic_challenge",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "type": "challenge",
                "question": data.get("challenge_question", ""),
                "why_its_tricky": data.get("why_its_tricky", ""),
                "common_trap": data.get("common_trap", ""),
                "answer": data.get("correct_answer", ""),
                "deep_insight": data.get("deep_insight", ""),
                "explanation": data.get("explanation", ""),
                "model_used": data.get("model_used", "unknown")
            }

        return {
            "type": "challenge",
            "question": f"Can you find a case where {core_concept} doesn't work as expected?",
            "why_its_tricky": "Edge case thinking",
            "common_trap": f"Assuming {core_concept} always applies uniformly",
            "answer": "",
            "deep_insight": f"Deep understanding of {core_concept} boundaries",
            "explanation": "",
            "model_used": "fallback"
        }

    # P2.2: MISCONCEPTION-TARGETED PROBE (after wrong answer)
    async def generate_misconception_probe(
        self,
        topic: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        misconception: str,
        root_concept: str,
        error_type: str = "conceptual",
        tone_directive: str = "",
        language_directive: str = "",
        mentor_directive: str = "",
    ) -> Dict:

        prompt = prompt_tmpl.build_misconception_probe(
            topic, question, student_answer, correct_answer,
            misconception, root_concept, error_type,
            tone_directive=tone_directive,
            language_directive=language_directive,
            mentor_directive=mentor_directive,
        )

        data = await call_llm(
            self.models, prompt, required_key="probe",
            engine_name="socratic_misconception_probe",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "type": "misconception_probe",
                "probe": data["probe"],
                "expected_insight": data.get("expected_insight", ""),
                "follow_up_if_stuck": data.get("follow_up_if_stuck", ""),
                "correct_answer": data.get("correct_answer", correct_answer),
                "model_used": data.get("model_used", "unknown"),
            }

        return {
            "type": "misconception_probe",
            "probe": f"Interesting answer. Can you walk me through why you chose '{student_answer}'? What would happen if we tested it?",
            "expected_insight": f"Understanding of {root_concept}",
            "follow_up_if_stuck": f"Let's think about {root_concept} more carefully.",
            "correct_answer": correct_answer,
            "model_used": "fallback",
        }
