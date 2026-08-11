"""Versioned prompt template for QuizGenerator."""

VERSION = "v1"


def build(topic: str, num_questions: int = 10, tone_directive: str = "", language_directive: str = "") -> str:
    return (
        "You are an expert quiz creator for educational assessments.\n\n"
        f"Topic: {topic}\n"
        f"Number of questions: {num_questions}\n\n"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        "Generate a quiz with the following requirements:\n"
        "- Each question tests a specific concept within the topic\n"
        "- Each question has exactly 4 options labeled A, B, C, D\n"
        "- Some questions should be single-correct, some should be multiple-correct\n"
        "- Questions should range from basic recall to application/analysis\n"
        "- Include a brief explanation for each correct answer\n\n"
        "Output ONLY valid JSON:\n"
        "{\n"
        '  "quiz_title": "Quiz: <topic>",\n'
        '  "questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "...",\n'
        '      "options": {\n'
        '        "A": "...",\n'
        '        "B": "...",\n'
        '        "C": "...",\n'
        '        "D": "..."\n'
        "      },\n"
        '      "correct": ["B"],\n'
        '      "multiple": false,\n'
        '      "concept": "what concept this tests",\n'
        '      "explanation": "why the correct answer is correct",\n'
        '      "difficulty": "easy|medium|hard"\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}"
    )
