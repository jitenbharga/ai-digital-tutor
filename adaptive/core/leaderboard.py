"""
P5.3 — Weekly Cohort Leaderboard

Opt-in weekly leaderboard ranked by XP earned that week.
  - Resets every Monday 00:00 UTC
  - Anonymized display names for privacy
  - Opt-in via leaderboard preference
  - Top-N visible (default 20)

Collection: `leaderboard_entries` — one doc per student per week.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("leaderboard")

_entries_col = None


def _get_collection():
    global _entries_col
    if _entries_col is None:
        from database import db
        _entries_col = db["leaderboard_entries"]
    return _entries_col


def _week_key(now: Optional[datetime] = None) -> str:
    """ISO week key: 'YYYY-WNN' (e.g. '2026-W27')."""
    now = now or datetime.now(timezone.utc)
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _anonymize(student_id: str) -> str:
    """Generate a fun, deterministic anonymous name from student_id."""
    adjectives = [
        "Swift", "Bright", "Clever", "Bold", "Keen",
        "Sharp", "Quick", "Calm", "Wise", "Brave",
        "Eager", "Noble", "Witty", "Lively", "Steady",
    ]
    animals = [
        "Falcon", "Dolphin", "Fox", "Owl", "Panther",
        "Eagle", "Wolf", "Tiger", "Hawk", "Lynx",
        "Otter", "Raven", "Puma", "Cobra", "Bear",
    ]
    h = int(hashlib.sha256(student_id.encode()).hexdigest()[:8], 16)
    adj = adjectives[h % len(adjectives)]
    animal = animals[(h >> 8) % len(animals)]
    num = (h >> 16) % 100
    return f"{adj}{animal}{num:02d}"


async def is_opted_in(student_id: str) -> bool:
    """Check if student has opted into leaderboard."""
    from database import student_states_collection
    state = await student_states_collection.find_one({"student_id": student_id})
    if not state:
        return False
    return state.get("leaderboard_opted_in", False)


async def set_opt_in(student_id: str, opted_in: bool) -> None:
    """Set leaderboard opt-in preference."""
    from database import student_states_collection
    await student_states_collection.update_one(
        {"student_id": student_id},
        {"$set": {"leaderboard_opted_in": opted_in}},
        upsert=True,
    )


async def record_xp(
    student_id: str,
    xp_delta: int,
    now: Optional[datetime] = None,
) -> None:
    """
    Add XP to this week's leaderboard entry.
    Only records if student has opted in.
    """
    if not await is_opted_in(student_id):
        return

    now = now or datetime.now(timezone.utc)
    week = _week_key(now)
    col = _get_collection()

    existing = await col.find_one({
        "student_id": student_id,
        "week": week,
    })

    if existing:
        await col.update_one(
            {"student_id": student_id, "week": week},
            {
                "$inc": {"weekly_xp": xp_delta},
                "$set": {"updated_at": now},
            },
        )
    else:
        await col.insert_one({
            "student_id": student_id,
            "week": week,
            "weekly_xp": xp_delta,
            "display_name": _anonymize(student_id),
            "created_at": now,
            "updated_at": now,
        })


async def get_leaderboard(
    top_n: int = 20,
    now: Optional[datetime] = None,
) -> dict:
    """
    Get this week's leaderboard.
    Returns ranked entries with anonymized names.
    """
    now = now or datetime.now(timezone.utc)
    week = _week_key(now)
    col = _get_collection()

    cursor = col.find(
        {"week": week},
    ).sort("weekly_xp", -1).limit(top_n)

    entries = await cursor.to_list(length=top_n)

    ranked = []
    for i, entry in enumerate(entries, 1):
        ranked.append({
            "rank": i,
            "display_name": entry.get("display_name", "Anonymous"),
            "weekly_xp": entry.get("weekly_xp", 0),
        })

    return {
        "week": week,
        "entries": ranked,
        "total_participants": await col.count_documents({"week": week}),
    }


async def get_my_rank(
    student_id: str,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """
    Get the current student's rank on this week's leaderboard.
    Returns None if not opted in or no activity.
    """
    now = now or datetime.now(timezone.utc)
    week = _week_key(now)
    col = _get_collection()

    my_entry = await col.find_one({
        "student_id": student_id,
        "week": week,
    })

    if not my_entry:
        return None

    my_xp = my_entry.get("weekly_xp", 0)

    # Count how many have more XP (rank = count_above + 1)
    above = await col.count_documents({
        "week": week,
        "weekly_xp": {"$gt": my_xp},
    })

    total = await col.count_documents({"week": week})

    return {
        "rank": above + 1,
        "total": total,
        "weekly_xp": my_xp,
        "display_name": my_entry.get("display_name", "Anonymous"),
        "percentile": round((1 - above / max(total, 1)) * 100, 1),
    }
