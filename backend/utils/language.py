"""
Build a language + reading-level directive string to inject into every LLM prompt.
Loaded from the student's persisted preferences in MongoDB.

B5: supports English, Hindi, Hinglish (code-switched, Roman script) and major
regional Indian languages. Universal rule: math notation, code, and standard
technical terms stay in English/Latin script — that's how they appear in
textbooks and exams, so translating them hurts learners.
"""

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
}

# BCP-47 codes for browser TTS/STT voice selection
SPEECH_CODES = {
    "en": "en-IN", "hi": "hi-IN", "hinglish": "hi-IN",
    "ta": "ta-IN", "te": "te-IN", "bn": "bn-IN", "mr": "mr-IN",
    "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN", "pa": "pa-IN",
}

_KEEP_TECHNICAL = (
    "Keep mathematical notation, code, formulas, and standard technical terms "
    "(e.g. 'array', 'photosynthesis', 'quadratic equation') in English/Latin "
    "script exactly as they appear in textbooks — do NOT translate them."
)

_NATIVE_SCRIPT_TEMPLATE = (
    "LANGUAGE: Respond entirely in {name} (native script). Use {name} for "
    "explanations, questions, hints, and feedback. " + _KEEP_TECHNICAL
)

_DIRECTIVES = {
    "hi": (
        "LANGUAGE: Respond entirely in Hindi (Devanagari script). "
        "Use Hindi for explanations, questions, hints, and feedback. "
        + _KEEP_TECHNICAL
    ),
    "hinglish": (
        "LANGUAGE: Respond in Hinglish — natural Hindi-English code-switching "
        "written in Roman (Latin) script, the way Indian students actually talk. "
        "Hindi sentence structure and connectors ('samajh gaye?', 'chalo dekhte "
        "hain', 'iska matlab hai ki...'), with English for technical terms. "
        "Friendly, conversational register — like a helpful senior explaining. "
        "Example tone: 'Dekho, variable basically ek container hota hai jisme "
        "hum value store karte hain.' " + _KEEP_TECHNICAL
    ),
}
for _code in ("ta", "te", "bn", "mr", "gu", "kn", "ml", "pa"):
    _DIRECTIVES[_code] = _NATIVE_SCRIPT_TEMPLATE.format(name=LANGUAGE_NAMES[_code])


def get_language_directive(preferences: dict | None) -> str:
    """
    Returns a combined language + reading-level instruction for LLM prompts.
    preferences is the dict stored on the user doc (or None for defaults).
    """
    # Defensive: some callers historically passed a username string or a
    # Student object. Only a real preferences dict is meaningful here.
    if not isinstance(preferences, dict):
        return ""

    lang = preferences.get("language", "en")
    level = preferences.get("reading_level", "standard")

    parts = []

    # Language directive (English is the default — no directive needed)
    directive = _DIRECTIVES.get(lang)
    if directive:
        parts.append(directive)

    # Reading level directive
    if level == "simple":
        parts.append(
            "READING LEVEL: Use simple language suitable for young learners (ages 8-12). "
            "Short sentences (max 15 words). Basic vocabulary only. "
            "Avoid jargon — if a technical term is needed, define it immediately. "
            "Use examples from everyday life."
        )

    if not parts:
        return ""

    return "\n".join(parts)


def get_speech_code(preferences: dict | None) -> str:
    """BCP-47 speech code for TTS/STT matching the student's language."""
    lang = (preferences or {}).get("language", "en")
    return SPEECH_CODES.get(lang, "en-IN")
