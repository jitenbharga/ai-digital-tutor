"""Versioned prompt template for HintGenerator."""

VERSION = "v1"


def build(question: str, tone_directive: str = "", language_directive: str = "", mentor_directive: str = "") -> str:

    mentor_block = ""
    if mentor_directive:
        mentor_block = f"{mentor_directive}\n\n"

    return f"""
{mentor_block}You are a helpful tutor.

{tone_directive}
{language_directive}

Give a HINT (not the full solution) for the following problem.

Rules:
- Do NOT give the final answer
- Do NOT fully solve it
- Give 1-3 step guidance only
- Use bullet points
- Keep it short and clear

Question:
{question}
"""
