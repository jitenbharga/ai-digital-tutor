"""Versioned prompt templates for SocraticEngine (3 modes)."""

from typing import Dict, List
from adaptive.utils.prompt_safety import wrap_student_text

VERSION = "v2"


def build_probe(
    topic: str,
    core_concept: str,
    knowledge_level: float,
    frustration: float,
    curiosity: float,
    last_turns: str,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
) -> str:

    frust_note = ""
    if frustration > 0.6:
        frust_note = f"IMPORTANT: Student frustration is HIGH ({frustration:.2f}). Make the probe easier and more guiding. Use encouraging language."

    curiosity_note = ""
    if curiosity > 0.7:
        curiosity_note = f"Student curiosity is HIGH ({curiosity:.2f}). Make it deeper and more thought-provoking. Add an unexpected angle."

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""{mentor_block}You are a Socratic tutor. Do NOT give the answer.

{tone_directive}
{language_directive}

Topic: {topic}
Concept being taught: {core_concept}
Student's current understanding: {knowledge_level:.2f} (0=none, 1=expert)
Previous exchange:
{last_turns}

Generate ONE probing question that:
- Targets the gap between what they know and what they need
- Makes them realize the answer themselves
- Is specific, not vague ("What happens to X when Y changes?" not "What do you think?")

{frust_note}
{curiosity_note}

Output ONLY valid JSON:
{{
    "probe": "your probing question",
    "expected_insight": "what the student should realize from this",
    "follow_up_if_stuck": "simpler version of the same probe",
    "thinking_direction": "brief hint about which direction to think"
}}"""


def build_reveal_step(
    topic: str,
    core_concept: str,
    knowledge_level: float,
    difficulty: str,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
) -> str:

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""{mentor_block}You are an expert tutor using scaffolded teaching.

{tone_directive}
{language_directive}

Topic: {topic}
Concept: {core_concept}
Student knowledge: {knowledge_level:.2f}
Difficulty: {difficulty}

Create a multi-step problem. REVEAL only Step 1, then ask the student to do Step 2.

Rules:
- Step 1 must be fully solved (show the work)
- Step 2 must follow logically from Step 1
- Step 2 should be slightly harder than Step 1
- Include a checkpoint so the student knows if they're on track

Output ONLY valid JSON:
{{
    "problem_context": "the overall problem setup",
    "step_1_revealed": "fully solved first step with explanation",
    "step_2_question": "what the student needs to solve next",
    "step_2_answer": "correct answer for step 2",
    "checkpoint_hint": "how to verify they're on the right track",
    "full_solution": "complete solution for reference"
}}"""


def build_challenge(
    topic: str,
    core_concept: str,
    mastery: float,
    difficulty: str,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
) -> str:

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""{mentor_block}You are an advanced tutor pushing a strong student to think deeper.

{tone_directive}
{language_directive}

Topic: {topic}
Concept: {core_concept}
Student mastery: {mastery:.2f} (high -- they understand the basics well)
Difficulty: {difficulty}

Generate a CHALLENGE question that:
- Tests edge cases or common misconceptions
- Requires applying the concept in an unexpected way
- Might have a counter-intuitive answer
- Frces the student to think beyond textbook definitions

Include a "trap" -- a common wrong answer that seems right.

Output ONLY valid JSON:
{{
    "challenge_question": "the challenging question",
    "why_its_tricky": "what makes this question deceptive",
    "common_trap": "the wrong answer most students give",
    "correct_answer": "the actual correct answer",
    "deep_insight": "what understanding this question tests",
    "explanation": "full explanation of why the answer is what it is"
}}"""


def build_misconception_probe(
    topic: str,
    question: str,
    student_answer: str,
    correct_answer: str,
    misconception: str,
    root_concept: str,
    error_type: str,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
) -> str:
    """P2.2: After a wrong answer, generate a Socratic probe that targets
    the specific misconception instead of just explaining the answer."""

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""{mentor_block}You are a Socratic tutor. The student just answered incorrectly.

{tone_directive}
{language_directive}

DO NOT reveal the correct answer. Instead, ask a targeted question that helps
the student discover their own mistake.

Topic: {topic}
Question they got wrong: {question}
{wrap_student_text(student_answer, "student_answer")}
Their misconception: {misconception}
Root concept they're missing: {root_concept}
Error type: {error_type}

Your probe must:
1. Target the SPECIFIC misconception (not a generic "think again")
2. Lead them toward the correct reasoning without stating it
3. Be concrete — reference their actual answer and why it doesn't hold
4. Be short (1-2 sentences max)

Output ONLY valid JSON:
{{
    "probe": "your targeted Socratic question (1-2 sentences)",
    "expected_insight": "what the student should realize",
    "follow_up_if_stuck": "an even simpler nudge if they're still lost",
    "correct_answer": "{correct_answer}"
}}"""
