"""
Gamification — XP/streaks, daily goals, quests, leaderboard, reminders, retention.
Extracted from serve.py.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Body

from dependencies import get_current_user, require_self_or_guardian
from runtime import _require_feature
from config.features import GAMIFICATION_ENABLED, LEADERBOARD_ENABLED, QUESTS_ENABLED
from api.schemas import (
    DailyGoal, GamificationResponse, LeaderboardEntry, LeaderboardResponse,
    QuestsResponse, ReminderPrefsResponse, RetentionResponse, StreakInfo,
)
from database import student_states_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gamification"])


# ── Extracted gamification routes (verbatim from serve.py) ──
@router.get("/gamification/{student_id}", response_model=GamificationResponse)
async def gamification_legacy(student_id: str, current_user: dict = Depends(require_self_or_guardian("student_id"))):
    """Legacy endpoint -- redirects to /me/gamification logic."""
    _require_feature(GAMIFICATION_ENABLED, "gamification")
    import re
    from core.gamification import get_gamification
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if not state:
        return GamificationResponse(
            xp=0, level=1, xp_in_level=0, xp_for_next_level=100,
            streak=StreakInfo(), daily_goal=DailyGoal(), badges=[], new_badges=[],
        )

    result = get_gamification(state)

    # Persist newly earned badges
    if result.get("new_badges"):
        await student_states_collection.update_one(
            {"student_id": student_id},
            {"$set": {"badges": result["badges"]}},
        )

    return result


@router.get("/me/gamification", response_model=GamificationResponse)
async def get_my_gamification(current_user: dict = Depends(get_current_user)):
    """Full gamification state: XP, level, streak, daily goal, badges."""
    _require_feature(GAMIFICATION_ENABLED, "gamification")
    from core.gamification import get_gamification
    student_id = current_user["username"]

    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if not state:
        return GamificationResponse(
            xp=0, level=1, xp_in_level=0, xp_for_next_level=100,
            streak=StreakInfo(), daily_goal=DailyGoal(), badges=[], new_badges=[],
        )

    result = get_gamification(state)

    # Persist newly earned badges
    if result.get("new_badges"):
        await student_states_collection.update_one(
            {"student_id": student_id},
            {"$set": {"badges": result["badges"]}},
        )

    return result


@router.put("/me/gamification/daily-goal")
async def update_daily_goal_targets(
    targets: dict,
    current_user: dict = Depends(get_current_user),
):
    """Let user customize daily goal targets."""
    _require_feature(GAMIFICATION_ENABLED, "gamification")
    answers_target = max(1, min(targets.get("answers_target", 5), 50))
    reviews_target = max(0, min(targets.get("reviews_target", 3), 30))
    await student_states_collection.update_one(
        {"student_id": current_user["username"]},
        {"$set": {"daily_goal_targets": {
            "answers_target": answers_target,
            "reviews_target": reviews_target,
        }}},
        upsert=True,
    )
    return {"answers_target": answers_target, "reviews_target": reviews_target}


@router.put("/me/gamification/reminders")
async def update_reminder_settings(
    settings: dict,
    current_user: dict = Depends(get_current_user),
):
    """Toggle opt-in daily reminders."""
    _require_feature(GAMIFICATION_ENABLED, "gamification")
    from database import users_collection
    enabled = bool(settings.get("enabled", False))
    time_str = settings.get("time", "09:00")
    await users_collection.update_one(
        {"username": current_user["username"]},
        {"$set": {"preferences.daily_reminder": enabled, "preferences.reminder_time": time_str}},
    )
    return {"enabled": enabled, "time": time_str}


@router.get("/me/quests", response_model=QuestsResponse)
async def get_my_quests(current_user: dict = Depends(get_current_user)):
    """Get today's daily quests, generated from student's weak areas."""
    _require_feature(QUESTS_ENABLED, "quests")
    from core.daily_quests import generate_daily_quests, check_quest_progress, get_today_stats
    from database import daily_quests_collection

    student_id = current_user["username"]
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Check if quests already generated for today
    cached = await daily_quests_collection.find_one(
        {"student_id": student_id, "date": today}, {"_id": 0}
    )

    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    ) or {}

    if cached and cached.get("quests"):
        quests = cached["quests"]
    else:
        # Generate new quests for today
        quests = generate_daily_quests(student_id, state, now)
        await daily_quests_collection.update_one(
            {"student_id": student_id, "date": today},
            {"$set": {"student_id": student_id, "date": today, "quests": quests}},
            upsert=True,
        )

    # Update progress from today's activity
    today_stats = get_today_stats(state)
    for q in quests:
        if not q.get("completed"):
            check_quest_progress(q, state, today_stats)

    # Persist updated progress
    await daily_quests_collection.update_one(
        {"student_id": student_id, "date": today},
        {"$set": {"quests": quests}},
    )

    return QuestsResponse(quests=quests, date=today)


@router.post("/me/quests/{quest_id}/complete")
async def complete_quest(
    quest_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Mark a quest as complete and award bonus XP."""
    _require_feature(QUESTS_ENABLED, "quests")
    from database import daily_quests_collection

    student_id = current_user["username"]
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    doc = await daily_quests_collection.find_one(
        {"student_id": student_id, "date": today}
    )
    if not doc:
        raise HTTPException(404, "No quests found for today")

    quests = doc.get("quests", [])
    target_quest = None
    for q in quests:
        if q["quest_id"] == quest_id:
            target_quest = q
            break

    if not target_quest:
        raise HTTPException(404, "Quest not found")

    if target_quest.get("completed"):
        return {"message": "Quest already completed", "xp_awarded": 0}

    # Verify progress meets target
    if target_quest.get("progress", 0) < target_quest.get("target", 1):
        raise HTTPException(400, "Quest target not yet reached")

    # Mark complete
    target_quest["completed"] = True
    xp_reward = target_quest.get("xp_reward", 0)

    await daily_quests_collection.update_one(
        {"student_id": student_id, "date": today},
        {"$set": {"quests": quests}},
    )

    # Award bonus XP
    await student_states_collection.update_one(
        {"student_id": student_id},
        {"$inc": {"bonus_xp": xp_reward, "quests_completed": 1}},
        upsert=True,
    )

    return {
        "message": f"Quest complete! +{xp_reward} XP",
        "xp_awarded": xp_reward,
        "quest_id": quest_id,
    }


@router.get("/me/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard_view(current_user: dict = Depends(get_current_user)):
    """Get this week's leaderboard + current user's rank."""
    _require_feature(LEADERBOARD_ENABLED, "leaderboard")
    from core.leaderboard import get_leaderboard, get_my_rank

    student_id = current_user["username"]
    board = await get_leaderboard(top_n=20)
    my_rank = await get_my_rank(student_id)

    return LeaderboardResponse(
        week=board["week"],
        entries=[LeaderboardEntry(**e) for e in board["entries"]],
        total_participants=board["total_participants"],
        my_rank=my_rank,
    )


@router.put("/me/leaderboard/opt-in")
async def leaderboard_opt_in(
    opted_in: bool = Body(..., embed=True),
    current_user: dict = Depends(get_current_user),
):
    """Opt in or out of the weekly leaderboard."""
    _require_feature(LEADERBOARD_ENABLED, "leaderboard")
    from core.leaderboard import set_opt_in

    student_id = current_user["username"]
    await set_opt_in(student_id, opted_in)
    return {"opted_in": opted_in}


@router.get("/me/reminders")
async def get_reminders(current_user: dict = Depends(get_current_user)):
    """Get pending (unread) reminders for the current user."""
    from core.reminder_engine import get_pending_reminders
    student_id = current_user["username"]
    reminders = await get_pending_reminders(student_id)
    return {"reminders": reminders}


@router.post("/me/reminders/read-all")
async def mark_all_reminders_read(current_user: dict = Depends(get_current_user)):
    """Mark all reminders as read."""
    from core.reminder_engine import mark_all_read
    student_id = current_user["username"]
    count = await mark_all_read(student_id)
    return {"marked_read": count}


@router.get("/me/reminder-prefs", response_model=ReminderPrefsResponse)
async def get_reminder_prefs(current_user: dict = Depends(get_current_user)):
    """Get reminder preferences."""
    from core.reminder_engine import get_prefs
    student_id = current_user["username"]
    prefs = await get_prefs(student_id)
    return ReminderPrefsResponse(**prefs)


@router.put("/me/reminder-prefs", response_model=ReminderPrefsResponse)
async def update_reminder_prefs(
    prefs: ReminderPrefsResponse,
    current_user: dict = Depends(get_current_user),
):
    """Update reminder preferences."""
    from core.reminder_engine import update_prefs
    student_id = current_user["username"]
    updated = await update_prefs(student_id, prefs.model_dump())
    return ReminderPrefsResponse(**updated)


@router.get("/me/retention", response_model=RetentionResponse)
async def get_my_retention(current_user: dict = Depends(get_current_user)):
    """Get retention data for the current user."""
    from core.retention_tracker import get_retention
    student_id = current_user["username"]
    data = await get_retention(student_id)
    if not data:
        return RetentionResponse(student_id=student_id)
    return RetentionResponse(
        student_id=student_id,
        first_seen=data.get("first_seen", "").isoformat() if hasattr(data.get("first_seen", ""), "isoformat") else str(data.get("first_seen", "")),
        total_active_days=data.get("total_active_days", 0),
        day_1_returned=data.get("day_1_returned", False),
        day_7_returned=data.get("day_7_returned", False),
    )


@router.get("/retention-summary")
async def retention_summary(current_user: str = Depends(get_current_user)):
    """Aggregate retention metrics across all users (admin view)."""
    from core.retention_tracker import get_retention_summary
    return await get_retention_summary()
