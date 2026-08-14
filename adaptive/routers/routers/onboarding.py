"""
Onboarding — placement quiz + profile capture.
Extracted from serve.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Body

from dependencies import require_role
from api.schemas import (
    OnboardingProfile, OnboardingStartResponse,
    OnboardingAnswerRequest, OnboardingAnswerResponse,
    OnboardingCompleteResponse,
)
from database import (
    users_collection, student_states_collection,
    onboarding_sessions_collection, mentor_memory_collection,
)
from core.onboarding import (
    create_session as create_onboarding_session,
    pick_question,
    evaluate_and_adapt,
    compute_mastery_seeds,
)
from core.mentor import save_memory_item
from core.analytics import track_onboarding_start, track_onboarding_complete

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboarding"])


@router.post("/onboarding/start", response_model=OnboardingStartResponse)
async def onboarding_start(
    profile: OnboardingProfile,
    current_user: dict = Depends(require_role("student")),
):
    """Start onboarding: capture profile, return first placement question."""
    # K4: Block under-13 (COPPA compliance)
    if profile.age_band == "under-13":
        raise HTTPException(
            403,
            "This product is currently available for users aged 13 and above. "
            "We cannot serve under-13 users until a COPPA-compliant parental consent flow is in place.",
        )

    student_id = current_user["username"]

    await users_collection.update_one(
        {"username": student_id},
        {"$set": {
            "display_name": profile.display_name,
            "age_band": profile.age_band,
            "interests": profile.interests,
            "goal": profile.goal,
            "onboarded": False,
        }},
    )

    if profile.goal:
        await save_memory_item(
            mentor_memory_collection, student_id,
            fact=f"Goal: {profile.goal}", category="goal",
        )

    try:
        await track_onboarding_start(student_id)
    except Exception:
        pass

    session = create_onboarding_session(student_id, profile.dict())
    question = pick_question(session)
    if not question:
        raise HTTPException(500, "Failed to generate placement question")

    session["current_question"] = question
    await onboarding_sessions_collection.insert_one(session)

    return {
        "session_id": session["session_id"],
        "question": question["question"],
        "options": question.get("options"),
        "topic": question["topic"],
        "question_number": 1,
        "total_questions": len(session["topics_to_assess"]),
    }


@router.post("/onboarding/answer", response_model=OnboardingAnswerResponse)
async def onboarding_answer(
    payload: OnboardingAnswerRequest,
    current_user: dict = Depends(require_role("student")),
):
    """Submit an answer to the current placement question."""
    session = await onboarding_sessions_collection.find_one(
        {"session_id": payload.session_id, "student_id": current_user["username"]},
    )
    if not session:
        raise HTTPException(404, "Onboarding session not found")
    if session.get("completed"):
        raise HTTPException(400, "Onboarding already completed")

    question = session.get("current_question")
    if not question:
        raise HTTPException(400, "No current question")

    correct = evaluate_and_adapt(session, payload.answer, question)

    next_q = pick_question(session)
    done = next_q is None or session["current_index"] >= len(session["topics_to_assess"])

    session["current_question"] = next_q if not done else None

    await onboarding_sessions_collection.update_one(
        {"session_id": payload.session_id},
        {"$set": {
            "results": session["results"],
            "current_index": session["current_index"],
            "current_difficulty": session["current_difficulty"],
            "current_question": session["current_question"],
        }},
    )

    resp = {
        "correct": correct,
        "question_number": session["current_index"] + (0 if done else 1),
        "total_questions": len(session["topics_to_assess"]),
        "done": done,
    }
    if not done and next_q:
        resp["next_question"] = next_q["question"]
        resp["next_options"] = next_q.get("options")
        resp["next_topic"] = next_q["topic"]

    return resp


@router.post("/onboarding/complete", response_model=OnboardingCompleteResponse)
async def onboarding_complete(
    session_id: str = Body(..., embed=True),
    current_user: dict = Depends(require_role("student")),
):
    """Finalize onboarding: seed BKT mastery from placement results."""
    student_id = current_user["username"]
    session = await onboarding_sessions_collection.find_one(
        {"session_id": session_id, "student_id": student_id},
    )
    if not session:
        raise HTTPException(404, "Onboarding session not found")

    mastery_seeds = compute_mastery_seeds(session)

    state_doc = await student_states_collection.find_one({"student_id": student_id})
    if state_doc:
        concepts = state_doc.get("concepts", {})
        for topic, mastery in mastery_seeds.items():
            if topic not in concepts:
                concepts[topic] = {}
            concepts[topic]["knowledge"] = mastery
            concepts[topic]["concept_mastery"] = mastery
        await student_states_collection.update_one(
            {"student_id": student_id},
            {"$set": {"concepts": concepts}},
        )
    else:
        concepts = {}
        for topic, mastery in mastery_seeds.items():
            concepts[topic] = {"knowledge": mastery, "concept_mastery": mastery}
        await student_states_collection.insert_one({
            "student_id": student_id,
            "concepts": concepts,
            "total_questions": 0,
            "correct_answers": 0,
        })

    await onboarding_sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"completed": True}},
    )
    await users_collection.update_one(
        {"username": student_id},
        {"$set": {"onboarded": True}},
    )

    try:
        await track_onboarding_complete(student_id, topics_assessed=len(mastery_seeds))
    except Exception:
        pass

    user = await users_collection.find_one({"username": student_id})
    display_name = (user or {}).get("display_name", student_id)

    return {
        "display_name": display_name,
        "topics_assessed": list(mastery_seeds.keys()),
        "mastery_seeds": mastery_seeds,
        "message": f"Welcome, {display_name}! Your placement is complete.",
    }
