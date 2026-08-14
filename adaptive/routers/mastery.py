"""
Mastery — progress, knowledge graph, challenges, learning path, today plan,
mastery history, progress snapshot, and PDF progress reports.
Extracted from serve.py.

serve.py re-exports get_progress_snapshot so extras' daily-session still resolves.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from adaptive.dependencies import get_current_user, require_role, require_self_or_guardian
from adaptive.runtime import (
    tutor, graph_engine, review_engine, study_planner, challenge_engine,
    _require_feature,
)
from adaptive.config.features import CERTIFICATES_ENABLED
from adaptive.utils.tone import get_tone_directive
from adaptive.utils.language import get_language_directive
from adaptive.core.learning_path import build_path, annotate_path, create_path_document
from adaptive.api.schemas import (
    StudentProgress, KnowledgeGraphResponse, ProgressiveChallengeResponse,
    SetGoalRequest, LearningPathResponse, TodayPlanResponse,
    MasteryDashboardResponse, MasteryOverviewCounts, MasterySnapshot, TopicMasteryHistory,
)
from adaptive.database import (
    student_states_collection, users_collection, learning_paths_collection,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mastery"])


# ── Extracted mastery / progress / learning-path routes (verbatim from serve.py) ──
@router.get("/progress/{student_id}", response_model=StudentProgress)
async def get_progress(student_id: str, current_user: dict = Depends(require_self_or_guardian("student_id"))):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")
    state = await student_states_collection.find_one(
        {"student_id": student_id},
        {"_id": 0}
    )

    if not state:
        return {
            "student_id": student_id,
            "topics": {},
            "total_questions": 0,
            "accuracy": 0
        }

    total = state.get("total_questions", 0)
    correct = state.get("correct_answers", 0)

    accuracy = (correct / total * 100) if total > 0 else 0

    return {
        "student_id": student_id,
        "topics": state.get("topic_proficiency", {}),
        "total_questions": total,
        "accuracy": round(accuracy, 2)
    }


@router.get("/knowledge-graph/{student_id}", response_model=KnowledgeGraphResponse)
async def knowledge_graph(student_id: str, current_user: dict = Depends(require_self_or_guardian("student_id"))):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        raise HTTPException(404, "Student not found")

    topics_with_mastery = [
        {"topic": topic, "mastery": round(concept.knowledge, 2)}
        for topic, concept in student.concepts.items()
    ]

    if not topics_with_mastery:
        raise HTTPException(404, "No topics found for this student")

    result = await graph_engine.generate_graph(topics_with_mastery)

    edges = []
    for e in result.get("edges", []):
        edges.append({
            "source": e.get("from", e.get("source", "")),
            "target": e.get("to", e.get("target", "")),
            "strength": e.get("strength", "weak"),
            "reason": e.get("reason", "")
        })

    return {
        "nodes": result.get("nodes", topics_with_mastery),
        "edges": edges,
        "weak_links": result.get("weak_links", []),
        "suggested_focus": result.get("suggested_focus", "")
    }


@router.get("/challenge/{student_id}", response_model=ProgressiveChallengeResponse)
async def progressive_challenge(
    student_id: str,
    difficulty: str = "medium",
    current_user: dict = Depends(require_self_or_guardian("student_id")),
):
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    if difficulty not in ("easy", "medium", "hard"):
        raise HTTPException(400, "Difficulty must be easy, medium, or hard")

    student = await tutor.sessions.get_student(student_id)
    if student is None:
        raise HTTPException(404, "Student not found")

    concept = student.get_current_concept()
    tone = get_tone_directive(student)
    user_doc = await users_collection.find_one({"username": student_id})
    lang_dir = get_language_directive((user_doc or {}).get("preferences"))

    result = await challenge_engine.generate_challenge(
        topic=student.current_topic,
        mastery=concept.concept_mastery,
        difficulty=difficulty,
        tone_directive=tone,
        language_directive=lang_dir,
    )

    return result


@router.post("/me/path", response_model=LearningPathResponse)
async def set_learning_path(
    payload: SetGoalRequest,
    current_user: dict = Depends(require_role("student")),
):
    """Set a learning goal and build an ordered prerequisite path."""
    student_id = current_user["username"]
    goal = payload.goal.strip().lower()

    # Build the path via prerequisite engine
    path_nodes = await build_path(goal, max_depth=3)

    # Save to DB (upsert per student)
    doc = create_path_document(student_id, goal, path_nodes)
    await learning_paths_collection.update_one(
        {"student_id": student_id},
        {"$set": doc},
        upsert=True,
    )

    # Also save goal on user doc
    await users_collection.update_one(
        {"username": student_id},
        {"$set": {"learning_goal": goal}},
    )

    # Annotate with mastery
    student = await tutor.sessions.get_student(student_id)
    concepts = student.concepts if student else {}
    annotated = annotate_path(path_nodes, concepts)

    current_topic = next((n["topic"] for n in annotated if n["state"] == "current"), None)
    mastered_count = sum(1 for n in annotated if n["state"] == "mastered")
    progress_pct = round(mastered_count / max(len(annotated), 1) * 100, 1)

    return {
        "goal": goal,
        "path": annotated,
        "current_topic": current_topic,
        "progress_pct": progress_pct,
    }


@router.get("/me/path", response_model=LearningPathResponse)
async def get_learning_path(
    current_user: dict = Depends(require_role("student")),
):
    """Get the student's current learning path with live mastery annotations."""
    student_id = current_user["username"]

    path_doc = await learning_paths_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if not path_doc:
        return {
            "goal": "",
            "path": [],
            "current_topic": None,
            "progress_pct": 0.0,
        }

    student = await tutor.sessions.get_student(student_id)
    concepts = student.concepts if student else {}
    annotated = annotate_path(path_doc["path"], concepts)

    current_topic = next((n["topic"] for n in annotated if n["state"] == "current"), None)
    mastered_count = sum(1 for n in annotated if n["state"] == "mastered")
    progress_pct = round(mastered_count / max(len(annotated), 1) * 100, 1)

    return {
        "goal": path_doc["goal"],
        "path": annotated,
        "current_topic": current_topic,
        "progress_pct": progress_pct,
    }


@router.get("/me/today", response_model=TodayPlanResponse)
async def get_today_plan(
    current_user: dict = Depends(require_role("student")),
):
    """
    Build a 1-3 task daily plan combining:
    - Next topic from learning path (if exists)
    - Due FSRS reviews
    - Weak area practice
    """
    student_id = current_user["username"]

    student = await tutor.sessions.get_student(student_id)
    tasks = []

    # 1. Check for due FSRS reviews
    if student and student.concepts:
        due_topics = review_engine.get_due_topics(student, threshold=0.85)
        for dt in due_topics[:1]:  # At most 1 review task
            tasks.append({
                "type": "review",
                "topic": dt["topic"],
                "reason": f"Retention dropped to {dt['retention_estimate']:.0%} — review to keep it fresh",
                "duration_min": 10,
                "mastery": dt["mastery"],
            })

    # 2. Check learning path for next topic
    has_path = False
    path_doc = await learning_paths_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if path_doc and path_doc.get("path"):
        has_path = True
        concepts = student.concepts if student else {}
        annotated = annotate_path(path_doc["path"], concepts)
        current_node = next((n for n in annotated if n["state"] == "current"), None)
        if current_node:
            tasks.append({
                "type": "learn",
                "topic": current_node["topic"],
                "reason": f"Next step toward your goal: {path_doc['goal']}",
                "duration_min": 15,
                "mastery": current_node["mastery"],
            })

    # 3. Practice a weak area (not already in tasks)
    if student and student.concepts and len(tasks) < 3:
        task_topics = {t["topic"] for t in tasks}
        weak = [
            (topic, c.concept_mastery)
            for topic, c in student.concepts.items()
            if c.concept_mastery < 0.5 and topic not in task_topics
        ]
        weak.sort(key=lambda x: x[1])
        if weak:
            topic, mastery = weak[0]
            tasks.append({
                "type": "practice",
                "topic": topic,
                "reason": f"Mastery is only {mastery:.0%} — extra practice will help",
                "duration_min": 10,
                "mastery": round(mastery, 3),
            })

    if not tasks:
        message = "Nothing specific today — pick a topic and start learning!"
    elif len(tasks) == 1:
        message = f"Focus on: {tasks[0]['topic']}"
    else:
        message = f"{len(tasks)} tasks for today — start with {tasks[0]['topic']}"

    return {
        "tasks": tasks,
        "message": message,
        "has_path": has_path,
    }


@router.get("/me/mastery-history", response_model=MasteryDashboardResponse)
async def mastery_history(current_user: dict = Depends(get_current_user)):
    """Aggregate interaction log into per-topic mastery snapshots over time."""
    from database import interactions_collection, student_states_collection
    from collections import defaultdict

    username = current_user["username"]

    # Pull all interactions for this student, sorted by time
    cursor = interactions_collection.find(
        {"student_id": username}
    ).sort("timestamp", 1)

    interactions = await cursor.to_list(length=5000)

    # Build rolling mastery per topic using exponential moving average
    topic_snapshots = defaultdict(list)  # topic -> [(date_str, mastery)]
    topic_running = defaultdict(lambda: {"correct": 0, "total": 0})

    for ix in interactions:
        topic = ix.get("skill_id", "Unknown")
        correct = ix.get("correct", False)
        ts = ix.get("timestamp")

        topic_running[topic]["total"] += 1
        if correct:
            topic_running[topic]["correct"] += 1

        r = topic_running[topic]
        mastery = r["correct"] / r["total"] if r["total"] > 0 else 0.0

        date_str = ""
        if isinstance(ts, (int, float)):
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        elif isinstance(ts, datetime):
            date_str = ts.strftime("%Y-%m-%d")
        elif isinstance(ts, str):
            date_str = ts[:10]

        # Keep latest snapshot per day per topic
        if topic_snapshots[topic] and topic_snapshots[topic][-1][0] == date_str:
            topic_snapshots[topic][-1] = (date_str, mastery)
        else:
            topic_snapshots[topic].append((date_str, mastery))

    # Get current mastery from student concepts (BKT/KT)
    student_doc = await student_states_collection.find_one({"student_id": username})
    concepts = {}
    if student_doc and "concepts" in student_doc:
        for name, c in student_doc["concepts"].items():
            if isinstance(c, dict):
                concepts[name] = c.get("mastery", 0.0)
            else:
                concepts[name] = getattr(c, "mastery", 0.0)

    # All known topics = union of interaction topics + concept topics
    all_topics = set(topic_snapshots.keys()) | set(concepts.keys())

    # Build history list
    history = []
    mastered_count = 0
    in_progress_count = 0
    not_started_count = 0

    for topic in sorted(all_topics):
        current = concepts.get(topic, 0.0)
        if topic in topic_running:
            running = topic_running[topic]
            current = max(current, running["correct"] / running["total"] if running["total"] > 0 else 0.0)

        snapshots = [
            MasterySnapshot(date=d, mastery=round(m, 3))
            for d, m in topic_snapshots.get(topic, [])
        ]

        history.append(TopicMasteryHistory(
            topic=topic,
            current_mastery=round(current, 3),
            snapshots=snapshots,
        ))

        if current >= 0.8:
            mastered_count += 1
        elif topic in topic_running and topic_running[topic]["total"] > 0:
            in_progress_count += 1
        else:
            not_started_count += 1

    # Overall trend: per topic, compare its EARLIEST vs LATEST snapshot mastery
    # (measures change over time), then average those deltas across topics.
    # The old version compared alphabetically-sorted topics to each other, which
    # measured nothing meaningful.
    deltas = []
    for h in history:
        if h.snapshots and len(h.snapshots) >= 2:
            deltas.append(h.snapshots[-1].mastery - h.snapshots[0].mastery)
    if deltas:
        mean_delta = sum(deltas) / len(deltas)
        if mean_delta > 0.05:
            trend = "improving"
        elif mean_delta < -0.05:
            trend = "declining"
        else:
            trend = "steady"
    else:
        trend = "steady"

    return MasteryDashboardResponse(
        counts=MasteryOverviewCounts(
            mastered=mastered_count,
            in_progress=in_progress_count,
            not_started=not_started_count,
            total=len(all_topics),
        ),
        history=history,
        overall_trend=trend,
    )


@router.get("/me/report")
async def download_my_report(current_user: dict = Depends(get_current_user)):
    """Generate and download the current user's progress report PDF."""
    _require_feature(CERTIFICATES_ENABLED, "certificates")
    import io
    username = current_user["username"]

    state = await student_states_collection.find_one(
        {"student_id": username}, {"_id": 0}
    )
    if not state:
        raise HTTPException(404, "No data yet — start learning first!")

    total = state.get("total_questions", 0)
    correct = state.get("correct_answers", 0)
    accuracy = round((correct / total * 100) if total > 0 else 0, 2)
    topics = state.get("topic_proficiency", {})

    # Knowledge graph
    kg_data = None
    try:
        student = await tutor.sessions.get_student(username)
        if student and student.concepts:
            topics_with_mastery = [
                {"topic": t, "mastery": round(c.knowledge, 2)}
                for t, c in student.concepts.items()
            ]
            if topics_with_mastery:
                kg_data = await graph_engine.generate_graph(topics_with_mastery)
    except Exception:
        pass

    # Study plan
    plan_data = None
    try:
        student = await tutor.sessions.get_student(username)
        if student:
            tone = get_tone_directive(student)
            u_doc = await users_collection.find_one({"username": username})
            l_dir = get_language_directive((u_doc or {}).get("preferences"))
            plan_data = await study_planner.generate_plan(
                student=student, available_minutes=30, tone_directive=tone,
                language_directive=l_dir,
            )
    except Exception:
        pass

    from core.report_builder import build_report_pdf
    pdf_bytes = build_report_pdf(
        student_id=username, total_questions=total,
        correct_answers=correct, accuracy=accuracy,
        topics=topics, kg_data=kg_data, plan_data=plan_data,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="progress_report_{username}.pdf"'
        },
    )


@router.get("/report/{student_id}")
async def download_report(student_id: str, current_user: dict = Depends(require_self_or_guardian("student_id"))):
    """Generate and stream a PDF progress report."""
    _require_feature(CERTIFICATES_ENABLED, "certificates")
    import re
    import io
    if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', student_id):
        raise HTTPException(400, "Invalid student_id format")

    # Gather data
    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if not state:
        raise HTTPException(404, "No data found for this student")

    total = state.get("total_questions", 0)
    correct = state.get("correct_answers", 0)
    accuracy = round((correct / total * 100) if total > 0 else 0, 2)
    topics = state.get("topic_proficiency", {})

    # Try knowledge graph
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
                kg_data = result
    except Exception:
        pass

    # Try study plan
    plan_data = None
    try:
        student = await tutor.sessions.get_student(student_id)
        if student:
            from utils.tone import get_tone_directive as gtd
            tone = gtd(student)
            u2 = await users_collection.find_one({"username": student_id})
            l2 = get_language_directive((u2 or {}).get("preferences"))
            plan_data = await study_planner.generate_plan(
                student=student, available_minutes=30, tone_directive=tone,
                language_directive=l2,
            )
    except Exception:
        pass

    # Build PDF
    from core.report_builder import build_report_pdf
    pdf_bytes = build_report_pdf(
        student_id=student_id,
        total_questions=total,
        correct_answers=correct,
        accuracy=accuracy,
        topics=topics,
        kg_data=kg_data,
        plan_data=plan_data,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="progress_report_{student_id}.pdf"'
        },
    )


@router.get("/me/progress-snapshot")
async def get_progress_snapshot(
    current_user: dict = Depends(require_role("student")),
):
    """Lightweight weekly progress snapshot — topics touched, mastery gained, streak, next up."""
    import time as _time7
    student_id = current_user["username"]

    now = _time7.time()
    week_ago = now - 7 * 86400

    # Get student state
    state = await student_states_collection.find_one(
        {"student_id": student_id}, {"_id": 0}
    )
    if not state:
        return {
            "topics_touched_this_week": 0,
            "topics_list": [],
            "total_mastery_gain": 0.0,
            "current_streak": 0,
            "questions_this_week": 0,
            "next_up": "",
            "message": "Start learning to see your progress!",
        }

    # Get concepts and compute this-week activity
    concepts = state.get("concepts", {})
    topics_touched = []
    total_gain = 0.0

    for topic, data in concepts.items():
        if isinstance(data, dict):
            mastery_now = data.get("concept_mastery", data.get("knowledge", 0.0))
            # Estimate mastery gain from recent interactions
            last_seen = data.get("last_seen", 0)
            if last_seen > week_ago:
                # Approximate gain — real gain would need historical snapshots
                exposure = data.get("exposure_count", 1)
                gain = min(mastery_now * 0.3, 0.2) if exposure > 0 else 0
                topics_touched.append({
                    "topic": topic,
                    "mastery_before": max(0, round(mastery_now - gain, 3)),
                    "mastery_now": round(mastery_now, 3),
                    "gain": round(gain, 3),
                })
                total_gain += gain

    # Count questions this week from interactions
    from database import interactions_collection as _interactions_n7
    q_count = await _interactions_n7.count_documents({
        "student_id": student_id,
        "timestamp": {"$gte": week_ago},
    })

    # Get streak from gamification
    gam_state = state.get("gamification", {})
    streak = gam_state.get("current_streak", 0)

    # Determine next_up from learning path or first weak concept
    next_up = ""
    from database import learning_paths_collection as _paths_n7
    path_doc = await _paths_n7.find_one(
        {"student_id": student_id}, {"_id": 0, "path": 1}
    )
    if path_doc and path_doc.get("path"):
        for node in path_doc["path"]:
            if node.get("state") in ("current", "unlocked"):
                next_up = node.get("topic", "")
                break

    if not next_up and topics_touched:
        # Suggest weakest recently-touched topic
        weakest = min(topics_touched, key=lambda t: t["mastery_now"])
        if weakest["mastery_now"] < 0.8:
            next_up = weakest["topic"]

    # Build motivational message
    n_topics = len(topics_touched)
    if n_topics == 0:
        message = "No activity this week yet. Start a session to get going!"
    elif total_gain > 0.1:
        message = "Great momentum! Keep it up."
    elif n_topics >= 3:
        message = "Covering lots of ground this week."
    else:
        message = "Every session counts. You're building knowledge."

    return {
        "topics_touched_this_week": n_topics,
        "topics_list": sorted(topics_touched, key=lambda t: -t["gain"])[:10],
        "total_mastery_gain": round(total_gain, 3),
        "current_streak": streak,
        "questions_this_week": q_count,
        "next_up": next_up,
        "message": message,
    }
