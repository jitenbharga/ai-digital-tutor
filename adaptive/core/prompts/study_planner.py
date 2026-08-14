"""Versioned prompt template for StudyPlanner."""

VERSION = "v1"


def build(
    weak_str: str,
    strong_str: str,
    profile: dict,
    available_minutes: int,
    tone_directive: str = "",
    language_directive: str = "",
) -> str:

    return (
        "You are an AI study planner.\n"
        "Student Profile:\n"
        f"- Weak concepts: {weak_str}\n"
        f"- Strong concepts: {strong_str}\n"
        f"- Average session length: {profile['avg_session_minutes']} minutes\n"
        f"- Current fatigue: {profile['fatigue']}\n"
        f"- Current frustration: {profile['frustration']}\n"
        f"- Current streak: {profile['streak']} days\n"
        f"- Overall engagement trend: {profile['engagement_trend']}\n\n"
        f"Today's constraints:\n"
        f"- Available time: {available_minutes} minutes\n"
        f"- Day of week: {profile['day']}\n\n"
        f"{tone_directive}\n"
        f"{language_directive}\n\n"
        "Generate a study plan that:\n"
        "- Starts with a quick review of something they're good at (confidence boost)\n"
        "- Spends 60% time on weak concepts\n"
        "- Alternates hard and easy topics to manage fatigue\n"
        "- Ends with something engaging (not the hardest topic)\n\n"
        "Output ONLY valid JSON:\n"
        '{\n'
        '  "plan": [\n'
        '    {"topic": "...", "duration_min": 10, "type": "review|learn|practice", "reason": "why this order"},\n'
        '    ...\n'
        '  ],\n'
        '  "motivational_note": "personalized encouragement based on their progress",\n'
        '  "estimated_knowledge_gain": "what they should know after this session"\n'
        '}'
    )
