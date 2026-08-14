"""Versioned prompt template for ReviewEngine."""

VERSION = "v1"


def build(
    topic: str,
    days_ago: float,
    mastery: float,
    retention_estimate: float,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
) -> str:

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""{mentor_block}You are generating a REVIEW question (not a new teaching question).

{tone_directive}
{language_directive}

Topic: {topic}
Student last studied this: {days_ago:.1f} days ago
Their mastery when they left: {mastery:.2f}
Their current estimated retention: {retention_estimate:.2f}

Generate a question that:
- Tests if they still remember the core concept
- Is slightly easier than their last difficulty level (build confidence)
- If retention_estimate < 0.4, include a brief refresher before the question

Output ONLY valid JSON:
{{
  "refresher": "1-2 sentence reminder of the key concept (or null if retention > 0.6)",
  "question": "the review question",
  "answer": "correct answer",
  "tests_concept": "what specific knowledge this verifies"
}}"""
