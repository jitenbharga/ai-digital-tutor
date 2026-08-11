"""Versioned prompt template for PrerequisiteEngine."""

VERSION = "v1"


def build(topic: str) -> str:

    return f"""
You are an expert curriculum designer.

Topic: {topic}

Return STRICT JSON only.

Format:
{{
  "prerequisites": ["topic1", "topic2", "topic3"]
}}

Rules:
- 3 to 5 prerequisites
- Only topic names
- No explanation
- Keep them precise and standard academic terms
"""
