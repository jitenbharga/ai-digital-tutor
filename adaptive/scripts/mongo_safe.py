"""Safe MongoDB query helpers (SEC-2).

User-supplied strings must never reach a Mongo ``$regex`` as a raw pattern:
a crafted value like ``(a+)+$`` triggers catastrophic backtracking (ReDoS)
and a ``.*`` silently matches everything, breaking intended scoping.

These helpers escape the input to a literal and cap its length before use.
"""
import re

# Cap topic length before it ever reaches the database.
MAX_TOPIC_LEN = 100


def normalize_topic(topic: str) -> str:
    """Trim and length-cap a user-supplied topic string."""
    if not topic:
        return ""
    return str(topic).strip()[:MAX_TOPIC_LEN]


def safe_topic_filter(topic: str) -> dict:
    """Return a Mongo filter that matches the topic as an escaped literal.

    ``re.escape`` neutralizes every regex metacharacter, so the value is
    treated as plain text (case-insensitive substring), never as a pattern.
    """
    literal = re.escape(normalize_topic(topic))
    return {"$regex": literal, "$options": "i"}


def exact_topic_value(topic: str) -> str:
    """Normalized, lower-cased topic for exact-equality lookups (no regex)."""
    return normalize_topic(topic).lower()
