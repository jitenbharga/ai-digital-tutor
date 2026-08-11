"""Versioned prompt template for QuestionGenerator."""

from typing import Any, Dict

VERSION = "v2"


def build(
    topic: str,
    difficulty: str,
    frustration: float,
    knowledge: float,
    explanation: Dict[str, Any],
    tone_directive: str = "",
    language_directive: str = "",
    grounding_context: str = "",
    mentor_directive: str = "",
    last_misconception: str = "",
) -> str:

    grounding_block = ""
    if grounding_context:
        grounding_block = f"\n{grounding_context}\n"

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"\n{mentor_directive}\n"

    misconception_block = ""
    if last_misconception:
        misconception_block = (
            f"IMPORTANT: The student just demonstrated this misconception: "
            f"'{last_misconception}'. Design the next question to specifically "
            f"test whether they have corrected this misunderstanding. Do NOT "
            f"repeat the same question -- create a new one that probes the same "
            f"underlying concept from a different angle.\n\n"
        )

    return f"""
{mentor_block}
You are a strict educational system.

{tone_directive}
{language_directive}
{grounding_block}
Generate exactly ONE question.

Topic: {topic}
explanation: {explanation}
Difficulty: {difficulty}
Frustration: {frustration}
Knowledge: {knowledge}

Difficulty Guidelines:
- easy -> basic recall / simple application
- medium -> multi-step reasoning
- hard -> deeper conceptual or tricky problem

{misconception_block}Rules:
- question must be generated based on topic and explanation
- question difficulty must match guidelines
- Output ONLY valid JSON
- No explanation outside JSON
- Answer must be correct and concise
- Avoid ambiguity

Format:
{{{{
"question": "...",
"answer": "...",
"explanation": "short explanation"
}}}}
"""
