"""Versioned prompt template for LLMAnswerEvaluator (G3: coarse rubric)."""

from utils.prompt_safety import wrap_student_text

VERSION = "v3"


def build(
    question: str,
    student_answer: str,
    correct_answer: str,
    topic: str = "",
    knowledge: float = 0.5,
) -> str:

    safe_answer = wrap_student_text(student_answer, "student_answer")

    return f"""You are an expert educational diagnostician grading a student's answer.

Question: {question}
Reference Answer: {correct_answer}
{safe_answer}
Topic: {topic}
Student Knowledge Level: {knowledge:.2f}

IMPORTANT: Grade the student's answer AGAINST the reference answer above. Do not judge freely.

Use this COARSE rubric (not a fine-grained 0-1 score):
- "correct" — the student's answer is equivalent to the reference (may use different wording)
- "partially_correct" — captures the core idea but has meaningful gaps or minor errors
- "incorrect" — fundamentally wrong, missing the point, or a non-answer

Output STRICT JSON:
{{{{
  "grade": "correct" | "partially_correct" | "incorrect",
  "confidence": 0.0 to 1.0,
  "error_type": "conceptual" | "procedural" | "careless" | "terminology" | "none",
  "misconception": "specific wrong mental model, or null",
  "root_concept": "the prerequisite concept they're missing, or null",
  "reasoning": "why this grade (compare to reference answer)",
  "targeted_feedback": "one sentence addressing their specific error",
  "remediation": "what to review next",
  "mistakes": ["list of specific mistakes"],
  "improvement": "how student can improve"
}}}}

Confidence guide:
- 1.0: Unambiguously correct or incorrect, no room for interpretation
- 0.7-0.9: Very likely this grade, minor ambiguity
- 0.4-0.6: Genuinely uncertain, could reasonably go either way
- 0.1-0.3: Guessing, answer is very hard to evaluate

Error type guide:
- conceptual: fundamentally wrong understanding
- procedural: right idea, wrong steps
- careless: clearly knows it but made a slip
- terminology: used wrong term but understands concept
- none: answer is correct
"""
