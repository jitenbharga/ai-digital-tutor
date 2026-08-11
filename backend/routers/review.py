"""
Review — spaced review, study plan, mistakes, and diagnostics.
Extracted from serve.py (/review, /study-plan, /me/review-due-count,
/me/mistakes*) and api/extras.py (/me/diagnose, /me/mock-test,
/me/practice/weak-spots).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request

from dependencies import require_role, require_self_or_guardian
from rate_limit import limiter, check_llm_budget, user_key
from utils.tone import get_tone_directive
from utils.language import get_language_directive
from utils.mongo_safe import safe_topic_filter
from runtime import tutor, review_engine, study_planner
from api.schemas import ReviewResponse, StudyPlanResponse
from database import mistakes_collection, users_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["review"])


# ── Review / study-plan / mistakes (from serve.py) ────────────────────
@router.get("/review/{student_id}", response_model=ReviewResponse)
async def review(student_id: str, current_user: dict = Depends(require_self_or_guardian("student_id"))):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        raise HTTPException(404, "Student not found")

    due_topics = review_engine.get_due_topics(student, threshold=0.9)

    if not due_topics:
        return {
            "due_topics": [],
            "review_question": None,
            "message": "All topics are fresh. No review needed right now."
        }

    most_urgent = due_topics[0]
    tone = get_tone_directive(student)
    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))

    review_q = await review_engine.generate_review_question(
        topic=most_urgent["topic"],
        days_ago=most_urgent["days_since_review"],
        mastery=most_urgent["mastery"],
        retention_estimate=most_urgent["retention_estimate"],
        tone_directive=tone,
        language_directive=lang_dir,
    )

    return {
        "due_topics": due_topics,
        "review_question": review_q,
        "message": "%d topic(s) due for review. Starting with: %s" % (len(due_topics), most_urgent["topic"])
    }


@router.get("/study-plan/{student_id}", response_model=StudyPlanResponse)
async def study_plan(
    student_id: str,
    available_minutes: int = 30,
    current_user: dict = Depends(require_self_or_guardian("student_id")),
):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        raise HTTPException(404, "Student not found")

    tone = get_tone_directive(student)
    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))

    result = await study_planner.generate_plan(
        student=student,
        available_minutes=available_minutes,
        tone_directive=tone,
        language_directive=lang_dir,
    )

    return result


@router.get("/me/review-due-count")
async def get_review_due_count(
    current_user: dict = Depends(require_role("student")),
):
    """Return count of topics due for FSRS review. Lightweight — no question generation."""
    student_id = current_user["username"]

    student = await tutor.sessions.get_student(student_id)
    if not student or not student.concepts:
        return {"count": 0, "topics": []}

    due = review_engine.get_due_topics(student, threshold=0.85)
    return {
        "count": len(due),
        "topics": [{"topic": d["topic"], "retention": round(d["retention_estimate"], 2)} for d in due[:5]],
    }


@router.get("/me/mistakes")
async def get_mistakes(
    topic: str = Query(None),
    resolved: bool = Query(None),
    limit: int = Query(50, le=100),
    current_user: dict = Depends(require_role("student")),
):
    """List mistakes. Filter by topic or resolved status."""
    student_id = current_user["username"]
    query = {"student_id": student_id}
    if topic:
        query["topic"] = safe_topic_filter(topic)
    if resolved is not None:
        query["resolved"] = resolved

    cursor = mistakes_collection.find(
        query, {"_id": 0, "student_id": 0}
    ).sort("timestamp", -1).limit(limit)

    mistakes = []
    async for doc in cursor:
        mistakes.append({
            "mistake_id": doc.get("mistake_id", ""),
            "source": doc.get("source", ""),
            "topic": doc.get("topic", ""),
            "concept": doc.get("concept", ""),
            "question": doc.get("question", ""),
            "user_answer": doc.get("user_answer", ""),
            "correct_answer": doc.get("correct_answer", ""),
            "explanation": doc.get("explanation", ""),
            "timestamp": doc.get("timestamp", 0),
            "resolved": doc.get("resolved", False),
            "resolved_at": doc.get("resolved_at"),
        })

    total = await mistakes_collection.count_documents({"student_id": student_id})
    unresolved = await mistakes_collection.count_documents(
        {"student_id": student_id, "resolved": False}
    )

    return {
        "mistakes": mistakes,
        "total": total,
        "unresolved": unresolved,
    }


@router.post("/me/mistakes/{mistake_id}/resolve")
async def resolve_mistake(
    mistake_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Mark a mistake as resolved/understood."""
    student_id = current_user["username"]
    import time as _time5

    result = await mistakes_collection.update_one(
        {"student_id": student_id, "mistake_id": mistake_id},
        {"$set": {"resolved": True, "resolved_at": _time5.time()}},
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Mistake not found")

    return {"ok": True, "mistake_id": mistake_id}


@router.post("/me/mistakes/{mistake_id}/explain")
async def explain_mistake(
    mistake_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Feynman-on-mistakes: the student explains, in their own words, why their
    answer was wrong and what the correct idea is. Graded IN THE CONTEXT of the
    mistake; if they show real understanding, it's auto-resolved."""
    from core.llm_utils import call_llm
    from core.llm_registry import build_models_cheap
    from utils.prompt_safety import wrap_student_text

    student_id = current_user["username"]
    explanation = (body.get("explanation") or "").strip()
    if len(explanation) < 20:
        raise HTTPException(400, "Write at least a sentence or two in your own words.")
    if len(explanation) > 4000:
        raise HTTPException(400, "Explanation too long (max 4000 chars)")

    m = await mistakes_collection.find_one(
        {"student_id": student_id, "mistake_id": mistake_id}
    )
    if not m:
        raise HTTPException(404, "Mistake not found")

    safe = wrap_student_text(explanation, "student_explanation")
    prompt = (
        "You are a kind, honest tutor. A student is explaining, in their own words, why they got a "
        "question wrong and what the correct idea is. Grade ONLY whether they now genuinely understand "
        "the concept behind THIS mistake — be encouraging but don't pass a vague or wrong explanation.\n\n"
        f"Topic: {m.get('topic','')}\n"
        f"Question: {m.get('question','')}\n"
        f"Their earlier wrong answer: {m.get('user_answer','')}\n"
        f"Correct answer: {m.get('correct_answer','')}\n"
        f"Reference explanation: {m.get('explanation','')}\n\n"
        f"The student's explain-back:\n{safe}\n\n"
        'Return ONLY JSON: {"understood": true/false, "score": 0-100, '
        '"what_was_good": "one line", "still_missing": ["..."], '
        '"feedback": "one or two encouraging, specific lines"}'
    )
    result = await call_llm(
        build_models_cheap(), prompt, required_key="understood",
        engine_name="mistake_explain", prompt_version="v1",
    )
    if not isinstance(result, dict):
        raise HTTPException(502, "Couldn't grade that — try again")

    understood = bool(result.get("understood")) or int(result.get("score", 0) or 0) >= 75
    resolved = False
    if understood:
        import time as _t_me
        await mistakes_collection.update_one(
            {"student_id": student_id, "mistake_id": mistake_id},
            {"$set": {"resolved": True, "resolved_at": _t_me.time(),
                      "resolved_via": "explain_back"}},
        )
        resolved = True

    return {
        "understood": understood,
        "resolved": resolved,
        "score": int(result.get("score", 0) or 0),
        "what_was_good": result.get("what_was_good", ""),
        "still_missing": result.get("still_missing", []) or [],
        "feedback": result.get("feedback", ""),
    }


# ── Diagnostics / mock-test / weak-spot practice (from api/extras.py) ──
WEAK_MASTERY = 0.55   # below this a concept counts as weak


@router.get("/me/diagnose/{topic}")
@limiter.limit("30/minute", key_func=user_key)
async def diagnose_stuck(
    request: Request,
    topic: str,
    subject: str = Query(None),
    current_user: dict = Depends(require_role("student")),
):
    """
    Trace WHY a topic won't stick: walk the curriculum prerequisite graph
    backward and report the weakest upstream root cause. Pure reuse of KT
    mastery + the canonical tree's prerequisites[] — no LLM required.
    """
    from serve import tutor  # live KT manager
    from core.curriculum_engine import (
        normalize_subject, get_or_generate_tree, SUBJECTS,
    )

    student_id = current_user["username"]
    topic = topic.strip()[:200]

    async def mastery_of(name: str) -> float:
        try:
            r = await tutor.kt.predict_mastery(student_id, name, heuristic_fallback=0.5)
            return float(r.get("p_correct", 0.5))
        except Exception:
            return 0.5

    # Find the subject tree that contains this topic
    tree = None
    if subject:
        tree = await get_or_generate_tree(normalize_subject(subject))
    if not tree:
        for s in SUBJECTS:
            t = await get_or_generate_tree(s["id"])
            if t and any(
                topic.lower() in (n.get("title", "").lower())
                or n.get("node_id") == topic
                for n in t.get("nodes", [])
            ):
                tree = t
                break

    topic_mastery = await mastery_of(topic)

    # No tree / prerequisites available → answer from mastery alone
    if not tree:
        return {
            "topic": topic,
            "topic_mastery": round(topic_mastery, 2),
            "chain": [{"concept": topic, "mastery": round(topic_mastery, 2), "is_root_gap": True}],
            "root_gap": None,
            "explanation": (
                f"Keep practicing {topic} — I don't have a prerequisite map for it, "
                "so more focused practice is the way forward."
                if topic_mastery < WEAK_MASTERY else
                f"Your {topic} looks solid — this may just need a bit more practice."
            ),
        }

    nodes = tree.get("nodes", [])
    by_id = {n["node_id"]: n for n in nodes}
    title_to_id = {n.get("title", "").lower(): n["node_id"] for n in nodes}

    # Resolve the starting node
    start_id = topic if topic in by_id else title_to_id.get(topic.lower())

    # Walk prerequisites backward, following the WEAKEST weak prereq each step
    chain = [{"concept": topic, "node_id": start_id, "mastery": round(topic_mastery, 2), "is_root_gap": False}]
    visited = set()
    cur_id = start_id
    while cur_id and cur_id not in visited:
        visited.add(cur_id)
        node = by_id.get(cur_id)
        if not node:
            break
        prereqs = node.get("prerequisites", []) or []
        # mastery of each prerequisite
        weak = []
        for pid in prereqs:
            pnode = by_id.get(pid)
            if not pnode:
                continue
            m = await mastery_of(pnode.get("title", pid))
            if m < WEAK_MASTERY:
                weak.append((m, pid, pnode.get("title", pid)))
        if not weak:
            break  # no weak prerequisite → current node is the root gap
        weak.sort()  # weakest first
        m, pid, ptitle = weak[0]
        chain.append({"concept": ptitle, "node_id": pid, "mastery": round(m, 2), "is_root_gap": False})
        cur_id = pid

    # The deepest reached weak concept is the root gap
    root = chain[-1]
    root["is_root_gap"] = True

    if topic_mastery >= WEAK_MASTERY and len(chain) == 1:
        explanation = f"Your {topic} looks solid — this likely just needs a little more practice."
    elif len(chain) == 1:
        explanation = (
            f"{topic} isn't sticking, and its prerequisites look fine — so the fix is more "
            f"focused practice on {topic} itself."
        )
    else:
        explanation = (
            f"{topic} isn't sticking because {root['concept']} — a prerequisite — is still weak "
            f"({int(root['mastery'] * 100)}% mastery). Fix that first and {topic} gets much easier."
        )

    return {
        "topic": topic,
        "topic_mastery": round(topic_mastery, 2),
        "chain": chain,
        "root_gap": root if len(chain) > 1 else None,
        "explanation": explanation,
    }


@router.post("/me/mock-test")
@limiter.limit("5/minute", key_func=user_key)
async def mock_test(
    request: Request,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """
    Build a timed, mixed, full-syllabus mock — weighted toward the student's
    weak concepts (low KT mastery + recently missed). Registers as an exam-mode
    active quiz so the normal submit/results/mistakes pipeline works unchanged.
    """
    import uuid
    from serve import tutor, _get_quiz_engine, _save_active_quiz
    from core.curriculum_engine import normalize_subject, get_or_generate_tree

    student_id = current_user["username"]

    subject = (body.get("subject") or "").strip()
    if not subject:
        raise HTTPException(400, "subject is required")
    num_q = min(max(int(body.get("num_questions") or 15), 5), 30)
    duration = min(max(int(body.get("duration_minutes") or 20), 5), 120)

    tree = await get_or_generate_tree(normalize_subject(subject))
    if not tree:
        raise HTTPException(404, "Subject not found")

    # Candidate concepts = studied leaf/topic nodes
    nodes = [n for n in tree.get("nodes", []) if n.get("level", 1) >= 1 and n.get("title")]
    if not nodes:
        raise HTTPException(400, "No topics found for this subject")

    # Weakness weight per concept: (1 - mastery) plus a bump for recent mistakes
    from database import mistakes_collection
    recent_wrong = {}
    async for m in mistakes_collection.find(
        {"student_id": student_id}, {"concept": 1, "topic": 1}
    ).sort("timestamp", -1).limit(100):
        key = (m.get("concept") or m.get("topic") or "").lower()
        if key:
            recent_wrong[key] = recent_wrong.get(key, 0) + 1

    weighted = []
    for n in nodes:
        title = n["title"]
        try:
            r = await tutor.kt.predict_mastery(student_id, title, heuristic_fallback=0.5)
            mastery = float(r.get("p_correct", 0.5))
        except Exception:
            mastery = 0.5
        weight = (1.0 - mastery) + 0.5 * recent_wrong.get(title.lower(), 0)
        weighted.append((max(weight, 0.05), title, round(mastery, 2)))

    # Weighted sample of distinct concepts to span (up to ~6 buckets)
    buckets = min(6, len(weighted), num_q)
    chosen = _weighted_sample_distinct(weighted, buckets)
    per_bucket = max(1, num_q // len(chosen))

    engine = _get_quiz_engine()
    all_questions = []
    breakdown = []
    qid = 1
    for weight, title, mastery in chosen:
        breakdown.append({"concept": title, "mastery": mastery, "weight": round(weight, 2)})
        try:
            qz = await engine.generate_quiz(topic=title, num_questions=per_bucket)
        except Exception as e:
            logger.warning("mock bucket gen failed for %s: %s", title, e)
            continue
        for q in qz.get("questions", [])[:per_bucket]:
            q["id"] = qid
            q["type"] = "mcq"
            q["hints_used"] = 0
            q["concept"] = title  # tag for per-topic scoring
            all_questions.append(q)
            qid += 1

    if not all_questions:
        raise HTTPException(502, "Could not generate the mock — try again")

    import time as _t
    quiz_id = str(uuid.uuid4())[:8]
    await _save_active_quiz(quiz_id, {
        "questions": all_questions,
        "student_id": student_id,
        "topic": f"{subject} mock",
        "mode": "exam",
        "duration_minutes": duration,
        "deadline": _t.time() + duration * 60,
        "source": "mock_test",
    })

    return {
        "quiz_title": f"Mock test: {subject}",
        "quiz_id": quiz_id,
        "mode": "exam",
        "duration_minutes": duration,
        "deadline": _t.time() + duration * 60,
        "weakness_breakdown": sorted(breakdown, key=lambda x: x["mastery"]),
        "questions": [
            {"id": q["id"], "type": "mcq", "question": q["question"],
             "options": q.get("options", {}), "multiple": q.get("multiple", False),
             "concept": q.get("concept", ""), "difficulty": q.get("difficulty", "medium")}
            for q in all_questions
        ],
    }


def _weighted_sample_distinct(weighted, k):
    """Sample k distinct (weight,title,mastery) tuples without replacement, weight-biased."""
    import random
    pool = list(weighted)
    picked = []
    while pool and len(picked) < k:
        total = sum(w for w, _, _ in pool)
        r = random.uniform(0, total)
        acc = 0
        for i, (w, t, m) in enumerate(pool):
            acc += w
            if acc >= r:
                picked.append(pool.pop(i))
                break
        else:
            picked.append(pool.pop())
    return picked


@router.post("/me/practice/weak-spots")
@limiter.limit("6/minute", key_func=user_key)
async def practice_weak_spots(
    request: Request,
    body: dict = Body(default={}),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Build a short practice quiz targeting the student's real weak areas.
    Signals (weighted): unresolved mistakes > low mastery > overdue reviews."""
    import uuid, time as _t
    from serve import tutor, _get_quiz_engine, _save_active_quiz
    from utils.tone import get_tone_directive
    from utils.language import get_language_directive
    from database import (
        mistakes_collection, student_states_collection,
        flashcards_collection, users_collection,
    )

    student_id = current_user["username"]
    num_q = min(max(int(body.get("num_questions") or 8), 4), 15)

    weights, reasons = {}, {}

    def _bump(topic, w, why):
        t = (topic or "").strip()
        if not t:
            return
        weights[t] = weights.get(t, 0.0) + w
        reasons.setdefault(t, why)

    # 1) Unresolved mistakes — strongest signal (you already got these wrong)
    try:
        async for m in mistakes_collection.find(
            {"student_id": student_id, "resolved": False},
            {"_id": 0, "concept": 1, "topic": 1},
        ).sort("timestamp", -1).limit(50):
            _bump(m.get("concept") or m.get("topic"), 1.0, "recent mistake")
    except Exception as e:
        logger.warning("weak-spots mistakes skipped: %s", e)

    # 2) Lowest-mastery concepts from the student's state
    try:
        state = await student_states_collection.find_one(
            {"student_id": student_id}, {"_id": 0, "concepts": 1}
        )
        graded = []
        for name, c in ((state or {}).get("concepts", {}) or {}).items():
            m = c.get("concept_mastery", c.get("knowledge", 0.5)) if isinstance(c, dict) else 0.5
            graded.append((float(m), name))
        graded.sort()
        for m, name in graded[:6]:
            if m < 0.6:
                _bump(name, (0.6 - m) * 2.0, f"low mastery ({int(m * 100)}%)")
    except Exception as e:
        logger.warning("weak-spots mastery skipped: %s", e)

    # 3) Overdue flashcards → their topics
    try:
        now = _t.time()
        async for card in flashcards_collection.find(
            {"student_id": student_id, "due_ts": {"$lte": now}},
            {"_id": 0, "topic": 1},
        ).sort("due_ts", 1).limit(30):
            _bump(card.get("topic"), 0.5, "overdue review")
    except Exception as e:
        logger.warning("weak-spots flashcards skipped: %s", e)

    if not weights:
        return {
            "empty": True,
            "message": "No weak spots yet — do a few quizzes or lessons and I'll "
                       "build a targeted set from what you miss.",
        }

    top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
    per = max(1, num_q // len(top))

    # tone + language directives
    tone, lang_dir = "", ""
    try:
        student = await tutor.sessions.get_student(student_id)
        if student:
            tone = get_tone_directive(student)
        u = await users_collection.find_one({"username": student_id})
        lang_dir = get_language_directive((u or {}).get("preferences"))
    except Exception:
        pass

    engine = _get_quiz_engine()
    all_questions, focus, qid = [], [], 1
    for topic, _score in top:
        focus.append({"topic": topic, "reason": reasons.get(topic, "weak area")})
        try:
            qz = await engine.generate_quiz(
                topic=topic, num_questions=per,
                tone_directive=tone, language_directive=lang_dir,
            )
        except Exception as e:
            logger.warning("weak-spots gen failed for %s: %s", topic, e)
            continue
        for q in qz.get("questions", [])[:per]:
            q["id"] = qid
            q["type"] = "mcq"
            q["hints_used"] = 0
            q["concept"] = topic
            all_questions.append(q)
            qid += 1

    if not all_questions:
        raise HTTPException(502, "Couldn't build a practice set — try again")

    quiz_id = str(uuid.uuid4())[:8]
    await _save_active_quiz(quiz_id, {
        "questions": all_questions,
        "student_id": student_id,
        "topic": "Weak-spot practice",
        "mode": "practice",
        "source": "weak_spots",
    })

    return {
        "quiz_title": "Fix my weak spots",
        "quiz_id": quiz_id,
        "mode": "practice",
        "focus": focus,
        "questions": [
            {"id": q["id"], "type": "mcq", "question": q["question"],
             "options": q.get("options", {}), "multiple": q.get("multiple", False),
             "concept": q.get("concept", ""), "difficulty": q.get("difficulty", "medium")}
            for q in all_questions
        ],
    }
