"""
Quiz — generate / submit / hint / retry, plus quiz history.
Extracted from serve.py.

Also owns the active-quiz store helpers (_save_active_quiz / _get_active_quiz)
and the lazy QuizGenerator singleton (_get_quiz_engine). serve.py re-exports
these so existing `from serve import _save_active_quiz, ...` call sites in
materials / review / extras keep resolving.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request

from adaptive.dependencies import get_current_user, require_role, require_self_or_guardian
from adaptive.rate_limit import limiter, check_llm_budget
from adaptive.utils.tone import get_tone_directive
from adaptive.utils.language import get_language_directive
from adaptive.utils.mongo_safe import safe_topic_filter
from adaptive.runtime import tutor, Hint
from adaptive.database import (
    users_collection, student_states_collection,
    mistakes_collection, quiz_history_collection,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quiz"])


# ── Extracted quiz routes + active-quiz store (verbatim from serve.py) ──
quiz_engine_instance = None


async def _save_active_quiz(quiz_id: str, doc: dict):
    from datetime import datetime, timezone as _tz
    from database import active_quizzes_collection
    doc = {**doc, "quiz_id": quiz_id, "created_at": datetime.now(_tz.utc)}
    await active_quizzes_collection.replace_one({"quiz_id": quiz_id}, doc, upsert=True)


async def _get_active_quiz(quiz_id: str):
    from database import active_quizzes_collection
    return await active_quizzes_collection.find_one({"quiz_id": quiz_id}, {"_id": 0})


def _get_quiz_engine():
    global quiz_engine_instance
    if quiz_engine_instance is None:
        from core.quiz_engine import QuizGenerator
        quiz_engine_instance = QuizGenerator()
    return quiz_engine_instance


@router.post("/quiz/{student_id}")
@limiter.limit("5/minute")
async def generate_quiz(
    request: Request,
    student_id: str,
    topic: str = "General",
    num_questions: int = 10,
    mode: str = "practice",
    duration_minutes: int = 0,
    _guard: dict = Depends(require_self_or_guardian("student_id")),
    current_user: dict = Depends(check_llm_budget),
):
    """Generate a new quiz. mode=practice (hints allowed, hint-discounted mastery)
    or mode=exam (B1: timed, no hints, full-credit honest grading)."""
    import re, uuid
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")
    if mode not in ("practice", "exam"):
        raise HTTPException(400, "mode must be practice or exam")
    if mode == "exam":
        duration_minutes = min(max(duration_minutes or 15, 5), 120)

    engine = _get_quiz_engine()
    tone = ""
    lang_dir = ""
    try:
        student = await tutor.sessions.get_student(student_id)
        if student:
            tone = get_tone_directive(student)
        u_doc = await users_collection.find_one({"username": student_id})
        lang_dir = get_language_directive((u_doc or {}).get("preferences"))
    except Exception:
        pass

    import asyncio

    # B2: quality feedback loop — if past questions on some concepts were missed
    # unusually often, tell the generator to write those more clearly.
    try:
        from database import content_stats_collection
        flagged = []
        async for s in content_stats_collection.find({"topic": topic, "shown": {"$gte": 5}}).limit(20):
            if s.get("wrong", 0) / max(s.get("shown", 1), 1) >= 0.7:
                flagged.append(s.get("concept", ""))
        if flagged:
            tone += (
                "\nQUALITY NOTE: students frequently miss questions on these concepts: "
                + ", ".join(f for f in flagged[:5] if f)
                + ". Write those questions with extra-clear, unambiguous wording and "
                "plausible but clearly-distinct options."
            )
    except Exception:
        pass

    # --- 10 MCQ (existing cheap-tier generator) ---
    quiz_data = await engine.generate_quiz(
        topic=topic,
        num_questions=10,
        tone_directive=tone,
        language_directive=lang_dir,
    )

    mcq_questions = quiz_data["questions"]
    for q in mcq_questions:
        q["type"] = "mcq"
        q["hints_used"] = 0

    # --- 5 open-ended (no option) questions: 2 easy / 2 medium / 1 hard ---
    open_diffs = ["easy", "easy", "medium", "medium", "hard"]

    async def _gen_open(diff):
        try:
            r = await tutor.generator.generate_question(
                topic=topic,
                difficulty=diff,
                frustration=0.3,
                knowledge=0.5,
                explanation={"core_concept": topic},
                tone_directive=tone,
                language_directive=lang_dir,
            )
            return r
        except Exception as e:
            logger.warning("open question gen failed (%s): %s", diff, e)
            return None

    open_results = await asyncio.gather(*[_gen_open(d) for d in open_diffs])

    base_id = len(mcq_questions)
    open_questions = []
    for i, (diff, r) in enumerate(zip(open_diffs, open_results)):
        if not r or not r.get("question"):
            continue
        open_questions.append({
            "id": base_id + i + 1,
            "type": "open",
            "question": r["question"],
            "answer": r.get("answer", ""),
            "explanation": r.get("explanation", ""),
            "options": {},
            "multiple": False,
            "correct": [],
            "concept": topic,
            "difficulty": diff,
            "hints_used": 0,
        })

    all_questions = mcq_questions + open_questions

    quiz_id = str(uuid.uuid4())[:8]
    import time as _t_exam
    deadline = (_t_exam.time() + duration_minutes * 60) if mode == "exam" else None
    await _save_active_quiz(quiz_id, {
        "questions": all_questions,
        "student_id": student_id,
        "topic": topic,
        "mode": mode,
        "duration_minutes": duration_minutes,
        "deadline": deadline,
    })

    public_questions = []
    for q in all_questions:
        public_questions.append({
            "id": q["id"],
            "type": q.get("type", "mcq"),
            "question": q["question"],
            "options": q.get("options", {}),
            "multiple": q.get("multiple", False),
            "concept": q.get("concept", ""),
            "difficulty": q.get("difficulty", "medium"),
        })

    return {
        "quiz_title": quiz_data["quiz_title"],
        "questions": public_questions,
        "quiz_id": quiz_id,
        "mode": mode,
        "duration_minutes": duration_minutes,
        "deadline": deadline,
    }


@router.post("/quiz/{student_id}/submit")
async def submit_quiz(
    student_id: str,
    quiz_id: str = Query(...),
    answers: dict = Body(...),
    current_user: dict = Depends(require_self_or_guardian("student_id")),
):
    """Submit quiz answers and get scored results."""
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    quiz_data = await _get_active_quiz(quiz_id)
    if not quiz_data:
        raise HTTPException(404, "Quiz not found or expired")

    if quiz_data["student_id"] != student_id:
        raise HTTPException(403, "This quiz belongs to a different student")

    int_answers = {}
    for k, v in answers.items():
        try:
            int_answers[int(k)] = v if isinstance(v, list) else [v]
        except (ValueError, TypeError):
            continue

    import asyncio, time as _time_quiz
    engine = _get_quiz_engine()
    all_qs = quiz_data["questions"]
    topic = quiz_data.get("topic", "General")

    # --- MCQ scoring (exact match) ---
    mcq_score = engine.score_quiz(all_qs, int_answers)
    results = list(mcq_score.get("results", []))

    # --- Open-ended grading via answer evaluator ---
    now = _time_quiz.time()
    open_qs = [q for q in all_qs if q.get("type") == "open"]

    async def _grade_open(q):
        qid = q["id"]
        raw = answers.get(str(qid), answers.get(qid, ""))
        text = " ".join(str(x) for x in raw) if isinstance(raw, list) else str(raw or "")
        base = {
            "id": qid,
            "type": "open",
            "question": q["question"],
            "submitted": [text] if text else [],
            "user_answer": text,
            "correct_answer": q.get("answer", ""),
            "concept": q.get("concept", topic),
            "hints_used": q.get("hints_used", 0),
        }
        if not text.strip():
            base.update({"is_correct": False, "explanation": q.get("explanation", ""),
                         "misconception": None, "remediation": ""})
            return base
        try:
            ev = await tutor.evaluator.evaluate(
                question=q["question"], student_answer=text,
                correct_answer=q.get("answer", ""), start_time=now, end_time=now,
                topic=topic, difficulty=q.get("difficulty", "medium"),
            )
        except Exception as e:
            logger.warning("open grade failed: %s", e)
            ev = {"correct": False}
        base.update({
            "is_correct": bool(ev.get("correct")),
            "explanation": ev.get("targeted_feedback") or q.get("explanation", ""),
            "misconception": ev.get("misconception"),
            "remediation": ev.get("remediation", ""),
        })
        return base

    if open_qs:
        results.extend(await asyncio.gather(*[_grade_open(q) for q in open_qs]))

    # --- Totals + mastery credit ---
    # practice: hint-discounted credit; exam (B1): no hints exist, full credit, late flag
    quiz_mode = quiz_data.get("mode", "practice")
    deadline = quiz_data.get("deadline")
    late = bool(quiz_mode == "exam" and deadline and now > deadline + 30)  # 30s grace

    total = len(all_qs)
    raw_correct = sum(1 for r in results if r.get("is_correct"))
    effective = 0.0
    total_hints = 0
    for r in results:
        total_hints += r.get("hints_used", 0)
        if r.get("is_correct"):
            if quiz_mode == "exam":
                effective += 1.0
            else:
                effective += 0.5 if r.get("hints_used", 0) > 0 else 1.0
    score_pct = round((raw_correct / total * 100) if total else 0, 1)

    score_result = {
        "total_questions": total,
        "correct_count": raw_correct,
        "score_percentage": score_pct,
        "passed": score_pct >= 70,
        "results": results,
        "mode": quiz_mode,
        "practice_mode": quiz_mode == "practice",
        "late_submission": late,
        "effective_mastery_credit": round(effective, 2),
        "hints_used_total": total_hints,
    }

    # Mastery uses hint-discounted credit, not raw score
    await student_states_collection.update_one(
        {"student_id": student_id},
        {"$inc": {
            "total_questions": total,
            "correct_answers": int(round(effective)),
            "quizzes_taken": 1,
            "hint_used": total_hints,
        }},
        upsert=True,
    )

    # Keep the quiz around (with its scored result) so wrong answers can be re-quizzed
    from database import active_quizzes_collection as _aqc
    await _aqc.update_one(
        {"quiz_id": quiz_id},
        {"$set": {"submitted": True, "result": score_result}},
    )

    # N9: Persist quiz history
    wrong_concepts = [r["concept"] for r in results if not r.get("is_correct") and r.get("concept")]
    await quiz_history_collection.insert_one({
        "student_id": student_id,
        "quiz_id": quiz_id,
        "topic": topic,
        "score_pct": score_pct,
        "correct": raw_correct,
        "total": total,
        "passed": score_result["passed"],
        "wrong_concepts": wrong_concepts,
        "hints_used_total": total_hints,
        "mode": quiz_mode,
        "late_submission": late,
        "taken_at": now,
    })

    # N5: Capture wrong answers as mistakes
    import uuid as _uuid_m
    for r in results:
        if not r.get("is_correct"):
            await mistakes_collection.insert_one({
                "student_id": student_id,
                "mistake_id": str(_uuid_m.uuid4())[:12],
                "source": "quiz",
                "topic": topic,
                "concept": r.get("concept", ""),
                "question": r.get("question", ""),
                "user_answer": r.get("user_answer") or ", ".join(r.get("submitted", [])),
                "correct_answer": r.get("correct_answer") or ", ".join(r.get("correct", [])),
                "explanation": r.get("explanation", ""),
                "timestamp": now,
                "resolved": False,
            })

    # B2: Content quality stats — aggregate outcomes per concept/difficulty
    try:
        from database import content_stats_collection
        for r in results:
            q_orig = next((q for q in all_qs if q["id"] == r.get("id")), {})
            await content_stats_collection.update_one(
                {
                    "topic": topic,
                    "concept": r.get("concept", "") or topic,
                    "difficulty": q_orig.get("difficulty", "medium"),
                },
                {"$inc": {
                    "shown": 1,
                    "wrong": 0 if r.get("is_correct") else 1,
                    "hinted": 1 if r.get("hints_used", 0) > 0 else 0,
                }},
                upsert=True,
            )
    except Exception as e:
        logger.warning("content stats skipped: %s", e)

    return score_result


@router.post("/quiz/{quiz_id}/hint")
@limiter.limit("10/minute")
async def quiz_hint(
    request: Request,
    quiz_id: str,
    question_id: int = Body(..., embed=True),
    hint_number: int = Body(1, embed=True),
    current_user: dict = Depends(check_llm_budget),
):
    """Progressive hint for one quiz question (max 3 per question). Practice mode only."""
    quiz_data = await _get_active_quiz(quiz_id)
    if not quiz_data:
        raise HTTPException(404, "Quiz not found or expired")

    if quiz_data.get("mode") == "exam":
        raise HTTPException(403, "Hints are not available in exam mode")

    q = next((x for x in quiz_data["questions"] if x["id"] == question_id), None)
    if q is None:
        raise HTTPException(404, "Question not found in this quiz")

    used = q.get("hints_used", 0)
    if used >= 3:
        return {"hint": None, "hints_used": used, "exhausted": True,
                "message": "You've used all 3 hints for this question."}

    hint_number = max(1, min(3, used + 1))
    directive = (
        f"Give hint number {hint_number} of 3 for this question — progressively more "
        f"specific, but never reveal the final answer.\n\nQuestion: {q['question']}"
    )
    hint_text = await Hint.generate_hint(directive)

    q["hints_used"] = used + 1
    from database import active_quizzes_collection as _aqc_h
    await _aqc_h.update_one(
        {"quiz_id": quiz_id, "questions.id": question_id},
        {"$set": {"questions.$.hints_used": q["hints_used"]}},
    )

    return {"hint": hint_text, "hints_used": q["hints_used"], "exhausted": q["hints_used"] >= 3}


@router.post("/quiz/{quiz_id}/retry-wrong")
async def retry_wrong_quiz(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Build a new quiz from only the questions the student got wrong."""
    import uuid as _uuid_rw

    quiz_data = await _get_active_quiz(quiz_id)
    if not quiz_data:
        raise HTTPException(404, "Quiz not found or expired")

    if quiz_data.get("student_id") != current_user["username"]:
        raise HTTPException(403, "This quiz belongs to a different student")

    result = quiz_data.get("result")
    if not result:
        raise HTTPException(400, "Quiz has not been submitted yet")

    wrong_ids = {r["id"] for r in result.get("results", []) if not r.get("is_correct")}
    if not wrong_ids:
        raise HTTPException(400, "No wrong answers to retry")

    # Collect the original wrong questions, reset hint usage, renumber ids
    wrong_questions = []
    for i, q in enumerate(quiz_data["questions"]):
        if q["id"] in wrong_ids:
            nq = dict(q)
            nq["hints_used"] = 0
            wrong_questions.append(nq)

    new_quiz_id = str(_uuid_rw.uuid4())[:8]
    await _save_active_quiz(new_quiz_id, {
        "questions": wrong_questions,
        "student_id": quiz_data["student_id"],
        "topic": quiz_data.get("topic", "General"),
        "retry_of": quiz_id,
    })

    public_questions = []
    for q in wrong_questions:
        public_questions.append({
            "id": q["id"],
            "type": q.get("type", "mcq"),
            "question": q["question"],
            "options": q.get("options", {}),
            "multiple": q.get("multiple", False),
            "concept": q.get("concept", ""),
            "difficulty": q.get("difficulty", "medium"),
        })

    return {
        "quiz_title": "Retry: wrong questions",
        "questions": public_questions,
        "quiz_id": new_quiz_id,
    }


@router.get("/me/quiz-history")
async def get_quiz_history(
    topic: str = Query(None),
    limit: int = Query(20, le=50),
    current_user: dict = Depends(require_role("student")),
):
    """List past quiz attempts, optionally filtered by topic."""
    student_id = current_user["username"]
    query = {"student_id": student_id}
    if topic:
        query["topic"] = safe_topic_filter(topic)

    cursor = quiz_history_collection.find(
        query, {"_id": 0}
    ).sort("taken_at", -1).limit(limit)

    history = []
    async for doc in cursor:
        history.append({
            "quiz_id": doc.get("quiz_id", ""),
            "topic": doc.get("topic", ""),
            "score_pct": doc.get("score_pct", 0),
            "correct": doc.get("correct", 0),
            "total": doc.get("total", 0),
            "passed": doc.get("passed", False),
            "taken_at": doc.get("taken_at", 0),
            "wrong_concepts": doc.get("wrong_concepts", []),
        })

    # Compute a TRUE all-time average across every quiz (not just the returned
    # page). The previous version averaged only the limited `history` slice.
    total_quizzes = await quiz_history_collection.count_documents({"student_id": student_id})
    avg_score = 0.0
    try:
        agg = await quiz_history_collection.aggregate([
            {"$match": {"student_id": student_id}},
            {"$group": {"_id": None, "avg": {"$avg": "$score_pct"}}},
        ]).to_list(length=1)
        if agg and agg[0].get("avg") is not None:
            avg_score = round(agg[0]["avg"], 1)
    except Exception as e:
        logger.warning("quiz avg aggregation failed, falling back to page avg: %s", e)
        if history:
            avg_score = round(sum(h["score_pct"] for h in history) / len(history), 1)

    return {
        "history": history,
        "total_quizzes": total_quizzes,
        "avg_score": avg_score,
    }
