"""Versioned prompt template for AdaptiveExplainer."""

from typing import Dict

VERSION = "v1"

STYLE_INSTRUCTIONS = {
    "visual": 'Use spatial language. Say "picture this...", describe layouts, use ASCII diagrams if helpful.',
    "verbal": "Be precise and formal. Define every term before using it. Use structured logical flow.",
    "example_first": "Start with a concrete, relatable example. THEN extract the general principle from it.",
    "theory_first": "State the rule/theorem clearly first. THEN show examples that demonstrate it.",
    "analogy": "Find a real-world analogy the student already understands. Build the entire explanation around it.",
}


def build(
    topic: str,
    student_profile: Dict,
    tone_directive: str = "",
    language_directive: str = "",
    style: str = "verbal",
    grounding_context: str = "",
    mentor_directive: str = "",
) -> str:

    style_instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["verbal"])

    grounding_block = ""
    if grounding_context:
        grounding_block = f"\n{grounding_context}\n\n----------------------------------\n\n"

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n----------------------------------\n\n"

    prompt = (
        f"{mentor_block}"
        f"You are an adaptive AI tutor.\n\n"
        f"Topic: {topic}\n"
        f"Student Profile: {student_profile}\n\n"
        f"{grounding_block}"
        f"EXPLANATION STYLE: {style}\n"
        f"Style-specific instructions:\n"
        f"- {style_instruction}\n\n"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        f"----------------------------------\n\n"
        f"TEACHING RULES:\n\n"
        f"1. Start from zero understanding\n"
        f"2. First explain WHY topic exists\n"
        f"3. Then explain prerequisites BEFORE main topic\n"
        f"4. Follow sequence:\n"
        f"   prerequisites -> foundation -> core -> examples -> next steps\n\n"
        f"5. Adapt to student:\n\n"
        f"- Low knowledge -> simple language + analogies\n"
        f"- Low focus -> short sections\n"
        f"- High frustration -> slow pace + supportive tone\n"
        f"- High curiosity -> deeper insights\n"
        f"- Low retention -> repeat key ideas\n"
        f"- High cognitive load -> break into chunks\n\n"
        f"6. Maintain engagement:\n"
        f"- ask thinking questions\n"
        f"- give real-life examples\n"
        f"- avoid long paragraphs\n\n"
        f"----------------------------------\n\n"
        f"QUESTION GENERATION RULES:\n\n"
        f"Generate EXACTLY 5 practice questions based ONLY on core_concept.\n\n"
        f"- Do NOT use entire topic, only core_concept\n"
        f"- Difficulty must adapt to student profile\n"
        f"- Follow:\n"
        f"  - easy -> recall / simple\n"
        f"  - medium -> multi-step reasoning\n"
        f"  - hard -> conceptual / tricky\n\n"
        f"- Avoid ambiguity\n"
        f"- Answers must be correct and concise\n"
        f"- Include short explanation\n\n"
        f"----------------------------------\n\n"
        f"OUTPUT FORMAT (STRICT JSON ONLY):\n\n"
    )

    prompt += '{\n'
    prompt += '"intuition": "...",\n'
    prompt += '"prerequisites": ["...", "..."],\n'
    prompt += '"core_concept": "...",\n'
    prompt += '"step_by_step": ["...", "..."],\n'
    prompt += f'"style_used": "{style}",\n'
    prompt += '"practice": [\n'
    for i in range(5):
        comma = "," if i < 4 else ""
        prompt += '  {\n'
        prompt += '    "question": "...",\n'
        prompt += '    "answer": "...",\n'
        prompt += '    "explanation": "short explanation"\n'
        prompt += '  }' + comma + '\n'
    prompt += '],\n'
    prompt += '"next_topics": ["...", "..."],\n'
    prompt += '"references": ["...", "..."]\n'
    prompt += '}\n\n'
    prompt += "Rules:\n"
    prompt += "- Output ONLY JSON\n"
    prompt += "- No extra text\n"
    prompt += "- Keep explanation clear and structured"

    return prompt
