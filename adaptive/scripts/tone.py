def get_tone_directive(student):
    """
    Returns an emotional tone instruction to inject into every LLM prompt.
    The RL agent indirectly controls this via the student state it shapes.
    """

    if student.frustration > 0.7:
        return (
            "TONE: Be warm, patient, and encouraging. "
            "Use phrases like 'This is tricky, but you're on the right track.' "
            "Break into smaller pieces. Celebrate partial understanding."
        )

    elif student.confidence > 0.8 and student.engagement > 0.7:
        return (
            "TONE: Be intellectually challenging. "
            "Push them with 'But what if...?' and edge cases. "
            "Don't over-explain."
        )

    elif student.fatigue > 0.6:
        return (
            "TONE: Be brief and energetic. Use short sentences. "
            "Add a real-world hook to re-engage."
        )

    elif student.curiosity > 0.7:
        return (
            "TONE: Feed their curiosity with 'Here's something most people don't know...' "
            "Go deeper than textbook."
        )

    else:
        return "TONE: Clear, balanced, supportive. Standard teaching pace."
