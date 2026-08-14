"""
Tutor — core teaching loop + conversational surfaces.
Extracted from serve.py.

Route groups:
  Teach     /tutor, /submit_answer, /hint
  Ask       /ask, /ask-selection, /explain-again
  Stream    /me/stream-ticket, /tutor/stream
  Chats     /me/chats*, /me/chat/*  (saved conversations)
"""

import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request
from fastapi.responses import StreamingResponse

from adaptive.dependencies import get_current_user, require_role, assert_owns_student
from adaptive.rate_limit import limiter, check_llm_budget
from adaptive.utils.tone import get_tone_directive
from adaptive.utils.language import get_language_directive
from adaptive.runtime import tutor, Hint, _concept_mastery, _is_feature_on_for_user
from adaptive.config.features import GAMIFICATION_ENABLED, QUESTS_ENABLED, CERTIFICATES_ENABLED
from adaptive.core.analytics import track_answer
from adaptive.api.schemas import (
    StudentInput, TutorResponse, AnswerRequest, HintRequest, HintResponse,
)
from adaptive.database import (
    db as _db_sel,
    student_states_collection, users_collection,
    ask_sessions_collection, chat_sessions_collection, mistakes_collection,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tutor"])


# ── Extracted tutor routes + chat helpers (verbatim from serve.py) ──
@router.post("/tutor", response_model=TutorResponse)
async def tutor_api(student: StudentInput, current_user: dict = Depends(get_current_user)):
    # SEC-IDOR: authoritative student_id is the caller's own username, never
    # the client-supplied body value.
    student.student_id = assert_owns_student(current_user, student.student_id)
    result = await tutor.decide(student)
    return result


@router.post("/submit_answer")
async def submit_answer(req: AnswerRequest, current_user: dict = Depends(get_current_user)):
    # SEC-IDOR: bind the action to the authenticated user, ignoring any
    # student_id an attacker might inject to mutate another student's state.
    req.student_id = assert_owns_student(current_user, req.student_id)
    result = await tutor.submit_answer(
        student_id=req.student_id,
        student_answer=req.answer
    )

    # E7: Check for certificate awards after answer (only if enabled or in treatment arm)
    new_cert = None
    _cert_on = await _is_feature_on_for_user(CERTIFICATES_ENABLED, "certificates", req.student_id)
    if _cert_on:
        try:
            from core.certificate_builder import check_and_award_certificates
            student = await tutor.sessions.get_student(req.student_id)
            if student and student.current_topic:
                concept = student.concepts.get(student.current_topic)
                if concept:
                    mastery = _concept_mastery(concept)
                    display_name = req.student_id
                    from database import users_collection
                    user_doc = await users_collection.find_one({"username": req.student_id})
                    if user_doc and user_doc.get("profile", {}).get("display_name"):
                        display_name = user_doc["profile"]["display_name"]

                    cert = await check_and_award_certificates(
                        student_id=req.student_id, topic=student.current_topic,
                        mastery=mastery, display_name=display_name,
                    )
                    if cert:
                        new_cert = {
                            "cert_id": cert["cert_id"],
                            "topic": cert["topic"],
                            "tier": cert["tier"],
                            "mastery": cert["mastery"],
                        }
        except Exception:
            pass

    if new_cert:
        result["new_certificate"] = new_cert

    # E10: Process gamification activity (only if enabled or in treatment arm)
    _gam_on = await _is_feature_on_for_user(GAMIFICATION_ENABLED, "gamification", req.student_id)
    if _gam_on:
        try:
            from core.gamification import process_activity
            state = await student_states_collection.find_one(
                {"student_id": req.student_id}, {"_id": 0}
            )
            if state:
                activity_updates = process_activity(state, "answer")
                celebration_events = activity_updates.pop("_celebration_events", [])
                new_level = activity_updates.pop("_new_level", None)
                new_badges = activity_updates.pop("_new_badges", None)

                # Persist gamification state updates
                persist = {k: v for k, v in activity_updates.items() if not k.startswith("_")}
                if persist:
                    await student_states_collection.update_one(
                        {"student_id": req.student_id},
                        {"$set": persist},
                    )

                # Attach celebrations to response
                if celebration_events:
                    result["celebrations"] = []
                    for evt in celebration_events:
                        ce = {"event": evt}
                        if evt == "level_up" and new_level:
                            ce["new_level"] = new_level
                        if evt == "badge_unlocked" and new_badges:
                            ce["new_badges"] = new_badges
                        result["celebrations"].append(ce)
        except Exception:
            pass

    # E11: Track quest-relevant activity (experiment-aware, consistent with
    # certificates/gamification gating above)
    _quests_on = await _is_feature_on_for_user(QUESTS_ENABLED, "quests", req.student_id)
    if _quests_on:
        try:
            from core.daily_quests import record_quest_activity
            q_state = await student_states_collection.find_one(
                {"student_id": req.student_id}, {"_id": 0}
            ) or {}
            is_correct = result.get("is_correct", result.get("correct", False))
            current_topic = result.get("topic", "")
            current_diff = result.get("difficulty", "medium")
            if isinstance(current_diff, (int, float)):
                current_diff = "hard" if current_diff >= 0.7 else ("medium" if current_diff >= 0.4 else "easy")
            q_updates = record_quest_activity(q_state, "answer", topic=current_topic, difficulty=current_diff, correct=is_correct)
            if q_updates:
                await student_states_collection.update_one(
                    {"student_id": req.student_id},
                    {"$set": q_updates},
                    upsert=True,
                )
        except Exception:
            pass

    # P0.3: Track answer event
    try:
        await track_answer(
            req.student_id,
            topic=result.get("topic", ""),
            correct=result.get("is_correct", result.get("correct", False)),
            difficulty=str(result.get("difficulty", "")),
        )
    except Exception:
        pass

    # P5.1: Track retention on every answer
    try:
        from core.retention_tracker import record_activity
        await record_activity(req.student_id)
    except Exception:
        pass

    # N5: Capture wrong tutor answers as mistakes
    if not result.get("is_correct", result.get("correct", True)):
        try:
            import uuid as _uuid_t
            import time as _time_t
            await mistakes_collection.insert_one({
                "student_id": req.student_id,
                "mistake_id": str(_uuid_t.uuid4())[:12],
                "source": "tutor",
                "topic": result.get("topic", ""),
                "concept": result.get("concept_tested", ""),
                "question": result.get("original_question", ""),
                "user_answer": req.answer,
                "correct_answer": result.get("correct_answer", ""),
                "explanation": result.get("targeted_feedback", result.get("reasoning", "")),
                "timestamp": _time_t.time(),
                "resolved": False,
            })
        except Exception:
            pass

    return result


@router.post("/hint", response_model=HintResponse)
async def get_hint(request: HintRequest, current_user: dict = Depends(get_current_user)):
    if len(request.question) > 1000:
        raise HTTPException(400, "Question too long")

    # SEC-IDOR: hint usage is recorded against the caller, not a body value.
    request.student_id = assert_owns_student(current_user, request.student_id)
    question = request.question.strip()
    hint = await Hint.generate_hint(question)

    await student_states_collection.update_one(
        {"student_id": request.student_id},
        {"$inc": {"hint_used": 1}},
        upsert=True
    )

    return {"hint": hint}


@router.get("/me/stream-ticket")
async def stream_ticket(current_user: dict = Depends(get_current_user)):
    """SEC: mint a short-lived (60s), single-purpose stream token so the
    long-lived access token never appears in an EventSource URL / server logs.
    The client fetches this (with its Authorization header) immediately before
    opening the stream."""
    from security import create_stream_token
    return {"ticket": create_stream_token(current_user["username"])}


@router.get("/tutor/stream")
async def tutor_stream(
    student_id: str = "",
    current_topic: str = "Algebra",
    ticket: str = "",
    token: str = "",
):
    """EventSource can't set headers, so we authenticate via a short-lived
    query-param *stream ticket* (type="stream", ~60s TTL) minted by
    /me/stream-ticket. The access token is never placed in the URL."""
    import jwt
    from jwt import PyJWTError as JWTError
    from database import users_collection

    cred = ticket or token
    if not cred:
        raise HTTPException(401, "Stream ticket required")
    try:
        from auth_config import SECRET_KEY as _sk, ALGORITHM as _alg
        payload = jwt.decode(cred, _sk, algorithms=[_alg])
        username = payload.get("sub")
        if not username:
            raise HTTPException(401, "Invalid ticket")
        # Only a purpose-built stream ticket is accepted here.
        if payload.get("type") != "stream":
            raise HTTPException(401, "Invalid ticket type")
        user = await users_collection.find_one({"username": username})
        if not user:
            raise HTTPException(401, "User not found")
    except JWTError:
        raise HTTPException(401, "Invalid or expired ticket")

    from api.schemas import StudentInput

    # SEC-IDOR: stream only the authenticated user's own session, regardless of
    # the student_id supplied in the query string.
    student_id = username
    student_input = StudentInput(student_id=student_id, current_topic=current_topic)
    result = await tutor.decide(student_input)

    async def event_generator():
        meta = {
            "mode": result.get("mode", "direct_question"),
            "hint_level": result.get("hint_level", 0),
            "difficulty": result.get("difficulty", 0.4),
            "question": result.get("question", ""),
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"

        explanation = result.get("explanation")
        if explanation and isinstance(explanation, dict):
            core = explanation.get("core_concept", "")
            if core:
                yield f"event: explanation\ndata: {json.dumps(explanation)}\n\n"

        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ask")
@limiter.limit("20/minute")
async def ask_anything(
    request: Request,
    req: dict = Body(...),
    current_user: str = Depends(check_llm_budget),
):
    """
    Accept a student's own question (text + optional OCR image text).
    Classify topic, route through Socratic engine with leakage guard.
    """
    from api.schemas import AskRequest
    from core.prompts.ask_anything import build_topic_classifier, build_socratic_help
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from core.leakage_guard import classify_message, get_redirect_response
    from core.retriever import retrieve, format_grounding_context

    body = AskRequest(**req)
    student_id = current_user["username"]
    combined_question = body.question
    if body.image_text:
        combined_question = f"{body.question}\n\n[From image]:\n{body.image_text}"

    if len(combined_question) > 6000:
        raise HTTPException(400, "Question too long (max 6000 chars with image text)")

    # Injection mitigation: log suspicious input; downstream prompts receive
    # the question wrapped as data (see build_socratic_help call below).
    from utils.prompt_safety import wrap_student_text, looks_like_injection
    if looks_like_injection(combined_question):
        logger.warning("possible prompt injection from %s: %.80s", student_id, combined_question)
    safe_question = wrap_student_text(combined_question)

    # Leakage guard
    flagged, category, matched = classify_message(combined_question)
    if flagged:
        redirect = get_redirect_response(category, topic="", mode=1)
        return {
            "response": redirect["redirect_response"],
            "probing_question": "",
            "hint_if_stuck": "",
            "concept_connection": "",
            "topic": "",
            "concept": "",
            "session_id": "",
            "flagged": True,
        }

    models = build_models()

    # Step 1: Classify topic
    classifier_prompt = build_topic_classifier(combined_question)
    classification = await call_llm(
        models, classifier_prompt, required_key="topic",
        engine_name="ask_topic_classifier",
        prompt_version="v1",
    )

    if not classification:
        classification = {
            "subject": "General",
            "topic": "General",
            "concept": combined_question[:100],
            "difficulty_estimate": "medium",
            "is_homework": False,
        }

    topic = classification.get("topic", "General")
    concept = classification.get("concept", topic)
    is_homework = classification.get("is_homework", False)

    # Step 2: Load student + KT mastery
    student = await tutor.sessions.get_student(student_id)
    if student is None:
        student = await tutor.sessions.create_session({"student_id": student_id})

    kt_result = await tutor.kt.predict_mastery(student_id, topic, heuristic_fallback=0.3)
    concept_obj = student.get_current_concept()
    profile = {
        "knowledge": kt_result["p_correct"],
        "mastery": concept_obj.concept_mastery if concept_obj else 0.5,
        "frustration": student.frustration,
        "curiosity": student.curiosity,
        "confidence": student.confidence,
        "retention": student.retention,
    }

    # Build conversation context from ask session
    session_doc = await ask_sessions_collection.find_one(
        {"student_id": student_id, "active": True},
        sort=[("updated_at", -1)],
    )
    conversation_context = ""
    session_id = ""
    if session_doc:
        session_id = session_doc["session_id"]
        turns = session_doc.get("turns", [])[-6:]
        conversation_context = "\n".join(
            f"- {t['role']}: {t['content'][:300]}" for t in turns
        )

    # RAG grounding
    chunks = retrieve(topic, query=combined_question, k=3)
    grounding_context = format_grounding_context(chunks)

    # Directives
    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))
    tone_dir = get_tone_directive(student)
    mentor_dir = await tutor._get_mentor_directive(student_id, student, is_socratic=True)

    # Step 3: Generate Socratic help (question wrapped as data — injection mitigation)
    help_prompt = build_socratic_help(
        user_question=safe_question,
        topic=topic,
        concept=concept,
        student_profile=profile,
        conversation_context=conversation_context,
        tone_directive=tone_dir,
        language_directive=lang_dir,
        mentor_directive=mentor_dir,
        grounding_context=grounding_context,
        is_homework=is_homework,
    )

    result = await call_llm(
        models, help_prompt, required_key="response",
        engine_name="ask_anything",
        prompt_version="v1",
    )

    if not result:
        result = {
            "response": "That's a great question! Let me help you think through it. What do you already know about this topic?",
            "probing_question": "What have you tried so far?",
            "hint_if_stuck": "Think about the basic concept.",
            "concept_connection": "This relates to the topic.",
            "next_step": "",
        }

    # Step 4: Persist conversation in ask session
    import time as _time
    now = _time.time()
    if not session_id:
        session_id = uuid.uuid4().hex[:16]
        await ask_sessions_collection.insert_one({
            "session_id": session_id,
            "student_id": student_id,
            "topic": topic,
            "concept": concept,
            "turns": [
                {"role": "student", "content": combined_question, "timestamp": now},
                {"role": "tutor", "content": result["response"], "timestamp": now},
            ],
            "re_explain_count": 0,
            "active": True,
            "created_at": now,
            "updated_at": now,
        })
    else:
        await ask_sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"turns": {
                    "$each": [
                        {"role": "student", "content": combined_question, "timestamp": now},
                        {"role": "tutor", "content": result["response"], "timestamp": now},
                    ]
                }},
                "$set": {"updated_at": now, "topic": topic, "concept": concept},
            }
        )

    return {
        "response": result.get("response", ""),
        "probing_question": result.get("probing_question", ""),
        "hint_if_stuck": result.get("hint_if_stuck", ""),
        "concept_connection": result.get("concept_connection", ""),
        "topic": topic,
        "concept": concept,
        "session_id": session_id,
    }


_selection_threads = _db_sel["selection_threads"]


@router.post("/ask-selection")
async def ask_selection(
    req: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Answer a question about a specific highlighted span of a tutor message.
    Injects the selected text + surrounding message as context; keeps a
    sub-thread keyed by source_message_id so follow-ups stay scoped.
    """
    from core.prompts.ask_anything import build_socratic_help
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from core.leakage_guard import classify_message, get_redirect_response
    import time as _t

    student_id = current_user["username"]
    selected_text = (req.get("selected_text") or "").strip()
    source_message_id = (req.get("source_message_id") or "").strip()
    source_message = (req.get("source_message") or "").strip()
    question = (req.get("question") or "").strip()
    topic = req.get("topic") or "General"

    if not selected_text:
        raise HTTPException(400, "selected_text is required")
    if len(selected_text) > 3000 or len(source_message) > 8000:
        raise HTTPException(400, "Selection or context too long")

    user_ask = question or "Can you explain this part?"

    # Leakage guard — do not let selection Q&A become an answer dump
    flagged, category, _matched = classify_message(user_ask + " " + selected_text)
    if flagged:
        redirect = get_redirect_response(category, topic=topic, mode=1)
        return {
            "response": redirect["redirect_response"],
            "probing_question": "", "hint_if_stuck": "", "concept_connection": "",
            "source_message_id": source_message_id, "flagged": True,
        }

    # Load existing sub-thread for this source message (scoped follow-ups)
    thread = await _selection_threads.find_one(
        {"student_id": student_id, "source_message_id": source_message_id}
    )
    convo = ""
    if thread:
        turns = thread.get("turns", [])[-6:]
        convo = "\n".join(f"- {t['role']}: {t['content'][:300]}" for t in turns)

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        student = await tutor.sessions.create_session({"student_id": student_id})
    concept_obj = student.get_current_concept()
    profile = {
        "knowledge": concept_obj.knowledge if concept_obj else 0.5,
        "mastery": concept_obj.concept_mastery if concept_obj else 0.5,
        "frustration": student.frustration,
        "curiosity": student.curiosity,
        "confidence": student.confidence,
        "retention": student.retention,
    }

    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))
    tone_dir = get_tone_directive(student)
    mentor_dir = await tutor._get_mentor_directive(student_id, student, is_socratic=True)

    models = build_models()
    combined_question = (
        f'The student highlighted this part of your last message:\n"{selected_text}"\n\n'
        f'Surrounding context:\n{source_message[:2000]}\n\n'
        f'Student asks: {user_ask}'
    )
    help_prompt = build_socratic_help(
        user_question=combined_question,
        topic=topic,
        concept=selected_text[:80],
        student_profile=profile,
        conversation_context=convo,
        tone_directive=tone_dir,
        language_directive=lang_dir,
        mentor_directive=mentor_dir,
        grounding_context="",
        is_homework=False,
    )
    result = await call_llm(
        models, help_prompt, required_key="response",
        engine_name="ask_selection", prompt_version="v1",
    )
    if not result:
        result = {
            "response": "Let's look at that part together — what about it feels unclear?",
            "probing_question": "", "hint_if_stuck": "", "concept_connection": "",
        }

    now = _t.time()
    turn_pair = [
        {"role": "student", "content": user_ask, "timestamp": now},
        {"role": "tutor", "content": result.get("response", ""), "timestamp": now},
    ]
    if thread:
        await _selection_threads.update_one(
            {"_id": thread["_id"]},
            {"$push": {"turns": {"$each": turn_pair}}, "$set": {"updated_at": now}},
        )
    else:
        await _selection_threads.insert_one({
            "student_id": student_id,
            "source_message_id": source_message_id,
            "selected_text": selected_text,
            "topic": topic,
            "turns": turn_pair,
            "created_at": now,
            "updated_at": now,
        })

    return {
        "response": result.get("response", ""),
        "probing_question": result.get("probing_question", ""),
        "hint_if_stuck": result.get("hint_if_stuck", ""),
        "concept_connection": result.get("concept_connection", ""),
        "source_message_id": source_message_id,
    }


@router.post("/explain-again")
@limiter.limit("10/minute")
async def explain_again(
    request: Request,
    req: dict = Body(...),
    current_user: str = Depends(check_llm_budget),
):
    """
    Re-explain the current concept in a different style.
    Styles: simpler, analogy, worked_example, step_by_step.
    """
    from api.schemas import ExplainAgainRequest
    from core.prompts.ask_anything import build_explain_again
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from core.retriever import retrieve, format_grounding_context

    body = ExplainAgainRequest(**req)
    student_id = current_user
    style = body.style

    # Find current context
    topic = ""
    concept = ""
    original_explanation = ""

    if body.session_id:
        session_doc = await ask_sessions_collection.find_one(
            {"session_id": body.session_id, "student_id": student_id}
        )
        if session_doc:
            topic = session_doc.get("topic", "")
            concept = session_doc.get("concept", "")
            for turn in reversed(session_doc.get("turns", [])):
                if turn["role"] == "tutor":
                    original_explanation = turn["content"]
                    break
    else:
        student = await tutor.sessions.get_student(student_id)
        if student:
            topic = student.current_topic or ""
            concept = topic
            for msg in reversed(student.conversation):
                if msg.get("role") == "tutor":
                    original_explanation = msg.get("content", "")
                    break

    # Fallback: use topic from request body (sent by Tutor page)
    if not topic and body.topic:
        topic = body.topic
        concept = topic

    if not topic:
        raise HTTPException(400, "No active topic to re-explain.")

    if not original_explanation:
        original_explanation = "Previous explanation of the topic."

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        student = await tutor.sessions.create_session({"student_id": student_id})

    concept_obj = student.get_current_concept()
    profile = {
        "knowledge": concept_obj.knowledge if concept_obj else 0.5,
        "mastery": concept_obj.concept_mastery if concept_obj else 0.5,
        "frustration": student.frustration,
        "curiosity": student.curiosity,
        "confidence": student.confidence,
        "retention": student.retention,
    }

    chunks = retrieve(topic, query=concept, k=3)
    grounding_context = format_grounding_context(chunks)

    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))
    tone_dir = get_tone_directive(student)
    mentor_dir = await tutor._get_mentor_directive(student_id, student, is_socratic=False)

    models = build_models()

    prompt = build_explain_again(
        topic=topic,
        concept=concept,
        original_explanation=original_explanation[:2000],
        style=style,
        student_profile=profile,
        tone_directive=tone_dir,
        language_directive=lang_dir,
        mentor_directive=mentor_dir,
        grounding_context=grounding_context,
    )

    result = await call_llm(
        models, prompt, required_key="explanation",
        engine_name="explain_again",
        prompt_version="v1",
    )

    if not result:
        result = {
            "explanation": "Let me try explaining this differently...",
            "style_used": style,
            "key_takeaway": "The key idea.",
            "check_understanding": "Does this make more sense?",
        }

    # Track re-explain count
    import time as _time2
    if body.session_id:
        await ask_sessions_collection.update_one(
            {"session_id": body.session_id},
            {
                "$inc": {"re_explain_count": 1},
                "$push": {"turns": {
                    "role": "tutor",
                    "content": result.get("explanation", ""),
                    "timestamp": _time2.time(),
                    "style": style,
                }},
                "$set": {"updated_at": _time2.time()},
            }
        )
    else:
        await student_states_collection.update_one(
            {"student_id": student_id},
            {"$inc": {"re_explain_count_total": 1}},
            upsert=True,
        )

    return {
        "explanation": result.get("explanation", ""),
        "style_used": result.get("style_used", style),
        "key_takeaway": result.get("key_takeaway", ""),
        "check_understanding": result.get("check_understanding", ""),
    }


def _chat_title_from_messages(messages: list, topic: str) -> str:
    """Derive a short title from the first student message, else the topic."""
    for m in messages:
        if m.get("role") == "student" and (m.get("content") or "").strip():
            t = m["content"].strip().replace("\n", " ")
            return (t[:60] + "…") if len(t) > 60 else t
    return topic or "New chat"


def _chat_preview(messages: list) -> str:
    """Last non-empty message as a one-line preview for the sidebar."""
    for m in reversed(messages):
        c = (m.get("content") or "").strip().replace("\n", " ")
        if c:
            return (c[:80] + "…") if len(c) > 80 else c
    return ""


async def _migrate_legacy_chats(student_id: str) -> None:
    """One-time, idempotent: give any legacy per-topic doc (no chat_id) a
    chat_id + title so it shows up as a proper chat in the new model."""
    import uuid as _u
    async for doc in chat_sessions_collection.find(
        {"student_id": student_id, "chat_id": {"$exists": False}}
    ):
        msgs = doc.get("messages", [])
        await chat_sessions_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "chat_id": _u.uuid4().hex[:16],
                "title": _chat_title_from_messages(msgs, doc.get("topic", "")),
                "created_at": doc.get("updated_at", time_module_now()),
            }},
        )


def time_module_now() -> float:
    import time as _t
    return _t.time()


@router.get("/me/chats")
async def list_chats(
    topic: str = Query(None),
    current_user: dict = Depends(require_role("student")),
):
    """List the student's chats (all topics, most-recent first). Lightweight —
    no full message bodies, just title + preview for the sidebar."""
    student_id = current_user["username"]
    await _migrate_legacy_chats(student_id)

    query = {"student_id": student_id}
    if topic:
        query["topic"] = topic

    chats = []
    cursor = chat_sessions_collection.find(
        query,
        {"_id": 0, "chat_id": 1, "topic": 1, "title": 1, "messages": 1,
         "message_count": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1)
    async for doc in cursor:
        msgs = doc.get("messages", [])
        chats.append({
            "chat_id": doc.get("chat_id", ""),
            "topic": doc.get("topic", ""),
            "title": doc.get("title") or _chat_title_from_messages(msgs, doc.get("topic", "")),
            "preview": _chat_preview(msgs),
            "message_count": doc.get("message_count", len(msgs)),
            "created_at": doc.get("created_at", doc.get("updated_at", 0)),
            "updated_at": doc.get("updated_at", 0),
        })
    return {"chats": chats, "total": len(chats)}


@router.post("/me/chats")
async def create_chat(
    body: dict = Body(default={}),
    current_user: dict = Depends(require_role("student")),
):
    """Create a new (empty) chat for a topic and return its chat_id."""
    import uuid as _uuid_c
    student_id = current_user["username"]
    topic = (body.get("topic") or "").strip() or "General"
    now = time_module_now()
    chat_id = _uuid_c.uuid4().hex[:16]
    doc = {
        "chat_id": chat_id,
        "student_id": student_id,
        "topic": topic,
        "title": topic,
        "messages": [],
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await chat_sessions_collection.insert_one(doc)
    return {"chat_id": chat_id, "topic": topic, "title": topic, "created_at": now}


@router.get("/me/chats/{chat_id}")
async def get_chat(
    chat_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Load one chat's full messages (ownership-checked) to resume it."""
    student_id = current_user["username"]
    doc = await chat_sessions_collection.find_one(
        {"student_id": student_id, "chat_id": chat_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Chat not found")
    return {
        "chat_id": chat_id,
        "topic": doc.get("topic", ""),
        "title": doc.get("title", ""),
        "messages": doc.get("messages", []),
        "updated_at": doc.get("updated_at"),
    }


@router.post("/me/chats/{chat_id}/save")
async def save_chat_by_id(
    chat_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Append/overwrite a chat's messages. Auto-titles from first student msg."""
    student_id = current_user["username"]
    messages = (body.get("messages") or [])[-100:]  # cap to avoid bloat
    topic = (body.get("topic") or "").strip()

    existing = await chat_sessions_collection.find_one(
        {"student_id": student_id, "chat_id": chat_id}, {"_id": 0, "topic": 1, "title": 1}
    )
    if not existing:
        raise HTTPException(404, "Chat not found")

    topic = topic or existing.get("topic", "")
    # Keep an explicit title once set; otherwise derive from the conversation.
    title = existing.get("title") or _chat_title_from_messages(messages, topic)
    if title in ("", topic) and messages:
        title = _chat_title_from_messages(messages, topic)

    await chat_sessions_collection.update_one(
        {"student_id": student_id, "chat_id": chat_id},
        {"$set": {
            "topic": topic,
            "title": title,
            "messages": messages,
            "message_count": len(messages),
            "updated_at": time_module_now(),
        }},
    )
    return {"ok": True, "saved": len(messages), "chat_id": chat_id, "title": title}


@router.delete("/me/chats/{chat_id}")
async def delete_chat(
    chat_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Permanently delete a single chat."""
    student_id = current_user["username"]
    result = await chat_sessions_collection.delete_one(
        {"student_id": student_id, "chat_id": chat_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Chat not found")
    return {"ok": True, "chat_id": chat_id}


@router.get("/me/chat/{topic}")
async def get_chat_history(
    topic: str,
    current_user: dict = Depends(require_role("student")),
):
    """Legacy: return the most recent chat for a topic."""
    student_id = current_user["username"]
    await _migrate_legacy_chats(student_id)
    doc = await chat_sessions_collection.find_one(
        {"student_id": student_id, "topic": topic},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    if not doc:
        return {"messages": [], "topic": topic}
    return {
        "messages": doc.get("messages", []),
        "topic": topic,
        "chat_id": doc.get("chat_id", ""),
        "updated_at": doc.get("updated_at"),
    }


@router.post("/me/chat/save")
async def save_chat(
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Legacy save: upsert the most recent chat for a topic (or create one)."""
    import uuid as _uuid_lc
    student_id = current_user["username"]
    topic = body.get("topic", "")
    messages = (body.get("messages") or [])[-100:]
    if not topic:
        raise HTTPException(400, "topic required")

    existing = await chat_sessions_collection.find_one(
        {"student_id": student_id, "topic": topic},
        sort=[("updated_at", -1)],
    )
    chat_id = existing.get("chat_id") if existing else _uuid_lc.uuid4().hex[:16]
    await chat_sessions_collection.update_one(
        {"student_id": student_id, "chat_id": chat_id},
        {"$set": {
            "student_id": student_id,
            "chat_id": chat_id,
            "topic": topic,
            "title": (existing or {}).get("title") or _chat_title_from_messages(messages, topic),
            "messages": messages,
            "message_count": len(messages),
            "updated_at": time_module_now(),
        }, "$setOnInsert": {"created_at": time_module_now()}},
        upsert=True,
    )
    return {"ok": True, "saved": len(messages), "chat_id": chat_id}


@router.delete("/me/chat/{topic}")
async def clear_chat(
    topic: str,
    current_user: dict = Depends(require_role("student")),
):
    """Legacy: delete the most recent chat for a topic."""
    student_id = current_user["username"]
    doc = await chat_sessions_collection.find_one(
        {"student_id": student_id, "topic": topic}, sort=[("updated_at", -1)]
    )
    if doc:
        await chat_sessions_collection.delete_one({"_id": doc["_id"]})
    return {"ok": True}
