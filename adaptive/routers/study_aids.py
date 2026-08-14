"""
Study aids — cheatsheets, Feynman mode, flashcards, exam plans.
Extracted from api/extras.py.

Route groups:
  Flashcards      /me/flashcards/*        (spaced-repetition sync/due/grade)
  Exam plan       /me/exam-plan, /me/next-exam
  Cheatsheet      /me/cheatsheet*         (generate / smart / PDF export)
  Feynman mode    /me/feynman/*           (explain-back evaluation + history)
  Recap           /me/recap
  Exam readiness  /me/exam-readiness/{subject}
"""

import time
import re
import logging

from fastapi import APIRouter, HTTPException, Query, Body, Depends, Request

from adaptive.dependencies import require_role
from adaptive.rate_limit import limiter, check_llm_budget, user_key
from adaptive.utils.mongo_safe import safe_topic_filter, exact_topic_value
from adaptive.database import mistakes_collection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["study_aids"])


# ── Extracted route handlers + helpers (verbatim from api/extras.py) ──
def _flash_scheduler():
    from fsrs import Scheduler
    return Scheduler(desired_retention=0.9, enable_fuzzing=False)


def _card_due_ts(card) -> float:
    try:
        return card.due.timestamp()
    except Exception:
        return time.time()


@router.post("/me/flashcards/sync")
async def sync_flashcards(
    current_user: dict = Depends(require_role("student")),
):
    """Build/refresh the deck: one card per unresolved mistake + one per notebook note.
    Existing cards are kept (their FSRS state is precious). Resolved-mistake cards are removed."""
    import uuid
    from fsrs import Card
    from database import flashcards_collection, notes_collection

    student_id = current_user["username"]
    existing = set()
    async for c in flashcards_collection.find(
        {"student_id": student_id}, {"source_id": 1}
    ):
        existing.add(c.get("source_id"))

    created = 0

    # Cards from unresolved mistakes: front = question, back = answer + why
    async for m in mistakes_collection.find(
        {"student_id": student_id, "resolved": False}
    ).sort("timestamp", -1).limit(200):
        sid = f"mistake:{m.get('mistake_id', '')}"
        if sid in existing or not m.get("question"):
            continue
        card = Card()
        await flashcards_collection.insert_one({
            "student_id": student_id,
            "card_id": str(uuid.uuid4())[:12],
            "source": "mistake",
            "source_id": sid,
            "front": m.get("question", "")[:1000],
            "back": (
                (m.get("correct_answer", "") or "")
                + ("\n\nWhy: " + m.get("explanation", "") if m.get("explanation") else "")
            )[:2000],
            "topic": m.get("topic", ""),
            "fsrs": card.to_dict(),
            "due_ts": _card_due_ts(card),
            "created_at": time.time(),
        })
        created += 1

    # Cards from notebook notes: recall your own highlight
    async for n in notes_collection.find(
        {"student_id": student_id}
    ).sort("created_at", -1).limit(200):
        sid = f"note:{n.get('note_id', '')}"
        if sid in existing or not n.get("selected_text"):
            continue
        card = Card()
        hint = (n.get("user_note") or "").strip()
        await flashcards_collection.insert_one({
            "student_id": student_id,
            "card_id": str(uuid.uuid4())[:12],
            "source": "note",
            "source_id": sid,
            "front": (
                f"Recall your highlight on \"{n.get('topic', 'this topic')}\""
                + (f" (hint: {hint[:120]})" if hint else "")
            ),
            "back": n.get("selected_text", "")[:2000],
            "topic": n.get("topic", ""),
            "fsrs": card.to_dict(),
            "due_ts": _card_due_ts(card),
            "created_at": time.time(),
        })
        created += 1

    # Drop cards whose mistake got resolved (learned — retire the card)
    resolved_ids = []
    async for m in mistakes_collection.find(
        {"student_id": student_id, "resolved": True}, {"mistake_id": 1}
    ).limit(500):
        resolved_ids.append(f"mistake:{m.get('mistake_id', '')}")
    removed = 0
    if resolved_ids:
        res = await flashcards_collection.delete_many(
            {"student_id": student_id, "source_id": {"$in": resolved_ids}}
        )
        removed = res.deleted_count

    total = await flashcards_collection.count_documents({"student_id": student_id})
    return {"created": created, "removed": removed, "total": total}


@router.get("/me/flashcards/due")
@limiter.limit("60/minute", key_func=user_key)
async def due_flashcards(
    request: Request,
    limit: int = Query(20, le=50),
    current_user: dict = Depends(require_role("student")),
):
    from database import flashcards_collection

    student_id = current_user["username"]
    now = time.time()
    cards = []
    async for c in flashcards_collection.find(
        {"student_id": student_id, "due_ts": {"$lte": now}},
        {"_id": 0, "fsrs": 0},
    ).sort("due_ts", 1).limit(limit):
        cards.append(c)

    total = await flashcards_collection.count_documents({"student_id": student_id})
    due_count = await flashcards_collection.count_documents(
        {"student_id": student_id, "due_ts": {"$lte": now}}
    )
    return {"cards": cards, "due_count": due_count, "total": total}


@router.post("/me/flashcards/{card_id}/grade")
async def grade_flashcard(
    card_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Grade a card: again | hard | good | easy → FSRS reschedules it."""
    from fsrs import Card, Rating
    from database import flashcards_collection

    rating_map = {
        "again": Rating.Again, "hard": Rating.Hard,
        "good": Rating.Good, "easy": Rating.Easy,
    }
    rating = rating_map.get((body.get("rating") or "").lower())
    if rating is None:
        raise HTTPException(400, "rating must be again|hard|good|easy")

    doc = await flashcards_collection.find_one(
        {"student_id": current_user["username"], "card_id": card_id}
    )
    if not doc:
        raise HTTPException(404, "Card not found")

    try:
        card = Card.from_dict(doc.get("fsrs") or {})
    except Exception:
        card = Card()

    card, _log = _flash_scheduler().review_card(card, rating)
    due_ts = _card_due_ts(card)

    await flashcards_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"fsrs": card.to_dict(), "due_ts": due_ts},
         "$inc": {"reviews": 1, "lapses": 1 if rating == Rating.Again else 0}},
    )
    return {"ok": True, "card_id": card_id, "next_due_ts": due_ts}


MINUTES_PER_NODE = 25  # avg time to learn one subtopic


@router.post("/me/exam-plan")
async def create_exam_plan(
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Build a day-by-day plan from remaining curriculum nodes to an exam date.
    Deterministic — no LLM. Last ~20% of days reserved for revision + a mock exam."""
    from datetime import date, timedelta
    from core.curriculum_engine import (
        normalize_subject, get_or_generate_tree, get_user_progress,
    )
    from database import exam_plans_collection

    student_id = current_user["username"]
    subject = (body.get("subject") or "").strip()
    if not subject:
        raise HTTPException(400, "subject is required")
    try:
        exam_date = date.fromisoformat(body.get("exam_date", ""))
    except ValueError:
        raise HTTPException(400, "exam_date must be YYYY-MM-DD")
    daily_minutes = min(max(int(body.get("daily_minutes") or 30), 15), 240)

    today = date.today()
    days_left = (exam_date - today).days
    if days_left < 1:
        raise HTTPException(400, "exam_date must be in the future")

    subject_id = normalize_subject(subject)
    tree_doc = await get_or_generate_tree(subject_id)
    if not tree_doc:
        raise HTTPException(404, "Subject not found")

    progress = await get_user_progress(student_id, subject_id)
    nodes = tree_doc.get("nodes", [])

    # Only what the student has actually LEARNED — revise done/in-progress leaves.
    # (Exam plan = revision of studied topics, not learning new ones.)
    max_level = max((n.get("level", 1) for n in nodes), default=1)
    leaves = [n for n in nodes if n.get("level") == max_level]
    remaining = [
        n for n in sorted(leaves, key=lambda x: x.get("order", 0))
        if progress.get(n["node_id"], "not_started") in ("done", "in_progress")
    ]

    # Day budget: reserve ~20% (min 1 if enough days) at the end for revision
    revision_days = max(1, days_left // 5) if days_left >= 5 else (1 if days_left >= 3 else 0)
    study_days = max(days_left - revision_days, 1)
    nodes_per_day = max(1, daily_minutes // MINUTES_PER_NODE)

    capacity = study_days * nodes_per_day
    feasible = len(remaining) <= capacity
    required_daily_minutes = None
    if not feasible:
        import math
        required_daily_minutes = math.ceil(len(remaining) * MINUTES_PER_NODE / study_days)

    # Assemble the calendar
    days = []
    node_i = 0
    for d in range(days_left):
        day_date = today + timedelta(days=d + 1)
        items = []
        if d < study_days and node_i < len(remaining):
            for _ in range(nodes_per_day):
                if node_i >= len(remaining):
                    break
                n = remaining[node_i]
                items.append({
                    "type": "revise",
                    "node_id": n["node_id"],
                    "title": n.get("title", n["node_id"]),
                    "est_minutes": MINUTES_PER_NODE,
                })
                node_i += 1
        if not items:
            if d == days_left - 1:
                items.append({
                    "type": "mock_exam",
                    "title": f"Mock exam: {subject} (exam mode, timed)",
                    "est_minutes": 30,
                })
            else:
                items.append({
                    "type": "revision",
                    "title": "Revision: flashcards + review due + retry mistakes",
                    "est_minutes": daily_minutes,
                })
        days.append({"date": day_date.isoformat(), "items": items, "done": False})

    plan = {
        "student_id": student_id,
        "subject": subject,
        "subject_id": subject_id,
        "exam_date": exam_date.isoformat(),
        "daily_minutes": daily_minutes,
        "days_left": days_left,
        "remaining_nodes": len(remaining),
        "feasible": feasible,
        "required_daily_minutes": required_daily_minutes,
        "days": days,
        "created_at": time.time(),
    }
    await exam_plans_collection.replace_one(
        {"student_id": student_id, "subject_id": subject_id}, plan, upsert=True
    )
    plan.pop("_id", None)
    return plan


@router.get("/me/exam-plan")
@limiter.limit("60/minute", key_func=user_key)
async def get_exam_plan(
    request: Request,
    subject: str = Query(...),
    current_user: dict = Depends(require_role("student")),
):
    """Stored plan + today's slice + on-track status (recomputed from live progress)."""
    from datetime import date
    from core.curriculum_engine import normalize_subject
    from database import exam_plans_collection

    student_id = current_user["username"]
    subject_id = normalize_subject(subject)
    plan = await exam_plans_collection.find_one(
        {"student_id": student_id, "subject_id": subject_id}, {"_id": 0}
    )
    if not plan:
        raise HTTPException(404, "No exam plan for this subject")

    today_iso = date.today().isoformat()
    today_items = next((d["items"] for d in plan["days"] if d["date"] == today_iso), [])

    # On-track: planned revision items scheduled up to today (revision is
    # self-paced — count scheduled vs the days elapsed, not mastery state)
    planned_so_far, done_so_far = 0, 0
    for d in plan["days"]:
        for it in d["items"]:
            if it["type"] == "revise":
                if d["date"] <= today_iso:
                    planned_so_far += 1
                    if d["date"] < today_iso:
                        done_so_far += 1

    days_to_exam = max((date.fromisoformat(plan["exam_date"]) - date.today()).days, 0)
    plan.update({
        "today": today_iso,
        "today_items": today_items,
        "days_to_exam": days_to_exam,
        "planned_so_far": planned_so_far,
        "done_so_far": done_so_far,
        "on_track": done_so_far >= planned_so_far,
        "behind_by": max(planned_so_far - done_so_far, 0),
    })
    return plan


@router.delete("/me/exam-plan")
async def delete_exam_plan(
    subject: str = Query(...),
    current_user: dict = Depends(require_role("student")),
):
    from core.curriculum_engine import normalize_subject
    from database import exam_plans_collection

    res = await exam_plans_collection.delete_one({
        "student_id": current_user["username"],
        "subject_id": normalize_subject(subject),
    })
    if res.deleted_count == 0:
        raise HTTPException(404, "No exam plan for this subject")
    return {"ok": True}


@router.get("/me/next-exam")
@limiter.limit("60/minute", key_func=user_key)
async def next_exam(
    request: Request,
    current_user: dict = Depends(require_role("student")),
):
    """The nearest upcoming exam (across all subjects) for a home countdown card.
    Fast — DB only, no LLM/KT. Returns has_exam=False when none is set."""
    from datetime import date
    from database import exam_plans_collection

    student_id = current_user["username"]
    today = date.today()
    today_iso = today.isoformat()

    best, best_days = None, None
    async for plan in exam_plans_collection.find({"student_id": student_id}, {"_id": 0}):
        try:
            d = (date.fromisoformat(plan["exam_date"]) - today).days
        except Exception:
            continue
        if d < 0:
            continue  # exam already passed
        if best_days is None or d < best_days:
            best, best_days = plan, d

    if not best:
        return {"has_exam": False}

    today_items = next(
        (dd["items"] for dd in best.get("days", []) if dd.get("date") == today_iso), []
    )

    planned_so_far, done_so_far = 0, 0
    for dd in best.get("days", []):
        for it in dd.get("items", []):
            if it.get("type") == "revise" and dd.get("date", "") <= today_iso:
                planned_so_far += 1
                if dd.get("date", "") < today_iso:
                    done_so_far += 1

    return {
        "has_exam": True,
        "subject": best.get("subject") or best.get("subject_id", ""),
        "subject_id": best.get("subject_id", ""),
        "exam_date": best.get("exam_date", ""),
        "days_to_exam": best_days,
        "today_count": len(today_items),
        "today_items": today_items,
        "on_track": done_so_far >= planned_so_far,
        "behind_by": max(planned_so_far - done_so_far, 0),
    }


@router.post("/me/cheatsheet")
@limiter.limit("6/minute", key_func=user_key)
async def make_cheatsheet(
    request: Request,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Build (or refresh) a one-page cheat sheet for a topic. Cached per (student, topic)."""
    from core.llm_utils import call_llm
    from core.llm_registry import build_models_cheap
    from database import cheatsheets_collection, feynman_attempts_collection

    student_id = current_user["username"]
    topic = (body.get("topic") or "").strip()
    refresh = bool(body.get("refresh"))
    if not topic or len(topic) > 200:
        raise HTTPException(400, "topic is required (max 200 chars)")
    topic_key = topic.lower()

    # Cheat-sheet generation version — bump to invalidate stale caches after a
    # generation/prompt fix (e.g. the off-topic-grounding bug).
    CHEATSHEET_VERSION = 2

    # Cached? (only serve a cache built with the current generation version)
    if not refresh:
        cached = await cheatsheets_collection.find_one(
            {"student_id": student_id, "topic_key": topic_key}, {"_id": 0}
        )
        if cached and cached.get("v") == CHEATSHEET_VERSION:
            return cached

    # (a) reference content for the topic.
    # min_score gate so an off-corpus topic isn't grounded on the nearest
    # unrelated chunks (which produced e.g. a Calculus sheet under the wrong title).
    grounding = ""
    try:
        from core.retriever import retrieve, format_grounding_context
        grounding = format_grounding_context(retrieve(topic, k=4, min_score=0.15))
    except Exception:
        grounding = ""

    # (b) the student's real mistakes on this topic
    gotchas_src = []
    async for m in mistakes_collection.find(
        {"student_id": student_id, "topic": {"$regex": f"^{re.escape(topic)}$", "$options": "i"}},
        {"_id": 0, "explanation": 1, "correct_answer": 1, "question": 1},
    ).sort("timestamp", -1).limit(8):
        piece = (m.get("explanation") or "") + " " + (m.get("correct_answer") or "")
        if piece.strip():
            gotchas_src.append(piece.strip()[:300])

    # (c) recent Feynman gaps/misconceptions for the topic
    try:
        async for a in feynman_attempts_collection.find(
            {"student_id": student_id, "topic": {"$regex": f"^{re.escape(topic)}$", "$options": "i"}},
            {"_id": 0, "gaps": 1, "misconceptions": 1},
        ).sort("created_at", -1).limit(5):
            for g in (a.get("gaps") or []) + (a.get("misconceptions") or []):
                if g:
                    gotchas_src.append(str(g)[:300])
    except Exception:
        pass

    from utils.prompt_safety import wrap_student_text
    personal = wrap_student_text("\n".join(gotchas_src[:12]) or "(no personal mistakes recorded yet)", "student_mistakes")

    grounding_block = (
        f"Reference material (use ONLY if it is actually about \"{topic}\"; "
        f"ignore it otherwise):\n{grounding}\n\n" if grounding else ""
    )
    prompt = (
        f"Build a ONE-PAGE exam cheat sheet for the topic: \"{topic}\".\n\n"
        f"{grounding_block}"
        f"The cheat sheet MUST be about \"{topic}\" specifically — do not drift to a "
        f"different subject. If unsure of the exact syllabus, give the standard "
        f"exam points for \"{topic}\".\n"
        f"The student's own recorded mistakes and gaps on this topic:\n{personal}\n\n"
        "Rules: concise, exam-focused, fits one page. Formulas in LaTeX ($...$). "
        "The 'your_gotchas' list MUST be built ONLY from the student's real mistakes above "
        "(phrase each as a short reminder like 'You keep forgetting X — remember Y'); if there are "
        "none, return an empty list. Do not invent gotchas.\n"
        'Return ONLY JSON: {"title": "...", '
        '"key_formulas": ["..."], '
        '"key_definitions": [{"term": "...", "definition": "..."}], '
        '"must_remember": ["...3-5 bullets..."], '
        '"your_gotchas": ["...from the student\'s mistakes only..."], '
        '"quick_examples": ["...1-2 tiny worked examples..."]}'
    )
    result = await call_llm(
        build_models_cheap(), prompt, required_key="title",
        engine_name="cheatsheet", prompt_version="v2",
    )
    if not result:
        raise HTTPException(502, "Couldn't build the cheat sheet — try again")

    # Cap list sizes so it stays one page
    def _cap(v, n):
        return (v or [])[:n] if isinstance(v, list) else []
    sheet = {
        "student_id": student_id,
        "topic": topic,
        "topic_key": topic_key,
        "title": str(result.get("title", topic))[:120],
        "key_formulas": [str(x)[:200] for x in _cap(result.get("key_formulas"), 8)],
        "key_definitions": [
            {"term": str(d.get("term", ""))[:80], "definition": str(d.get("definition", ""))[:240]}
            for d in _cap(result.get("key_definitions"), 8) if isinstance(d, dict)
        ],
        "must_remember": [str(x)[:200] for x in _cap(result.get("must_remember"), 6)],
        "your_gotchas": [str(x)[:240] for x in _cap(result.get("your_gotchas"), 6)],
        "quick_examples": [str(x)[:400] for x in _cap(result.get("quick_examples"), 3)],
        "created_at": time.time(),
        "v": CHEATSHEET_VERSION,
    }
    await cheatsheets_collection.replace_one(
        {"student_id": student_id, "topic_key": topic_key}, sheet, upsert=True
    )
    sheet.pop("_id", None)
    return sheet


@router.get("/me/cheatsheet/{topic}.pdf")
@limiter.limit("20/minute", key_func=user_key)
async def cheatsheet_pdf(
    request: Request,
    topic: str,
    current_user: dict = Depends(require_role("student")),
):
    from fastapi import Response
    from database import cheatsheets_collection
    from core.report_builder import build_cheatsheet_pdf

    sheet = await cheatsheets_collection.find_one(
        {"student_id": current_user["username"], "topic_key": topic.lower()}, {"_id": 0}
    )
    if not sheet:
        raise HTTPException(404, "Generate the cheat sheet first")
    pdf = build_cheatsheet_pdf(current_user["username"], sheet)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="cheatsheet_{topic[:30]}.pdf"'})


READY_STRONG = 0.75


@router.get("/me/exam-readiness/{subject}")
@limiter.limit("30/minute", key_func=user_key)
async def exam_readiness(
    request: Request,
    subject: str,
    current_user: dict = Depends(require_role("student")),
):
    """Readiness % for a subject from KT mastery over studied topics, plus the
    weakest topics to focus on. No LLM — instant, honest."""
    from serve import tutor
    from core.curriculum_engine import (
        normalize_subject, get_or_generate_tree, get_user_progress,
    )

    student_id = current_user["username"]
    subject_id = normalize_subject(subject)
    tree = await get_or_generate_tree(subject_id)
    if not tree:
        raise HTTPException(404, "Subject not found")

    nodes = tree.get("nodes", [])
    max_level = max((n.get("level", 1) for n in nodes), default=1)
    leaves = [n for n in nodes if n.get("level") == max_level and n.get("title")]
    total_topics = len(leaves)
    if total_topics == 0:
        raise HTTPException(400, "No topics in this subject")

    progress = await get_user_progress(student_id, subject_id)

    async def mastery_of(name):
        try:
            r = await tutor.kt.predict_mastery(student_id, name, heuristic_fallback=0.0)
            return float(r.get("p_correct", 0.0))
        except Exception:
            return 0.0

    per_topic = []
    studied = 0
    mastery_sum = 0.0
    for n in leaves:
        title = n["title"]
        status = progress.get(n["node_id"], "not_started")
        m = await mastery_of(title)
        is_studied = status in ("done", "in_progress") or m > 0.05
        if is_studied:
            studied += 1
        mastery_sum += m  # not-started contribute 0 → readiness reflects coverage too
        per_topic.append({"topic": title, "mastery": round(m, 2), "studied": is_studied, "status": status})

    # Readiness = average mastery across ALL exam topics (unstudied = 0 → honest)
    readiness = round(mastery_sum / total_topics * 100)
    coverage = round(studied / total_topics * 100)

    weak = sorted(
        [t for t in per_topic if t["mastery"] < READY_STRONG],
        key=lambda t: t["mastery"],
    )[:5]

    if readiness >= 75:
        verdict, tone = "You're exam-ready — polish the weak spots below.", "strong"
    elif readiness >= 50:
        verdict, tone = "Almost there — focus on your weak topics to cross the line.", "medium"
    else:
        verdict, tone = "Keep going — a lot of the syllabus still needs work.", "weak"

    return {
        "subject": subject,
        "readiness_pct": readiness,
        "coverage_pct": coverage,
        "total_topics": total_topics,
        "studied_topics": studied,
        "tone": tone,
        "verdict": verdict,
        "weak_topics": weak,
    }


@router.post("/me/recap")
@limiter.limit("15/minute", key_func=user_key)
async def quick_recap(
    request: Request,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """A ~60-second recap of a topic: 3-5 key points + 1-line 'the big idea'."""
    from core.llm_utils import call_llm
    from core.llm_registry import build_models_cheap
    from database import cheatsheets_collection  # reuse a lightweight cache collection

    topic = (body.get("topic") or "").strip()
    if not topic or len(topic) > 200:
        raise HTTPException(400, "topic is required (max 200 chars)")

    # Recap generation version — bump to invalidate stale caches after a
    # generation/prompt fix (e.g. the off-topic-grounding bug).
    RECAP_VERSION = 2

    # Day-cached recap (stored on a recap doc keyed by student+topic)
    from database import db as _db
    recap_col = _db["recaps"]
    cached = await recap_col.find_one(
        {"student_id": current_user["username"], "topic_key": topic.lower()}, {"_id": 0}
    )
    if (
        cached
        and cached.get("v") == RECAP_VERSION
        and (time.time() - cached.get("created_at", 0) < 86400)
    ):
        return cached

    grounding = ""
    try:
        from core.retriever import retrieve, format_grounding_context
        # min_score gate: only ground on chunks genuinely about this topic.
        # Without it, off-corpus topics (e.g. "History Of Computing") were
        # grounded on the nearest unrelated Calculus chunks and the recap came
        # back as Calculus under the wrong title.
        grounding = format_grounding_context(retrieve(topic, k=3, min_score=0.15))
    except Exception:
        grounding = ""

    grounding_block = (
        f"Reference material (use ONLY if it is actually about \"{topic}\"; "
        f"ignore it otherwise):\n{grounding}\n\n" if grounding else ""
    )
    prompt = (
        f"Give a 60-second REVISION recap of the topic: \"{topic}\".\n"
        f"{grounding_block}"
        f"The recap MUST be about \"{topic}\" specifically — do not drift to a "
        "different subject. If you are unsure of the exact syllabus, give the "
        f"standard revision points for \"{topic}\".\n"
        "Keep it tight — this is a quick refresher before deeper study, not a lesson. "
        "Use LaTeX ($...$) for any math.\n"
        'Return ONLY JSON: {"big_idea": "one punchy sentence — the core of the topic", '
        '"key_points": ["3-5 short bullets a student must recall"], '
        '"common_trap": "one thing students often get wrong (one line)"}'
    )
    result = await call_llm(
        build_models_cheap(), prompt, required_key="big_idea",
        engine_name="quick_recap", prompt_version="v2",
    )
    if not result:
        raise HTTPException(502, "Couldn't build a recap — try again")

    recap = {
        "student_id": current_user["username"],
        "topic": topic,
        "topic_key": topic.lower(),
        "big_idea": str(result.get("big_idea", ""))[:400],
        "key_points": [str(x)[:200] for x in (result.get("key_points") or [])[:5]],
        "common_trap": str(result.get("common_trap", ""))[:300],
        "created_at": time.time(),
        "v": RECAP_VERSION,
    }
    await recap_col.replace_one(
        {"student_id": current_user["username"], "topic_key": topic.lower()}, recap, upsert=True
    )
    recap.pop("_id", None)
    return recap


@router.post("/me/feynman/evaluate")
@limiter.limit("10/minute", key_func=user_key)
async def evaluate_feynman(
    request: Request,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """
    Student explains a topic. AI grades: score, verdict, gaps, misconceptions.
    Misconceptions auto-inserted into mistakes notebook.
    """
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from utils.prompt_safety import wrap_student_text, looks_like_injection
    from database import feynman_attempts_collection, user_materials_collection

    student_id = current_user["username"]
    topic = (body.get("topic") or "").strip()
    explanation = (body.get("explanation") or "").strip()
    material_id = body.get("material_id")

    if not topic or len(topic) > 200:
        raise HTTPException(400, "topic is required (max 200 chars)")
    if len(explanation) < 30:
        raise HTTPException(400, "Explanation too short — write at least 30 characters to get meaningful feedback.")
    if len(explanation) > 6000:
        raise HTTPException(400, "Explanation too long (max 6000 chars)")

    if looks_like_injection(explanation):
        logger.warning("possible injection in feynman from %s", student_id)

    # Optional grounding from uploaded material
    grounding_block = ""
    if material_id:
        from core.user_materials import retrieve_chunks, format_material_grounding
        mat_doc = await user_materials_collection.find_one({
            "student_id": student_id, "material_id": material_id,
        })
        if mat_doc:
            chunks = mat_doc.get("chunks", [])
            idf = mat_doc.get("idf", {})
            relevant = retrieve_chunks(topic, chunks, idf, top_k=10)
            grounding_block = format_material_grounding(relevant, mat_doc.get("title", "chapter"))

    safe_explanation = wrap_student_text(explanation, "student_explanation")

    prompt = f"""You are a kind but honest teacher grading a student's explain-back attempt.

Topic: {topic}
{grounding_block}

The student's explanation:
{safe_explanation}

Grade this explanation thoroughly:
1. What was CORRECT and well-explained
2. What important concepts were SKIPPED (the "why", conditions, edge cases they missed)
3. What was actually WRONG (misconceptions)
4. A challenge question probing their weakest spot

Return strict JSON:
{{
  "score": <0-100>,
  "verdict": "solid|partial|shaky",
  "correctness": <0-10>,
  "completeness": <0-10>,
  "clarity": <0-10>,
  "what_was_good": "...",
  "gaps": ["gap1 description", "gap2 description", ...],
  "misconceptions": ["misconception1", "misconception2", ...],
  "challenge_question": "..."
}}

Be specific — don't say "you missed some things." Say WHAT they missed."""

    result = await call_llm(
        build_models(), prompt, required_key="score",
        engine_name="feynman_evaluate", prompt_version="v1",
    )
    if not result:
        raise HTTPException(502, "Failed to evaluate explanation — try again")

    # Ensure correct types
    result["score"] = int(result.get("score", 50))
    result["verdict"] = result.get("verdict", "partial")
    result["gaps"] = result.get("gaps", [])
    result["misconceptions"] = result.get("misconceptions", [])

    # Insert misconceptions into mistakes notebook
    misconceptions_added = 0
    if result["misconceptions"]:
        import uuid
        for mc in result["misconceptions"][:5]:
            await mistakes_collection.insert_one({
                "student_id": student_id,
                "mistake_id": str(uuid.uuid4())[:12],
                "topic": topic,
                "question": f"[Feynman] You said: {mc}",
                "student_answer": explanation[:200],
                "correct_answer": f"Misconception identified during explain-back",
                "explanation": mc,
                "concept": topic,
                "source": "feynman",
                "resolved": False,
                "timestamp": time.time(),
            })
            misconceptions_added += 1

    # Persist attempt
    attempt = {
        "student_id": student_id,
        "topic": topic,
        "material_id": material_id,
        "score": result["score"],
        "verdict": result["verdict"],
        "correctness": result.get("correctness"),
        "completeness": result.get("completeness"),
        "clarity": result.get("clarity"),
        "gaps": result["gaps"],
        "misconceptions": result["misconceptions"],
        "challenge_question": result.get("challenge_question", ""),
        "created_at": time.time(),
    }
    await feynman_attempts_collection.insert_one(attempt)

    result["misconceptions_added"] = misconceptions_added
    return result


@router.get("/me/feynman/history")
@limiter.limit("60/minute", key_func=user_key)
async def feynman_history(
    request: Request,
    topic: str = Query(None),
    limit: int = Query(20, le=50),
    current_user: dict = Depends(require_role("student")),
):
    """List past Feynman attempts, optionally filtered by topic."""
    from database import feynman_attempts_collection

    query = {"student_id": current_user["username"]}
    if topic:
        query["topic"] = safe_topic_filter(topic)

    items = []
    async for doc in feynman_attempts_collection.find(
        query, {"_id": 0, "student_id": 0}
    ).sort("created_at", -1).limit(limit):
        items.append(doc)

    return {"attempts": items, "total": len(items)}


@router.post("/me/cheatsheet/smart")
@limiter.limit("10/minute", key_func=user_key)
async def generate_cheatsheet(
    request: Request,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
    _budget: dict = Depends(check_llm_budget),
):
    """Generate a one-page smart cheat sheet: generic half + personal gotchas."""
    from core.llm_utils import call_llm
    from core.llm_registry import build_models
    from utils.prompt_safety import wrap_student_text
    from database import cheatsheets_collection, feynman_attempts_collection, user_materials_collection

    student_id = current_user["username"]
    topic = (body.get("topic") or "").strip()
    material_id = body.get("material_id")

    if not topic or len(topic) > 200:
        raise HTTPException(400, "topic is required (max 200 chars)")

    # 1) Gather reference content
    grounding = ""
    if material_id:
        from core.user_materials import retrieve_chunks, format_material_grounding
        mat = await user_materials_collection.find_one({
            "student_id": student_id, "material_id": material_id,
        })
        if mat:
            chunks = mat.get("chunks", [])
            idf = mat.get("idf", {})
            relevant = retrieve_chunks(topic, chunks, idf, top_k=10)
            grounding = format_material_grounding(relevant, mat.get("title", ""))

    # 2) Gather student's mistakes for this topic
    mistakes_text = ""
    mistake_items = []
    async for m in mistakes_collection.find(
        {"student_id": student_id, "topic": safe_topic_filter(topic)},
        {"_id": 0, "question": 1, "correct_answer": 1, "explanation": 1, "resolved": 1},
    ).sort("timestamp", -1).limit(20):
        mistake_items.append(m)

    if mistake_items:
        mistakes_text = "\n".join(
            f"- Q: {m.get('question', '')[:150]} | Correct: {m.get('correct_answer', '')[:150]}"
            f"{' | Why: ' + m.get('explanation', '')[:150] if m.get('explanation') else ''}"
            f" [{'resolved' if m.get('resolved') else 'unresolved'}]"
            for m in mistake_items
        )

    # 3) Gather Feynman gaps
    feynman_text = ""
    feynman_items = []
    async for f in feynman_attempts_collection.find(
        {"student_id": student_id, "topic": safe_topic_filter(topic)},
        {"_id": 0, "gaps": 1, "misconceptions": 1, "score": 1},
    ).sort("created_at", -1).limit(5):
        feynman_items.append(f)

    if feynman_items:
        gaps_flat = []
        miscon_flat = []
        for f in feynman_items:
            gaps_flat.extend(f.get("gaps", []))
            miscon_flat.extend(f.get("misconceptions", []))
        if gaps_flat or miscon_flat:
            feynman_text = "Gaps: " + "; ".join(gaps_flat[:8])
            if miscon_flat:
                feynman_text += "\nMisconceptions: " + "; ".join(miscon_flat[:5])

    # 4) Build prompt
    personal_section = ""
    if mistakes_text or feynman_text:
        personal_section = f"""
<student_mistakes_and_gaps>
{wrap_student_text(mistakes_text, 'mistakes') if mistakes_text else '(no mistakes yet)'}
{wrap_student_text(feynman_text, 'feynman_gaps') if feynman_text else ''}
</student_mistakes_and_gaps>"""

    prompt = f"""Create a ONE-PAGE smart cheat sheet for the topic: {topic}

{grounding}
{personal_section}

The cheat sheet has two halves:
1. GENERIC: key formulas, definitions, must-remember points from the topic
2. PERSONAL: "Your Gotchas" — specific warnings drawn ONLY from the student's real mistakes
   and gaps listed above. If no mistakes/gaps exist, say "No personal gotchas yet — take a quiz first."
   NEVER invent gotchas.

Return strict JSON:
{{
  "title": "{topic} — Quick Reference",
  "key_formulas": ["formula1 (LaTeX ok)", "formula2", ...],
  "key_definitions": [{{"term": "...", "definition": "..."}}, ...],
  "must_remember": ["point1", "point2", "point3"],
  "your_gotchas": ["You confused X with Y — remember Z", ...],
  "quick_examples": [{{"problem": "...", "solution": "..."}}, ...]
}}

CONSTRAINTS:
- key_formulas: max 8 items
- key_definitions: max 8 items
- must_remember: 3-5 items
- your_gotchas: max 5 items (ONLY from real student data, never invented)
- quick_examples: 1-2 items
Everything must genuinely fit on ONE printed page."""

    result = await call_llm(
        build_models(), prompt, required_key="title",
        engine_name="cheatsheet", prompt_version="v1",
    )
    if not result:
        raise HTTPException(502, "Failed to generate cheat sheet — try again")

    # Cache. topic_key is a normalized (lower-cased) form used for exact
    # equality lookups — no user-controlled regex ever hits the DB (SEC-2).
    sheet_doc = {
        "student_id": student_id,
        "topic": topic,
        "topic_key": exact_topic_value(topic),
        "material_id": material_id,
        "sheet": result,
        "created_at": time.time(),
    }
    await cheatsheets_collection.replace_one(
        {"student_id": student_id, "topic_key": exact_topic_value(topic)},
        sheet_doc, upsert=True,
    )

    return result


@router.get("/me/cheatsheet")
@limiter.limit("60/minute", key_func=user_key)
async def get_cheatsheet(
    request: Request,
    topic: str = Query(...),
    current_user: dict = Depends(require_role("student")),
):
    """Get cached cheat sheet for a topic."""
    from database import cheatsheets_collection

    doc = await cheatsheets_collection.find_one(
        {"student_id": current_user["username"], "topic_key": exact_topic_value(topic)},
        {"_id": 0, "student_id": 0},
    )
    if not doc:
        raise HTTPException(404, "No cheat sheet for this topic. Generate one first.")
    return doc.get("sheet", doc)


@router.get("/me/cheatsheet/{topic_slug}/pdf")
@limiter.limit("60/minute", key_func=user_key)
async def cheatsheet_pdf(
    request: Request,
    topic_slug: str,
    current_user: dict = Depends(require_role("student")),
):
    """Render cheat sheet as downloadable PDF."""
    from fastapi.responses import Response
    from database import cheatsheets_collection

    topic = topic_slug.replace("-", " ").replace("_", " ")
    doc = await cheatsheets_collection.find_one(
        {"student_id": current_user["username"], "topic_key": exact_topic_value(topic)},
        {"_id": 0},
    )
    if not doc or not doc.get("sheet"):
        raise HTTPException(404, "No cheat sheet found. Generate one first.")

    sheet = doc["sheet"]

    try:
        pdf_bytes = _render_cheatsheet_pdf(sheet)
    except ImportError:
        # Fallback: plain text
        text = _render_cheatsheet_text(sheet)
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{topic}_cheatsheet.txt"'},
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{topic}_cheatsheet.pdf"'},
    )


def _render_cheatsheet_text(sheet: dict) -> str:
    """Plain text fallback for cheat sheet."""
    lines = [f"{'=' * 60}", f"  {sheet.get('title', 'Cheat Sheet')}", f"{'=' * 60}", ""]

    if sheet.get("key_formulas"):
        lines.append("KEY FORMULAS:")
        for f in sheet["key_formulas"]:
            lines.append(f"  • {f}")
        lines.append("")

    if sheet.get("key_definitions"):
        lines.append("KEY DEFINITIONS:")
        for d in sheet["key_definitions"]:
            term = d.get("term", "") if isinstance(d, dict) else str(d)
            defn = d.get("definition", "") if isinstance(d, dict) else ""
            lines.append(f"  • {term}: {defn}")
        lines.append("")

    if sheet.get("must_remember"):
        lines.append("MUST REMEMBER:")
        for m in sheet["must_remember"]:
            lines.append(f"  ★ {m}")
        lines.append("")

    if sheet.get("your_gotchas"):
        lines.append("YOUR PERSONAL GOTCHAS:")
        for g in sheet["your_gotchas"]:
            lines.append(f"  ⚠ {g}")
        lines.append("")

    if sheet.get("quick_examples"):
        lines.append("QUICK EXAMPLES:")
        for ex in sheet["quick_examples"]:
            if isinstance(ex, dict):
                lines.append(f"  Problem: {ex.get('problem', '')}")
                lines.append(f"  Solution: {ex.get('solution', '')}")
            else:
                lines.append(f"  • {ex}")
            lines.append("")

    return "\n".join(lines)


def _render_cheatsheet_pdf(sheet: dict) -> bytes:
    """Render compact PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm,
                            leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("CheatTitle", parent=styles["Heading1"], fontSize=14,
                                  spaceAfter=6, textColor=HexColor("#1e40af"))
    section_style = ParagraphStyle("CheatSection", parent=styles["Heading3"], fontSize=10,
                                    spaceBefore=6, spaceAfter=3, textColor=HexColor("#4338ca"))
    body_style = ParagraphStyle("CheatBody", parent=styles["Normal"], fontSize=8,
                                 leading=10, spaceAfter=2)
    gotcha_style = ParagraphStyle("CheatGotcha", parent=body_style,
                                   textColor=HexColor("#dc2626"), backColor=HexColor("#fef2f2"))

    story = [Paragraph(sheet.get("title", "Cheat Sheet"), title_style)]

    if sheet.get("key_formulas"):
        story.append(Paragraph("Key Formulas", section_style))
        for f in sheet["key_formulas"]:
            story.append(Paragraph(f"• {f}", body_style))

    if sheet.get("key_definitions"):
        story.append(Paragraph("Key Definitions", section_style))
        for d in sheet["key_definitions"]:
            if isinstance(d, dict):
                story.append(Paragraph(f"<b>{d.get('term', '')}</b>: {d.get('definition', '')}", body_style))
            else:
                story.append(Paragraph(f"• {d}", body_style))

    if sheet.get("must_remember"):
        story.append(Paragraph("Must Remember", section_style))
        for m in sheet["must_remember"]:
            story.append(Paragraph(f"★ {m}", body_style))

    if sheet.get("your_gotchas"):
        story.append(Paragraph("Your Personal Gotchas", section_style))
        for g in sheet["your_gotchas"]:
            story.append(Paragraph(f"⚠ {g}", gotcha_style))

    if sheet.get("quick_examples"):
        story.append(Paragraph("Quick Examples", section_style))
        for ex in sheet["quick_examples"]:
            if isinstance(ex, dict):
                story.append(Paragraph(f"<b>Q:</b> {ex.get('problem', '')}", body_style))
                story.append(Paragraph(f"<b>A:</b> {ex.get('solution', '')}", body_style))
                story.append(Spacer(1, 2*mm))

    doc.build(story)
    return buf.getvalue()
