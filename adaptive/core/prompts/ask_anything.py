"""Versioned prompt templates for Ask-Anything (N1) and Explain-Again (N2)."""

from adaptive.utils.prompt_safety import wrap_student_text

VERSION = "v1"


def build_topic_classifier(user_question: str) -> str:
    """Classify the user's free-form question into a known topic/concept."""
    safe_question = wrap_student_text(user_question, "student_question")
    return (
        f"You are a topic classifier for an educational AI tutor.\n\n"
        f"A student asked this question:\n"
        f'{safe_question}\n\n'
        f"Identify the subject and specific topic/concept this question belongs to.\n\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        f'{{\n'
        f'  "subject": "the broad subject (e.g. Mathematics, Physics, Computer Science, Biology)",\n'
        f'  "topic": "the specific topic (e.g. Quadratic Equations, Newton\'s Laws, Arrays)",\n'
        f'  "concept": "the core concept being asked about",\n'
        f'  "difficulty_estimate": "easy | medium | hard",\n'
        f'  "is_homework": true or false\n'
        f'}}\n\n'
        f"Rules:\n"
        f"- Output ONLY JSON, no extra text\n"
        f"- Be specific with the topic, not too broad\n"
        f"- is_homework = true if the question looks like a homework/assignment problem\n"
    )


def build_socratic_help(
    user_question: str,
    topic: str,
    concept: str,
    student_profile: dict,
    conversation_context: str = "",
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
    grounding_context: str = "",
    is_homework: bool = False,
) -> str:
    """Build prompt for Socratic help on user's own question."""

    mentor_block = f"{mentor_directive}\n\n---\n\n" if mentor_directive else ""
    grounding_block = f"\n{grounding_context}\n\n---\n\n" if grounding_context else ""
    context_block = (
        f"\nPrevious conversation:\n{conversation_context}\n\n---\n\n"
        if conversation_context else ""
    )

    homework_guard = ""
    if is_homework:
        homework_guard = (
            "\nIMPORTANT — HOMEWORK DETECTED:\n"
            "This appears to be a homework/assignment problem. You must NOT give the final answer.\n"
            "Instead: guide the student to discover the answer themselves through scaffolded steps.\n"
            "Break it down, ask what they've tried, probe their understanding.\n\n"
        )

    safe_question = wrap_student_text(user_question, "student_question")
    return (
        f"{mentor_block}"
        f"You are a Socratic AI tutor helping a student with THEIR OWN question.\n\n"
        f"Student's question:\n"
        f'{safe_question}\n\n'
        f"Topic: {topic}\n"
        f"Core concept: {concept}\n"
        f"Student profile: {student_profile}\n\n"
        f"{grounding_block}"
        f"{context_block}"
        f"{homework_guard}"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        f"---\n\n"
        f"TEACHING APPROACH:\n"
        f"1. Acknowledge their question warmly\n"
        f"2. Probe what they already know or have tried\n"
        f"3. Break the problem into smaller pieces\n"
        f"4. Guide with leading questions — don't dump the answer\n"
        f"5. If they're stuck, give progressively stronger hints\n"
        f"6. When they reach the answer, confirm and reinforce the concept\n\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        f'{{\n'
        f'  "response": "your Socratic response to the student (markdown OK)",\n'
        f'  "probing_question": "a question to check their understanding",\n'
        f'  "hint_if_stuck": "a hint if they can\'t answer the probe",\n'
        f'  "concept_connection": "how this connects to the broader topic",\n'
        f'  "next_step": "what to explore next if they get it right"\n'
        f'}}\n\n'
        f"Rules:\n"
        f"- Output ONLY JSON, no extra text\n"
        f"- NEVER reveal the full answer directly\n"
        f"- Be encouraging and patient\n"
        f"- Use the student's language level\n"
    )


def build_explain_again(
    topic: str,
    concept: str,
    original_explanation: str,
    style: str,
    student_profile: dict,
    tone_directive: str = "",
    language_directive: str = "",
    mentor_directive: str = "",
    grounding_context: str = "",
) -> str:
    """Build prompt for re-explaining a concept in a different style."""

    mentor_block = f"{mentor_directive}\n\n---\n\n" if mentor_directive else ""
    grounding_block = f"\n{grounding_context}\n\n---\n\n" if grounding_context else ""

    style_instructions = {
        "simpler": (
            "Explain this as simply as possible. Use everyday language a 10-year-old would understand. "
            "Avoid jargon. Short sentences. Concrete examples."
        ),
        "analogy": (
            "Explain this using a real-world analogy the student already understands. "
            "Find a vivid comparison from daily life and build the entire explanation around it."
        ),
        "worked_example": (
            "Explain this through a complete worked example. Show every step of solving a concrete "
            "problem, explaining WHY each step is done, not just what."
        ),
        "step_by_step": (
            "Break this into the smallest possible steps. Number each step. "
            "Each step should be one single idea. Explain the reasoning for each transition."
        ),
    }

    style_inst = style_instructions.get(style, style_instructions["simpler"])

    return (
        f"{mentor_block}"
        f"You are an adaptive AI tutor. A student didn't understand an explanation and is "
        f"asking you to explain it differently.\n\n"
        f"Topic: {topic}\n"
        f"Concept: {concept}\n"
        f"Student profile: {student_profile}\n\n"
        f"The previous explanation was:\n"
        f'"""\n{original_explanation}\n"""\n\n'
        f"The student wants a DIFFERENT explanation.\n\n"
        f"{grounding_block}"
        f"STYLE REQUESTED: {style}\n"
        f"Instructions: {style_inst}\n\n"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        f"---\n\n"
        f"CRITICAL RULES:\n"
        f"1. The new explanation must be GENUINELY DIFFERENT from the previous one\n"
        f"2. Don't just reword — use a completely different approach\n"
        f"3. Adapt to the student's level\n"
        f"4. Keep it focused on the specific concept\n\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        f'{{\n'
        f'  "explanation": "the new explanation in the requested style (markdown OK)",\n'
        f'  "style_used": "{style}",\n'
        f'  "key_takeaway": "one sentence summary of the concept",\n'
        f'  "check_understanding": "a quick question to verify they got it"\n'
        f'}}\n\n'
        f"Rules:\n"
        f"- Output ONLY JSON, no extra text\n"
        f"- Make the explanation GENUINELY different from the original\n"
    )
