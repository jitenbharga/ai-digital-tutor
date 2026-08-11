"""
P5.1 — Day-7 Retention Tracker

Measures per-user retention by tracking:
  - first_seen: first activity timestamp
  - last_seen: most recent activity
  - active_days: set of unique active dates
  - day_1_returned: bool — active on day after first_seen
  - day_7_returned: bool — active within day 6-8 after first_seen

Designed to feed into A/B experiments: each delight feature gets its own
experiment, and this module provides the retention metric for comparison.

Collection: `retention` — one doc per student.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("retention_tracker")

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        from database import db
        _collection = db["retention"]
    return _collection


async def record_activity(student_id: str, now: Optional[datetime] = None) -> dict:
    """
    Record that a student was active. Call on every meaningful interaction
    (answer, session start, review).

    Returns the updated retention doc.
    """
    now = now or datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    col = _get_collection()

    existing = await col.find_one({"student_id": student_id})

    if existing is None:
        doc = {
            "student_id": student_id,
            "first_seen": now,
            "last_seen": now,
            "active_days": [today],
            "total_active_days": 1,
            "day_1_returned": False,
            "day_7_returned": False,
        }
        await col.insert_one(doc)
        return doc

    # Update last_seen and active_days
    active_days = existing.get("active_days", [])
    if today not in active_days:
        active_days.append(today)

    first_seen = existing.get("first_seen", now)

    # Check retention milestones
    days_since_first = (now - first_seen).days

    day_1 = existing.get("day_1_returned", False)
    if not day_1 and days_since_first >= 1:
        day_1 = True

    day_7 = existing.get("day_7_returned", False)
    if not day_7 and days_since_first >= 6:
        # Active within the day-7 window (day 6-8)
        day_7 = True

    updates = {
        "last_seen": now,
        "active_days": active_days,
        "total_active_days": len(active_days),
        "day_1_returned": day_1,
        "day_7_returned": day_7,
    }

    await col.update_one(
        {"student_id": student_id},
        {"$set": updates},
    )

    return {**existing, **updates}


async def get_retention(student_id: str) -> Optional[dict]:
    """Get retention data for a student."""
    col = _get_collection()
    doc = await col.find_one({"student_id": student_id})
    if doc:
        doc.pop("_id", None)
    return doc


async def get_retention_summary() -> dict:
    """
    Aggregate retention metrics across all users.
    Returns counts and rates for day-1 and day-7 retention.
    """
    col = _get_collection()

    total = await col.count_documents({})
    if total == 0:
        return {
            "total_users": 0,
            "day_1_retained": 0,
            "day_7_retained": 0,
            "day_1_rate": 0.0,
            "day_7_rate": 0.0,
            "avg_active_days": 0.0,
        }

    # Users who were first seen at least 1 day ago
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    eligible_day1 = await col.count_documents({"first_seen": {"$lte": one_day_ago}})
    day1_returned = await col.count_documents({
        "first_seen": {"$lte": one_day_ago},
        "day_1_returned": True,
    })

    # Users who were first seen at least 7 days ago
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    eligible_day7 = await col.count_documents({"first_seen": {"$lte": seven_days_ago}})
    day7_returned = await col.count_documents({
        "first_seen": {"$lte": seven_days_ago},
        "day_7_returned": True,
    })

    # Average active days
    pipeline = [
        {"$group": {"_id": None, "avg": {"$avg": "$total_active_days"}}},
    ]
    cursor = col.aggregate(pipeline)
    avg_doc = await cursor.to_list(length=1)
    avg_active = avg_doc[0]["avg"] if avg_doc else 0.0

    return {
        "total_users": total,
        "eligible_day1": eligible_day1,
        "day_1_retained": day1_returned,
        "day_1_rate": round(day1_returned / max(eligible_day1, 1), 4),
        "eligible_day7": eligible_day7,
        "day_7_retained": day7_returned,
        "day_7_rate": round(day7_returned / max(eligible_day7, 1), 4),
        "avg_active_days": round(avg_active, 2),
    }


async def track_retention_for_experiment(
    student_id: str,
    experiment_id: str,
) -> None:
    """
    If student has day-7 retention data, push it to the A/B experiment
    as a metric. Called periodically or on activity.
    """
    retention = await get_retention(student_id)
    if not retention:
        return

    first_seen = retention.get("first_seen")
    if not first_seen:
        return

    days_since = (datetime.now(timezone.utc) - first_seen).days
    if days_since < 7:
        return  # Too early to measure day-7

    from core.ab_experiment import get_experiment_manager

    mgr = get_experiment_manager()
    arm = await mgr.get_arm(student_id, experiment_id)
    if arm is None:
        return

    # Track day-7 retention as 1.0 (returned) or 0.0 (didn't)
    value = 1.0 if retention.get("day_7_returned", False) else 0.0

    try:
        await mgr.track_metric(
            student_id=student_id,
            experiment_id=experiment_id,
            metric_name="day7_retention",
            value=value,
            properties={
                "total_active_days": retention.get("total_active_days", 0),
                "days_since_first_seen": days_since,
            },
        )
    except Exception as e:
        logger.warning("Failed to track retention metric: %s", e)
