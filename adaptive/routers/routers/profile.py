"""
Profile — student preferences, profile, and feature-flag surface.
Extracted from serve.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Body

from dependencies import get_current_user
from config.features import (
    GAMIFICATION_ENABLED, QUESTS_ENABLED, GUARDIAN_ENABLED,
    CERTIFICATES_ENABLED, VOICE_ENABLED, LEADERBOARD_ENABLED,
)
from api.schemas import StudentPreferences
from database import student_states_collection, users_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile"])


# ── Extracted preferences / profile / features routes (verbatim from serve.py) ──
@router.get("/me/preferences", response_model=StudentPreferences)
async def get_preferences(current_user: dict = Depends(get_current_user)):
    """Get student's language, reading level, and accessibility preferences."""
    user = await users_collection.find_one({"username": current_user["username"]})
    prefs = user.get("preferences", {}) if user else {}
    return StudentPreferences(**prefs)


@router.put("/me/preferences", response_model=StudentPreferences)
async def update_preferences(prefs: StudentPreferences, current_user: dict = Depends(get_current_user)):
    """Update student's preferences. Persisted in user doc."""
    await users_collection.update_one(
        {"username": current_user["username"]},
        {"$set": {"preferences": prefs.model_dump()}},
    )
    return prefs


@router.get("/me/profile")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Account profile + a headline stats snapshot."""
    username = current_user["username"]
    state = await student_states_collection.find_one(
        {"student_id": username}, {"_id": 0}
    )
    total = state.get("total_questions", 0) if state else 0
    correct = state.get("correct_answers", 0) if state else 0
    accuracy = round((correct / total * 100) if total > 0 else 0, 1)
    topics_count = len(state.get("topic_proficiency", {})) if state else 0

    gam = {}
    try:
        if state:
            from core.gamification import get_gamification
            gam = get_gamification(state)
    except Exception:
        gam = {}

    return {
        "username": username,
        "role": current_user.get("role", "student"),
        "display_name": current_user.get("display_name") or username,
        "goal": current_user.get("goal") or current_user.get("learning_goal") or "",
        "interests": current_user.get("interests", []) or [],
        "age_band": current_user.get("age_band", ""),
        "onboarded": bool(current_user.get("onboarded", False)),
        "total_questions": total,
        "accuracy": accuracy,
        "topics_count": topics_count,
        "level": gam.get("level", 1),
        "xp": gam.get("xp", 0),
        "streak": (gam.get("streak") or {}).get("current", 0) if isinstance(gam.get("streak"), dict) else 0,
    }


@router.put("/me/profile")
async def update_my_profile(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Edit display name, learning goal, and interests."""
    updates = {}
    if "display_name" in body:
        dn = (body.get("display_name") or "").strip()
        if not dn:
            raise HTTPException(400, "Display name can't be empty")
        if len(dn) > 40:
            raise HTTPException(400, "Display name too long (max 40 characters)")
        updates["display_name"] = dn
    if "goal" in body:
        updates["goal"] = (body.get("goal") or "").strip()[:200]
    if "interests" in body and isinstance(body["interests"], list):
        updates["interests"] = [str(x).strip()[:40] for x in body["interests"][:12] if str(x).strip()]
    if not updates:
        raise HTTPException(400, "Nothing to update")
    await users_collection.update_one(
        {"username": current_user["username"]}, {"$set": updates}
    )
    return {"ok": True, **updates}


@router.get("/me/features")
async def get_feature_flags(current_user: dict = Depends(get_current_user)):
    """Return active feature flags so frontend can gate UI."""
    # Voice (TTS/STT) is enabled globally by the flag OR for non-minors. Minors
    # stay gated off (COPPA biometric-data caution) unless the global flag is on.
    voice_on = VOICE_ENABLED or (not current_user.get("is_minor", False))
    return {
        "voice_enabled": voice_on,
        "gamification_enabled": GAMIFICATION_ENABLED,
        "quests_enabled": QUESTS_ENABLED,
        "guardian_enabled": GUARDIAN_ENABLED,
        "certificates_enabled": CERTIFICATES_ENABLED,
        "leaderboard_enabled": LEADERBOARD_ENABLED,
    }
