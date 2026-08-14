"""Versioned prompt template for ProgressiveChallengeEngine."""

VERSION = "v1"


def build(
    topic: str,
    mastery: float,
    difficulty: str = "medium",
    tone_directive: str = "",
    language_directive: str = "",
) -> str:

    return (
        "You are creating a PROGRESSIVE CHALLENGE -- a multi-step problem.\n\n"
        f"Topic: {topic}\n"
        f"Student mastery: {mastery:.2f}\n"
        f"Difficulty: {difficulty}\n\n"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        "Create a problem with 3-4 steps where:\n"
        "- Step 1 uses a concept they know well\n"
        "- Each subsequent step adds one new layer\n"
        "- The final step combines everything\n"
        "- Each step has a clear checkpoint answer\n\n"
        "Output ONLY valid JSON:\n"
        "{\n"
        '  "problem_statement": "the full problem",\n'
        '  "steps": [\n'
        "    {\n"
        '      "step": 1,\n'
        '      "sub_problem": "what to solve in this step",\n'
        '      "checkpoint_answer": "expected result",\n'
        '      "hint_if_stuck": "nudge without giving away",\n'
        '      "concept_tested": "what this step verifies"\n'
        "    }\n"
        "  ],\n"
        '  "final_answer": "...",\n'
        '  "learning_arc": "what the student learns by completing all steps"\n'
        "}"
    )
