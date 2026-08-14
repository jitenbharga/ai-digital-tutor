"""
Guardian — parent/guardian access + weekly progress digest.
Extracted from serve.py (invite / redeem / children / child overview) and
api/extras.py (the /guardian/digest/* routes + their content helpers).

The digest content is built here; the email itself is sent from the BROWSER
via EmailJS (the app's only email service — there is no backend mailer).
"""

import time
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Body, Request

from adaptive.dependencies import require_role
from adaptive.rate_limit import limiter, user_key
from adaptive.runtime import tutor, graph_engine, _require_feature
from adaptive.config.features import GUARDIAN_ENABLED
from adaptive.api.schemas import (
    GuardianChildOverview, GuardianChildrenResponse, GuardianRedeemRequest,
)
from adaptive.database import (
    student_states_collection, mistakes_collection,
    quiz_history_collection,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["guardian"])


# ── Guardian access: invite / redeem / children / child overview ──────
@router.post("/me/guardian-invite")
async def generate_guardian_invite(
    current_user: dict = Depends(require_role("student")),
):
    """Student generates a short-lived invite code for a guardian."""
    _require_feature(GUARDIAN_ENABLED, "guardian")
    import secrets
    from database import guardian_invites_collection

    code = secrets.token_urlsafe(16)
    await guardian_invites_collection.insert_one({
        "code": code,
        "student": current_user["username"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "redeemed_by": None,
    })
    return {"code": code, "expires_in": "24 hours"}


@router.post("/guardian/redeem-invite")
async def guardian_redeem_invite(
    payload: GuardianRedeemRequest,
    current_user: dict = Depends(require_role("guardian")),
):
    """Guardian redeems an invite code to gain read-only access to a student."""
    _require_feature(GUARDIAN_ENABLED, "guardian")
    from database import users_collection, guardian_invites_collection

    invite = await guardian_invites_collection.find_one({
        "code": payload.code,
        "redeemed_by": None,
    })
    if not invite:
        raise HTTPException(404, "Invalid or already-used invite code")

    # Mongo returns naive UTC datetimes (pymongo tz_aware defaults off); coerce
    # to aware before comparing, else a naive/aware compare raises 500.
    _expires = invite["expires_at"]
    if _expires.tzinfo is None:
        _expires = _expires.replace(tzinfo=timezone.utc)
    if _expires < datetime.now(timezone.utc):
        raise HTTPException(410, "Invite code has expired")

    student_username = invite["student"]

    # Check not already linked
    linked = current_user.get("linked_children", [])
    if student_username in linked:
        raise HTTPException(400, "Already linked to this student")

    # Mark invite redeemed
    await guardian_invites_collection.update_one(
        {"_id": invite["_id"]},
        {"$set": {"redeemed_by": current_user["username"]}},
    )

    # Add student to guardian's linked_children
    await users_collection.update_one(
        {"username": current_user["username"]},
        {"$addToSet": {"linked_children": student_username}},
    )

    return {"message": f"You now have read-only access to {student_username}"}


@router.get("/guardian/children", response_model=GuardianChildrenResponse)
async def guardian_children(current_user: dict = Depends(require_role("guardian"))):
    """List children linked to this guardian."""
    _require_feature(GUARDIAN_ENABLED, "guardian")
    linked = current_user.get("linked_children", [])

    # PERF: fetch all children's states in ONE query ($in) instead of N
    # sequential round-trips (was an N+1 that scaled linearly with children).
    states_by_id = {}
    if linked:
        async for state in student_states_collection.find(
            {"student_id": {"$in": linked}}, {"_id": 0}
        ):
            states_by_id[state.get("student_id")] = state

    children = []
    for sid in linked:
        state = states_by_id.get(sid)
        total = state.get("total_questions", 0) if state else 0
        correct = state.get("correct_answers", 0) if state else 0
        accuracy = round((correct / total * 100) if total > 0 else 0, 2)
        topics_count = len(state.get("topic_proficiency", {})) if state else 0
        last_active = state.get("last_active") if state else None

        children.append({
            "student_id": sid,
            "total_questions": total,
            "accuracy": accuracy,
            "topics_count": topics_count,
            "last_active": str(last_active) if last_active else None,
        })

    return {"children": children}


@router.get("/guardian/child/{student_id}/overview", response_model=GuardianChildOverview)
async def guardian_child_overview(
    student_id: str,
    current_user: dict = Depends(require_role("guardian")),
):
    """View a child's progress (read-only). Guardian must have been invited by this student."""
    _require_feature(GUARDIAN_ENABLED, "guardian")
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    linked = current_user.get("linked_children", [])
    if student_id not in linked:
        raise HTTPException(403, "This student has not invited you")

    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    total = state.get("total_questions", 0) if state else 0
    correct = state.get("correct_answers", 0) if state else 0
    accuracy = round((correct / total * 100) if total > 0 else 0, 2)
    progress_data = {
        "student_id": student_id,
        "topics": state.get("topic_proficiency", {}) if state else {},
        "total_questions": total,
        "accuracy": accuracy,
    }

    kg_data = None
    try:
        student = await tutor.sessions.get_student(student_id)
        if student and student.concepts:
            topics_with_mastery = [
                {"topic": t, "mastery": round(c.knowledge, 2)}
                for t, c in student.concepts.items()
            ]
            if topics_with_mastery:
                result = await graph_engine.generate_graph(topics_with_mastery)
                edges = []
                for e in result.get("edges", []):
                    edges.append({
                        "source": e.get("from", e.get("source", "")),
                        "target": e.get("to", e.get("target", "")),
                        "strength": e.get("strength", "weak"),
                        "reason": e.get("reason", ""),
                    })
                kg_data = {
                    "nodes": result.get("nodes", topics_with_mastery),
                    "edges": edges,
                    "weak_links": result.get("weak_links", []),
                    "suggested_focus": result.get("suggested_focus", ""),
                }
    except Exception:
        pass

    return {
        "student_id": student_id,
        "progress": progress_data,
        "knowledge_graph": kg_data,
    }


# ── Guardian weekly digest: send helpers + /guardian/digest/* routes ──
async def _child_week_summary(child_id: str) -> dict:
    """Last-7-days activity for one child, from existing collections."""
    week_ago = time.time() - 7 * 86400

    quizzes, score_sum, topics = 0, 0.0, set()
    async for q in quiz_history_collection.find(
        {"student_id": child_id, "taken_at": {"$gte": week_ago}}
    ).limit(100):
        quizzes += 1
        score_sum += q.get("score_pct", 0)
        if q.get("topic"):
            topics.add(q["topic"])

    mistakes_added = await mistakes_collection.count_documents(
        {"student_id": child_id, "timestamp": {"$gte": week_ago}}
    )
    mistakes_resolved = await mistakes_collection.count_documents(
        {"student_id": child_id, "resolved": True, "resolved_at": {"$gte": week_ago}}
    )

    return {
        "child": child_id,
        "quizzes": quizzes,
        "avg_score": round(score_sum / quizzes, 1) if quizzes else None,
        "topics": sorted(topics)[:6],
        "mistakes_added": mistakes_added,
        "mistakes_resolved": mistakes_resolved,
        "active": quizzes > 0 or mistakes_added > 0,
    }


def _digest_html(guardian: str, summaries: list) -> str:
    rows = ""
    for s in summaries:
        topics = ", ".join(s["topics"]) or "—"
        score = f"{s['avg_score']}%" if s["avg_score"] is not None else "—"
        status = "✅ active this week" if s["active"] else "😴 no activity this week"
        rows += f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:12px 0;">
          <h3 style="margin:0 0 4px;color:#111827;">{s['child']} <span style="font-size:12px;font-weight:normal;color:#6b7280;">{status}</span></h3>
          <table style="font-size:14px;color:#374151;border-collapse:collapse;">
            <tr><td style="padding:2px 12px 2px 0;">Quizzes taken</td><td><b>{s['quizzes']}</b></td></tr>
            <tr><td style="padding:2px 12px 2px 0;">Average score</td><td><b>{score}</b></td></tr>
            <tr><td style="padding:2px 12px 2px 0;">Topics studied</td><td><b>{topics}</b></td></tr>
            <tr><td style="padding:2px 12px 2px 0;">Mistakes fixed</td><td><b>{s['mistakes_resolved']}</b> (new: {s['mistakes_added']})</td></tr>
          </table>
        </div>"""
    return f"""
    <div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:560px;margin:auto;">
      <h2 style="color:#4f46e5;">Weekly learning digest</h2>
      <p style="color:#374151;">Hi {guardian}, here's what your learner(s) did this week:</p>
      {rows}
      <p style="font-size:12px;color:#9ca3af;">You get this weekly. Turn it off any time from your Guardian dashboard.</p>
    </div>"""


async def _build_guardian_digest(guardian_doc: dict) -> dict:
    """Build the weekly-digest content (subject + HTML + plain text).

    The email itself is sent by the FRONTEND (EmailJS — the only email service
    in the app). This returns the content; the browser emails it.
    """
    username = guardian_doc["username"]
    children = guardian_doc.get("linked_children") or []
    if not children:
        return {}

    summaries = [await _child_week_summary(c) for c in children]
    html = _digest_html(username, summaries)
    text = "\n".join(
        f"{s['child']}: {s['quizzes']} quizzes, avg {s['avg_score']}%, "
        f"{s['mistakes_resolved']} mistakes fixed" for s in summaries
    )
    return {
        "subject": "Your weekly learning digest",
        "html": html,
        "text": text,
        "recipient_name": username,
    }


@router.post("/guardian/digest/prefs")
async def set_digest_prefs(
    body: dict = Body(...),
    current_user: dict = Depends(require_role("guardian")),
):
    """Set digest email + enabled flag on the guardian's user doc."""
    from database import users_collection
    import re

    email = (body.get("email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Invalid email address")

    await users_collection.update_one(
        {"username": current_user["username"]},
        {"$set": {
            "digest_email": email,
            "digest_enabled": bool(body.get("enabled", True)),
        }},
    )
    return {"ok": True, "email": email, "enabled": bool(body.get("enabled", True))}


@router.get("/guardian/digest/prefs")
@limiter.limit("60/minute", key_func=user_key)
async def get_digest_prefs(
    request: Request,
    current_user: dict = Depends(require_role("guardian")),
):
    from database import users_collection

    doc = await users_collection.find_one({"username": current_user["username"]})
    return {
        "email": (doc or {}).get("digest_email", ""),
        "enabled": (doc or {}).get("digest_enabled", True),
    }


@router.post("/guardian/digest/send-now")
async def send_digest_now(
    current_user: dict = Depends(require_role("guardian")),
):
    """Return this guardian's digest content — the FRONTEND emails it via
    EmailJS (the only email service in the app; there is no backend mailer)."""
    from database import users_collection

    doc = await users_collection.find_one({"username": current_user["username"]})
    if not doc:
        raise HTTPException(404, "Guardian account not found")
    if not doc.get("linked_children"):
        raise HTTPException(400, "No linked children yet — redeem an invite first")

    content = await _build_guardian_digest(doc)
    if not content:
        raise HTTPException(400, "No linked children yet — redeem an invite first")

    from core.emailer import send_email, emailer_configured
    if emailer_configured() and content.get("email"):
        try:
            await send_email(content["email"], content.get("subject", "Weekly Learning Digest"), content.get("html", ""), content.get("text", ""))
        except Exception as e:
            logger.warning("Guardian digest send_email failed: %s", e)

    return {"ok": True, **content}
