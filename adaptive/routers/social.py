"""
Social — study-buddy pairing (invite / redeem / view / unpair).
Extracted from serve.py.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Body

from adaptive.dependencies import require_role
from adaptive.database import users_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["social"])


# ── Extracted study-buddy routes + streak helper (verbatim from serve.py) ──
def _shared_streak(days_a, days_b, today):
    """Consecutive days (ending today, with 1-day grace) where BOTH studied."""
    both = set(days_a) & set(days_b)
    if not both:
        return 0
    start = today if today.isoformat() in both else (today - timedelta(days=1))
    if start.isoformat() not in both:
        return 0
    streak, d = 0, start
    while d.isoformat() in both:
        streak += 1
        d = d - timedelta(days=1)
    return streak


@router.post("/me/buddy/invite")
async def buddy_invite(current_user: dict = Depends(require_role("student"))):
    """Generate a short-lived code to invite a friend as a study buddy."""
    import secrets
    from database import buddy_invites_collection
    if current_user.get("buddy"):
        raise HTTPException(400, "You already have a study buddy — unpair first.")
    code = secrets.token_urlsafe(9)
    await buddy_invites_collection.insert_one({
        "code": code,
        "inviter": current_user["username"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=48),
        "redeemed_by": None,
    })
    return {"code": code, "expires_in": "48 hours"}


@router.post("/me/buddy/redeem")
async def buddy_redeem(
    payload: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Redeem a buddy code — links both students as study buddies (mutual)."""
    from database import buddy_invites_collection
    me = current_user["username"]
    code = (payload.get("code") or "").strip()
    if not code:
        raise HTTPException(400, "code is required")
    if current_user.get("buddy"):
        raise HTTPException(400, "You already have a study buddy.")

    invite = await buddy_invites_collection.find_one({"code": code, "redeemed_by": None})
    if not invite:
        raise HTTPException(404, "Invalid or already-used code")
    # Mongo returns naive UTC datetimes (pymongo tz_aware defaults off); coerce
    # to aware before comparing, else a naive/aware compare raises 500.
    _expires = invite["expires_at"]
    if _expires.tzinfo is None:
        _expires = _expires.replace(tzinfo=timezone.utc)
    if _expires < datetime.now(timezone.utc):
        raise HTTPException(410, "This code has expired")
    inviter = invite["inviter"]
    if inviter == me:
        raise HTTPException(400, "You can't buddy up with yourself.")

    inviter_doc = await users_collection.find_one({"username": inviter})
    if not inviter_doc:
        raise HTTPException(404, "Inviter not found")
    if inviter_doc.get("buddy"):
        raise HTTPException(400, "That friend already has a study buddy.")

    await users_collection.update_one({"username": me}, {"$set": {"buddy": inviter}})
    await users_collection.update_one({"username": inviter}, {"$set": {"buddy": me}})
    await buddy_invites_collection.update_one(
        {"_id": invite["_id"]}, {"$set": {"redeemed_by": me}}
    )
    return {"ok": True, "buddy": inviter}


@router.get("/me/buddy")
async def get_buddy(current_user: dict = Depends(require_role("student"))):
    """Buddy status + shared streak + who studied today."""
    from datetime import date
    from database import retention_collection
    me = current_user["username"]
    buddy = current_user.get("buddy")
    if not buddy:
        return {"has_buddy": False}

    today = date.today()
    today_iso = today.isoformat()
    my_ret = await retention_collection.find_one({"student_id": me}, {"_id": 0, "active_days": 1})
    bd_ret = await retention_collection.find_one({"student_id": buddy}, {"_id": 0, "active_days": 1})
    my_days = (my_ret or {}).get("active_days", []) or []
    bd_days = (bd_ret or {}).get("active_days", []) or []

    return {
        "has_buddy": True,
        "buddy": buddy,
        "shared_streak": _shared_streak(my_days, bd_days, today),
        "you_today": today_iso in my_days,
        "buddy_today": today_iso in bd_days,
        "buddy_last_active": max(bd_days) if bd_days else None,
    }


@router.delete("/me/buddy")
async def remove_buddy(current_user: dict = Depends(require_role("student"))):
    """Unpair from your study buddy (clears both sides)."""
    me = current_user["username"]
    buddy = current_user.get("buddy")
    if not buddy:
        raise HTTPException(400, "You don't have a study buddy.")
    await users_collection.update_one({"username": me}, {"$unset": {"buddy": ""}})
    await users_collection.update_one({"username": buddy}, {"$unset": {"buddy": ""}})
    return {"ok": True}
