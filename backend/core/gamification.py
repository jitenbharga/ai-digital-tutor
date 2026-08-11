"""
Core Gamification Engine — Streaks, XP, levels, badges, and activity processing.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List

MAX_STREAK_FREEZES = 1
XP_PER_LEVEL = 100

BADGES = [
    {"id": "first_step", "name": "First Step", "description": "Completed your first learning activity", "icon": "🚀"},
    {"id": "streak_3", "name": "On Fire", "description": "Maintained a 3-day learning streak", "icon": "🔥"},
    {"id": "streak_7", "name": "Unstoppable", "description": "Maintained a 7-day learning streak", "icon": "⚡"},
    {"id": "quiz_master", "name": "Quiz Master", "description": "Scored 100% on a quiz", "icon": "🎯"},
    {"id": "night_owl", "name": "Night Owl", "description": "Studied late at night", "icon": "🌙"},
]


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def compute_streak(state: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate current streak status based on last active date and freeze logic."""
    if now is None:
        now = datetime.now(timezone.utc)

    today = now.date()
    streak = state.get("streak", 0)
    last_active_str = state.get("last_active_date")
    freezes_used = state.get("streak_freezes_used_this_week", 0)

    if not last_active_str:
        return {
            "streak_alive": False,
            "streak": 0,
            "streak_freezes_used_this_week": 0,
            "last_active_date": None,
        }

    try:
        last_active_date = datetime.strptime(last_active_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {
            "streak_alive": False,
            "streak": 0,
            "streak_freezes_used_this_week": 0,
            "last_active_date": None,
        }

    days_diff = (today - last_active_date).days

    if days_diff <= 1:
        # Active today or yesterday
        return {
            "streak_alive": True,
            "streak": streak,
            "streak_freezes_used_this_week": freezes_used,
            "last_active_date": last_active_str,
        }

    # Gap of > 1 day: check if freeze can save streak
    if freezes_used < MAX_STREAK_FREEZES:
        return {
            "streak_alive": True,
            "streak": streak,
            "streak_freezes_used_this_week": freezes_used + 1,
            "last_active_date": last_active_str,
            "freeze_used": True,
        }

    # Freezes exhausted -> streak breaks
    return {
        "streak_alive": False,
        "streak": 0,
        "streak_freezes_used_this_week": freezes_used,
        "last_active_date": last_active_str,
    }


def advance_streak(state: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Advance student's streak if active on a new calendar day."""
    if now is None:
        now = datetime.now(timezone.utc)

    today_str = _fmt_date(now)
    last_active_str = state.get("last_active_date")
    streak_info = compute_streak(state, now)
    current_streak = streak_info["streak"]

    if last_active_str == today_str:
        # Already active today -> do not double count
        return {
            **state,
            "streak": current_streak,
            "last_active_date": today_str,
            "streak_alive": True,
        }

    # New day activity
    new_streak = current_streak + 1 if streak_info["streak_alive"] or not last_active_str else 1
    freezes_used = streak_info.get("streak_freezes_used_this_week", 0)

    res = dict(state)
    res["streak"] = new_streak
    res["last_active_date"] = today_str
    res["streak_alive"] = True
    res["streak_freezes_used_this_week"] = freezes_used
    return res


def calculate_level(xp: int) -> Dict[str, int]:
    """Calculate current level, XP in level, and XP needed for next level."""
    level = math.floor(xp / XP_PER_LEVEL) + 1
    xp_in_level = xp % XP_PER_LEVEL
    xp_for_next_level = XP_PER_LEVEL
    return {
        "level": level,
        "xp_in_level": xp_in_level,
        "xp_for_next_level": xp_for_next_level,
    }


def get_gamification(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return full gamification payload for a student state."""
    xp = state.get("xp", 0)
    level_info = calculate_level(xp)
    streak_info = compute_streak(state)

    badges = state.get("badges", [])
    daily_goal = state.get("daily_goal", {"target_minutes": 15, "progress_minutes": 0, "completed": False})

    return {
        "xp": xp,
        "level": level_info["level"],
        "xp_in_level": level_info["xp_in_level"],
        "xp_for_next_level": level_info["xp_for_next_level"],
        "streak": {
            "current_streak": streak_info["streak"],
            "streak_alive": streak_info["streak_alive"],
            "last_active_date": streak_info.get("last_active_date"),
        },
        "daily_goal": daily_goal,
        "badges": badges,
        "new_badges": [],
    }


def process_activity(state: Dict[str, Any], activity_type: str = "answer", now: Optional[datetime] = None) -> Dict[str, Any]:
    """Process a completed learning activity, award XP, and update streak."""
    if now is None:
        now = datetime.now(timezone.utc)

    xp_gains = {"answer": 10, "quiz": 50, "review": 20, "feynman": 30}
    xp_earned = xp_gains.get(activity_type, 10)

    updated_state = advance_streak(state, now)
    updated_state["xp"] = updated_state.get("xp", 0) + xp_earned

    return updated_state
