"""
P5.2 — Reminder Engine

Generates reminder notifications for:
  - Streak at risk (didn't practice today, streak > 0)
  - Daily goal incomplete (partial progress, hours left in day)
  - Welcome back (inactive 2+ days, no streak)
  - Weekly summary (end of week, XP/mastery highlights)

This is a **notification stub** — it produces reminder payloads but doesn't
deliver them (no email/push infra yet). Consumers: a polling endpoint,
a scheduled cron job, or a future push service.

Reminder preferences stored per-student in `reminder_prefs` collection.
Pending reminders stored in `reminders` collection.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("reminder_engine")

_prefs_col = None
_reminders_col = None


def _get_collections():
    global _prefs_col, _reminders_col
    if _prefs_col is None:
        from database import db
        _prefs_col = db["reminder_prefs"]
        _reminders_col = db["reminders"]
    return _prefs_col, _reminders_col


# ── Default preferences ──

DEFAULT_PREFS = {
    "streak_reminder": True,
    "daily_goal_reminder": True,
    "welcome_back": True,
    "weekly_summary": True,
    "quiet_hours_start": 22,  # 10 PM
    "quiet_hours_end": 8,     # 8 AM
    "timezone_offset": 0,     # UTC offset in hours
}

# ── Reminder types ──

REMINDER_STREAK_AT_RISK = "streak_at_risk"
REMINDER_DAILY_GOAL = "daily_goal_incomplete"
REMINDER_WELCOME_BACK = "welcome_back"
REMINDER_WEEKLY_SUMMARY = "weekly_summary"


async def get_prefs(student_id: str) -> dict:
    """Get reminder preferences, falling back to defaults."""
    prefs_col, _ = _get_collections()
    doc = await prefs_col.find_one({"student_id": student_id})
    if doc:
        doc.pop("_id", None)
        doc.pop("student_id", None)
        return {**DEFAULT_PREFS, **doc}
    return {**DEFAULT_PREFS}


async def update_prefs(student_id: str, updates: dict) -> dict:
    """Update reminder preferences for a student."""
    prefs_col, _ = _get_collections()

    # Only allow known preference keys
    allowed = set(DEFAULT_PREFS.keys())
    clean = {k: v for k, v in updates.items() if k in allowed}

    await prefs_col.update_one(
        {"student_id": student_id},
        {"$set": {**clean, "student_id": student_id}},
        upsert=True,
    )
    return await get_prefs(student_id)


async def generate_reminders(student_id: str, state: dict) -> list[dict]:
    """
    Check student state and generate any pending reminders.
    Does NOT send — just creates reminder docs for later delivery.

    Args:
        student_id: The student
        state: Current student state dict (from student_states collection)

    Returns:
        List of reminder dicts generated this call
    """
    prefs = await get_prefs(student_id)
    _, reminders_col = _get_collections()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    generated = []

    # Check quiet hours
    hour = (now.hour + prefs.get("timezone_offset", 0)) % 24
    q_start = prefs.get("quiet_hours_start", 22)
    q_end = prefs.get("quiet_hours_end", 8)
    if q_start > q_end:  # wraps midnight
        in_quiet = hour >= q_start or hour < q_end
    else:
        in_quiet = q_start <= hour < q_end
    if in_quiet:
        return []

    # Don't duplicate — check what was already sent today
    existing = await reminders_col.find(
        {"student_id": student_id, "date": today}
    ).to_list(length=100)
    sent_types = {r["type"] for r in existing}

    # 1. Streak at risk
    if (
        prefs.get("streak_reminder")
        and REMINDER_STREAK_AT_RISK not in sent_types
    ):
        streak = state.get("streak", 0)
        last_active = state.get("last_active_date", "")
        if streak > 0 and last_active != today:
            reminder = _build_reminder(
                student_id, REMINDER_STREAK_AT_RISK, today,
                title="Your streak is at risk!",
                body=f"You have a {streak}-day streak. Practice today to keep it alive!",
                priority="high",
            )
            await reminders_col.insert_one(reminder)
            generated.append(reminder)

    # 2. Daily goal incomplete
    if (
        prefs.get("daily_goal_reminder")
        and REMINDER_DAILY_GOAL not in sent_types
    ):
        daily = state.get("daily_progress", {})
        if daily.get("date") == today and not daily.get("completed"):
            answers_done = daily.get("answers_done", 0)
            answers_target = state.get("daily_goal_targets", {}).get("answers_target", 5)
            if answers_done > 0 and answers_done < answers_target:
                remaining = answers_target - answers_done
                reminder = _build_reminder(
                    student_id, REMINDER_DAILY_GOAL, today,
                    title="Almost there!",
                    body=f"Just {remaining} more answer{'s' if remaining > 1 else ''} to hit your daily goal.",
                    priority="medium",
                )
                await reminders_col.insert_one(reminder)
                generated.append(reminder)

    # 3. Welcome back
    if (
        prefs.get("welcome_back")
        and REMINDER_WELCOME_BACK not in sent_types
    ):
        last_active = state.get("last_active_date", "")
        if last_active:
            try:
                last_dt = datetime.strptime(last_active, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                days_away = (now - last_dt).days
                if days_away >= 2:
                    reminder = _build_reminder(
                        student_id, REMINDER_WELCOME_BACK, today,
                        title="We miss you!",
                        body=f"It's been {days_away} days. Jump back in — even 5 minutes helps.",
                        priority="low",
                    )
                    await reminders_col.insert_one(reminder)
                    generated.append(reminder)
            except (ValueError, TypeError):
                pass

    return generated


async def get_pending_reminders(student_id: str) -> list[dict]:
    """Get all unread reminders for a student."""
    _, reminders_col = _get_collections()
    cursor = reminders_col.find(
        {"student_id": student_id, "read": False},
    ).sort("created_at", -1).limit(20)
    docs = await cursor.to_list(length=20)
    for d in docs:
        d.pop("_id", None)
    return docs


async def mark_reminder_read(student_id: str, reminder_id: str) -> bool:
    """Mark a reminder as read."""
    _, reminders_col = _get_collections()
    result = await reminders_col.update_one(
        {"student_id": student_id, "reminder_id": reminder_id},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def mark_all_read(student_id: str) -> int:
    """Mark all reminders as read."""
    _, reminders_col = _get_collections()
    result = await reminders_col.update_many(
        {"student_id": student_id, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count


def _build_reminder(
    student_id: str,
    reminder_type: str,
    date: str,
    title: str,
    body: str,
    priority: str = "medium",
) -> dict:
    """Build a reminder document."""
    import uuid

    return {
        "reminder_id": uuid.uuid4().hex[:12],
        "student_id": student_id,
        "type": reminder_type,
        "date": date,
        "title": title,
        "body": body,
        "priority": priority,
        "read": False,
        "created_at": datetime.now(timezone.utc),
    }
