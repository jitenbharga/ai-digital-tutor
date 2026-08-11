"""
P0.3 — Product Analytics Instrumentation

Lightweight event tracking to MongoDB. Tracks:
  - Onboarding completion
  - Session starts / answers / drop-off
  - Day-1 / Day-7 retention
  - Questions answered per session

All events go to the `analytics_events` collection.
Query with scripts/analytics_report.py.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("analytics")

# Lazy reference to collection — set on first use
_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        from database import db
        _collection = db["analytics_events"]
    return _collection


async def track_event(
    event: str,
    student_id: str,
    properties: Optional[dict] = None,
):
    """
    Log an analytics event.

    Args:
        event: Event name (e.g., "onboarding_complete", "session_start", "answer_submitted")
        student_id: Who triggered it
        properties: Optional dict of extra data
    """
    doc = {
        "event": event,
        "student_id": student_id,
        "timestamp": datetime.now(timezone.utc),
        "properties": properties or {},
    }
    try:
        await _get_collection().insert_one(doc)
    except Exception as e:
        logger.warning("analytics.track_event failed: %s", e)


# ── Convenience wrappers ──

async def track_signup(student_id: str, account_type: str = "student"):
    await track_event("signup", student_id, {"account_type": account_type})


async def track_onboarding_start(student_id: str):
    await track_event("onboarding_start", student_id)


async def track_onboarding_complete(student_id: str, topics_assessed: int = 0):
    await track_event("onboarding_complete", student_id, {"topics_assessed": topics_assessed})


async def track_session_start(student_id: str, topic: str = ""):
    await track_event("session_start", student_id, {"topic": topic})


async def track_answer(student_id: str, topic: str, correct: bool, difficulty: str = ""):
    await track_event("answer_submitted", student_id, {
        "topic": topic, "correct": correct, "difficulty": difficulty,
    })


async def track_drop_off(student_id: str, page: str = "", reason: str = ""):
    await track_event("drop_off", student_id, {"page": page, "reason": reason})
