"""
Curriculum — subjects, curriculum map, branch/node progression, resume,
capstone projects, and per-node reference resources.
Extracted from serve.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Body

from adaptive.dependencies import get_current_user, require_role
from adaptive.runtime import tutor
from adaptive.routers.quiz import _save_active_quiz, _get_quiz_engine
from adaptive.core.curriculum_engine import (
    SUBJECTS as CURRICULUM_SUBJECTS, normalize_subject, get_or_generate_tree,
    get_user_progress, start_subject, update_node_status, compute_skip_warnings,
    overlay_progress, compute_progress_stats, get_chosen_branches, set_chosen_branch,
    get_pending_choices, filter_tree_by_branches, get_completion_meta,
    mark_node_complete, unlock_dependents,
)
from adaptive.core.project_engine import (
    get_or_generate_project, get_concept_project_link, complete_milestone, submit_project,
)
from adaptive.database import (
    student_states_collection, curricula_collection, curriculum_progress_collection,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["curriculum"])


# ── Extracted curriculum routes + resource helpers (verbatim from serve.py) ──
@router.get("/subjects")
async def list_subjects(
    current_user: dict = Depends(get_current_user),
):
    """List available subjects. Mark which ones user has started."""
    user_id = current_user["username"]

    # Get user's started subjects
    cursor = curriculum_progress_collection.find(
        {"user_id": user_id}, {"subject_id": 1, "_id": 0}
    )
    started_ids = set()
    async for doc in cursor:
        started_ids.add(doc["subject_id"])

    subjects = []
    for s in CURRICULUM_SUBJECTS:
        subjects.append({
            "id": s["id"],
            "title": s["title"],
            "icon": s["icon"],
            "color": s["color"],
            "started": s["id"] in started_ids,
        })

    return {"subjects": subjects}


@router.post("/subjects/{subject}/start")
async def start_subject_endpoint(
    subject: str,
    current_user: dict = Depends(require_role("student")),
):
    """Start a subject — generates canonical tree if needed, initializes user progress."""
    user_id = current_user["username"]
    subject_id = normalize_subject(subject)

    # Get or generate the canonical tree
    tree_doc = await get_or_generate_tree(subject_id)
    if not tree_doc:
        logger.error("Curriculum tree generation failed for %s — check LLM API keys and logs", subject_id)
        raise HTTPException(status_code=503, detail="Failed to generate curriculum tree — LLM service may be unavailable. Check server logs.")

    nodes = tree_doc["nodes"]

    # Initialize user progress
    progress = await start_subject(user_id, subject_id, nodes)

    # Get student concepts for mastery overlay
    student = await tutor.sessions.get_student(user_id)
    concepts = student.concepts if student else {}

    chosen = await get_chosen_branches(user_id, subject_id)
    filtered = filter_tree_by_branches(nodes, chosen)

    meta = await get_completion_meta(user_id, subject_id)
    enriched = overlay_progress(filtered, progress, concepts, meta)

    # Ratchet: persist any node that just crossed the mastery threshold, then
    # unlock its dependents, and re-overlay so the response reflects both.
    newly = [n for n in enriched if n.get("auto_complete")]
    if newly:
        for n in newly:
            await mark_node_complete(user_id, subject_id, n["node_id"], "mastery", n["mastery"])
            progress[n["node_id"]] = "done"
        await unlock_dependents(user_id, subject_id, filtered, progress)
        meta = await get_completion_meta(user_id, subject_id)
        enriched = overlay_progress(filtered, progress, concepts, meta)

    stats = compute_progress_stats(enriched)
    pending = get_pending_choices(nodes, chosen)

    return {
        "subject_id": subject_id,
        "subject_title": tree_doc.get("subject_title", subject_id),
        "nodes": enriched,
        "stats": stats,
        "pending_choices": pending,
        "chosen_branches": chosen,
    }


@router.get("/me/curriculum/{subject}")
async def get_curriculum_map(
    subject: str,
    current_user: dict = Depends(require_role("student")),
):
    """Get the curriculum map for a subject with user's progress overlaid."""
    user_id = current_user["username"]
    subject_id = normalize_subject(subject)

    # Get canonical tree
    tree_doc = await curricula_collection.find_one(
        {"subject_id": subject_id}, {"_id": 0}
    )
    if not tree_doc:
        # Try generating it
        tree_doc = await get_or_generate_tree(subject_id)
        if not tree_doc:
            logger.error("Curriculum tree not found and generation failed for %s", subject_id)
            raise HTTPException(status_code=503, detail="Curriculum tree not available — LLM generation failed. Check server logs.")

    nodes = tree_doc["nodes"]

    # Get user progress
    progress = await get_user_progress(user_id, subject_id)

    # Get student concepts for mastery
    student = await tutor.sessions.get_student(user_id)
    concepts = student.concepts if student else {}

    chosen = await get_chosen_branches(user_id, subject_id)
    filtered = filter_tree_by_branches(nodes, chosen)

    meta = await get_completion_meta(user_id, subject_id)
    enriched = overlay_progress(filtered, progress, concepts, meta)

    # Ratchet: persist any node that just crossed the mastery threshold, then
    # unlock its dependents, and re-overlay so the response reflects both.
    newly = [n for n in enriched if n.get("auto_complete")]
    if newly:
        for n in newly:
            await mark_node_complete(user_id, subject_id, n["node_id"], "mastery", n["mastery"])
            progress[n["node_id"]] = "done"
        await unlock_dependents(user_id, subject_id, filtered, progress)
        meta = await get_completion_meta(user_id, subject_id)
        enriched = overlay_progress(filtered, progress, concepts, meta)

    stats = compute_progress_stats(enriched)
    pending = get_pending_choices(nodes, chosen)

    return {
        "subject_id": subject_id,
        "subject_title": tree_doc.get("subject_title", subject_id),
        "nodes": enriched,
        "stats": stats,
        "pending_choices": pending,
        "chosen_branches": chosen,
    }


@router.post("/me/curriculum/{subject}/choose-branch")
async def choose_branch(
    subject: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """
    Choose a branch in a choice node.
    Body: { "branch_group": "lang_choice", "chosen_node_id": "python_track" }
    """
    user_id = current_user["username"]
    subject_id = normalize_subject(subject)
    branch_group = body.get("branch_group")
    chosen_node_id = body.get("chosen_node_id")

    if not branch_group or not chosen_node_id:
        raise HTTPException(400, "branch_group and chosen_node_id required")

    # Validate the node exists and is a branch in that group
    tree_doc = await curricula_collection.find_one(
        {"subject_id": subject_id}, {"_id": 0}
    )
    if not tree_doc:
        raise HTTPException(404, "Subject not found")

    nodes = tree_doc["nodes"]
    valid = any(
        n["node_id"] == chosen_node_id
        and n.get("node_type") == "branch"
        and n.get("branch_group") == branch_group
        for n in nodes
    )
    if not valid:
        raise HTTPException(400, f"'{chosen_node_id}' is not a valid branch in group '{branch_group}'")

    await set_chosen_branch(user_id, subject_id, branch_group, chosen_node_id)

    # Unlock the chosen branch's children as in_progress
    for n in nodes:
        if n.get("parent_id") == chosen_node_id:
            await update_node_status(user_id, subject_id, n["node_id"], "in_progress")
            break  # just first child

    # Also mark the chosen branch node itself as in_progress
    await update_node_status(user_id, subject_id, chosen_node_id, "in_progress")

    return {"success": True, "branch_group": branch_group, "chosen_node_id": chosen_node_id}


@router.post("/me/curriculum/{subject}/node/{node_id}/skip")
async def skip_curriculum_node(
    subject: str,
    node_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """
    Skip a curriculum node. Warns if dependents need it as prerequisite.
    Skipping proceeds anyway (user acknowledged warning on frontend).
    """
    user_id = current_user["username"]
    subject_id = normalize_subject(subject)

    # Get canonical tree
    tree_doc = await curricula_collection.find_one(
        {"subject_id": subject_id}, {"_id": 0}
    )
    if not tree_doc:
        raise HTTPException(status_code=404, detail="Subject not found")

    nodes = tree_doc["nodes"]

    # Verify node exists
    node = next((n for n in nodes if n["node_id"] == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Get current progress
    progress = await get_user_progress(user_id, subject_id)

    # Check for warnings
    warnings = compute_skip_warnings(node_id, nodes, progress)

    # Apply skip
    await update_node_status(user_id, subject_id, node_id, "skipped")

    # Auto-unlock next nodes whose prereqs are now all done/skipped
    progress[node_id] = "skipped"
    for n in nodes:
        n_status = progress.get(n["node_id"], "not_started")
        if n_status == "not_started" and n.get("prerequisites"):
            all_met = all(
                progress.get(p, "not_started") in ("done", "skipped")
                for p in n["prerequisites"]
            )
            if all_met:
                await update_node_status(user_id, subject_id, n["node_id"], "in_progress")

    return {
        "success": True,
        "node_id": node_id,
        "warnings": warnings,
        "message": "Skipped '{}'{}" .format(
            node.get("title", node_id),
            ". Warning: some dependent topics may be harder without this foundation."
            if warnings else ""
        ),
    }


@router.post("/me/curriculum/{subject}/node/{node_id}/complete")
async def complete_curriculum_node(
    subject: str,
    node_id: str,
    body: dict = Body(default={}),
    current_user: dict = Depends(require_role("student")),
):
    """
    Manually mark a node complete (source "manual" — distinct from mastery-based).
    Optional: if body.require_check is true and not yet verified, returns a quick
    3-question check quiz instead; the client scores it and calls again with verified=true.
    Manual completion satisfies prerequisites just like mastery completion.
    """
    import uuid as _uuid_mc
    user_id = current_user["username"]
    subject_id = normalize_subject(subject)

    tree_doc = await curricula_collection.find_one({"subject_id": subject_id}, {"_id": 0})
    if not tree_doc:
        raise HTTPException(404, "Subject not found")
    nodes = tree_doc["nodes"]
    node = next((n for n in nodes if n["node_id"] == node_id), None)
    if not node:
        raise HTTPException(404, "Node not found")

    require_check = bool(body.get("require_check"))
    verified = bool(body.get("verified"))

    # Optional 3-question check before honoring the manual complete
    if require_check and not verified:
        engine = _get_quiz_engine()
        quiz_data = await engine.generate_quiz(topic=node.get("title", node_id), num_questions=3)
        for q in quiz_data["questions"]:
            q["type"] = "mcq"
            q["hints_used"] = 0
        quiz_id = str(_uuid_mc.uuid4())[:8]
        await _save_active_quiz(quiz_id, {
            "questions": quiz_data["questions"],
            "student_id": user_id,
            "topic": node.get("title", node_id),
        })
        public = [{
            "id": q["id"], "type": "mcq", "question": q["question"],
            "options": q.get("options", {}), "multiple": q.get("multiple", False),
            "concept": q.get("concept", ""), "difficulty": q.get("difficulty", "medium"),
        } for q in quiz_data["questions"]]
        return {
            "needs_check": True,
            "quiz": {"quiz_title": f"Quick check: {node.get('title', node_id)}",
                     "questions": public, "quiz_id": quiz_id},
        }

    # Persist manual completion + unlock dependents
    await mark_node_complete(user_id, subject_id, node_id, "manual", None)
    progress = await get_user_progress(user_id, subject_id)
    progress[node_id] = "done"
    await unlock_dependents(user_id, subject_id, nodes, progress)

    return {
        "success": True,
        "node_id": node_id,
        "status": "done",
        "source": "manual",
        "message": "Marked '{}' as complete.".format(node.get("title", node_id)),
    }


@router.get("/me/resume")
async def get_resume_info(
    current_user: dict = Depends(require_role("student")),
):
    """Return last active topic + context for resume functionality."""
    student_id = current_user["username"]

    # Check student state for last_active_topic
    state_doc = await student_states_collection.find_one(
        {"student_id": student_id},
        {"_id": 0, "last_active_topic": 1, "last_active_at": 1,
         "last_session_question": 1, "last_session_mode": 1},
    )

    if not state_doc or not state_doc.get("last_active_topic"):
        return {"has_session": False}

    import time as _time3
    last_at = state_doc.get("last_active_at", 0)
    elapsed_hours = (_time3.time() - last_at) / 3600 if last_at else 999

    # Get mastery for that topic
    student = await tutor.sessions.get_student(student_id)
    mastery = 0.0
    if student and student.concepts:
        concept = student.concepts.get(state_doc["last_active_topic"])
        if concept:
            mastery = getattr(concept, "concept_mastery", 0.0)

    return {
        "has_session": True,
        "topic": state_doc["last_active_topic"],
        "last_active_at": last_at,
        "elapsed_hours": round(elapsed_hours, 1),
        "last_question": state_doc.get("last_session_question", ""),
        "last_mode": state_doc.get("last_session_mode", ""),
        "mastery": round(mastery, 3),
    }


@router.post("/me/resume/track")
async def track_active_session(
    req: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Track last active topic (called by frontend on tutor session start/activity)."""
    student_id = current_user["username"]
    topic = req.get("topic", "").strip()
    if not topic:
        raise HTTPException(400, "topic required")

    import time as _time4
    await student_states_collection.update_one(
        {"student_id": student_id},
        {"$set": {
            "last_active_topic": topic,
            "last_active_at": _time4.time(),
            "last_session_question": req.get("question", ""),
            "last_session_mode": req.get("mode", ""),
        }},
        upsert=True,
    )
    return {"ok": True}


@router.get("/me/curriculum/{subject}/project")
async def get_project(
    subject: str,
    current_user: dict = Depends(require_role("student")),
):
    """Get or generate project for a subject."""
    student_id = current_user["username"]
    from core.curriculum_engine import (
        normalize_subject, get_or_generate_tree, SUBJECT_IDS,
    )

    subject_id = normalize_subject(subject)
    if subject_id not in SUBJECT_IDS:
        raise HTTPException(404, "Subject not found")

    # Get curriculum tree
    tree_doc = await get_or_generate_tree(subject_id)
    if not tree_doc:
        raise HTTPException(500, "Could not load curriculum")

    nodes = tree_doc.get("nodes", [])
    subject_title = tree_doc.get("subject_title", subject_id)

    # Get topic-level nodes (level 1) and subtopic titles
    topics = [n for n in nodes if n.get("level") == 1]
    topic_title = topics[0]["title"] if topics else subject_title
    subtopics = [n["title"] for n in nodes if n.get("level") == 2]

    project = await get_or_generate_project(
        student_id, subject_id, topic_title, subtopics, nodes,
    )

    if not project:
        raise HTTPException(500, "Could not generate project")

    # Compute milestone stats
    milestones = project.get("milestones", [])
    done = sum(1 for m in milestones if m.get("completed"))

    return {
        "project_id": project.get("project_id", ""),
        "subject_id": subject_id,
        "topic_type": project.get("topic_type", "technical"),
        "title": project.get("title", ""),
        "goal": project.get("goal", ""),
        "description": project.get("description", ""),
        "skills_required": project.get("skills_required", []),
        "milestones": milestones,
        "rubric": project.get("rubric", []),
        "status": project.get("status", "active"),
        "milestones_done": done,
        "milestones_total": len(milestones),
        "submission": project.get("submission"),
        "review": project.get("review"),
        "created_at": project.get("created_at", 0),
    }


@router.get("/me/curriculum/{subject}/node/{node_id}/project-link")
async def get_node_project_link(
    subject: str,
    node_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Get concept-to-project mapping for a specific node."""
    student_id = current_user["username"]
    from core.curriculum_engine import normalize_subject, get_or_generate_tree

    subject_id = normalize_subject(subject)

    # Get node title from tree
    tree_doc = await get_or_generate_tree(subject_id)
    node_title = node_id
    if tree_doc:
        for n in tree_doc.get("nodes", []):
            if n["node_id"] == node_id:
                node_title = n.get("title", node_id)
                break

    link = await get_concept_project_link(
        student_id, subject_id, node_id, node_title,
    )

    if not link:
        return {"node_id": node_id, "project_part": "", "milestone_id": ""}

    return {
        "node_id": node_id,
        "node_title": node_title,
        "project_part": link.get("project_part", ""),
        "milestone_id": link.get("milestone_id", ""),
    }


@router.post("/me/curriculum/{subject}/project/milestone/{milestone_id}/complete")
async def complete_project_milestone(
    subject: str,
    milestone_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """Self-attest a milestone as completed."""
    student_id = current_user["username"]
    from core.curriculum_engine import normalize_subject

    subject_id = normalize_subject(subject)

    success = await complete_milestone(student_id, subject_id, milestone_id)
    if not success:
        raise HTTPException(404, "Milestone or project not found")

    return {"ok": True, "milestone_id": milestone_id}


@router.post("/me/curriculum/{subject}/project/submit")
async def submit_project_endpoint(
    subject: str,
    body: dict = Body(...),
    current_user: dict = Depends(require_role("student")),
):
    """Submit project for AI review."""
    student_id = current_user["username"]
    from core.curriculum_engine import normalize_subject

    subject_id = normalize_subject(subject)

    submission_type = body.get("submission_type", "description")
    content = body.get("content", "").strip()
    if not content or len(content) > 20000:
        raise HTTPException(400, "Submission must be 1-20000 characters")

    result = await submit_project(
        student_id, subject_id, submission_type, content,
    )

    if not result:
        raise HTTPException(404, "No project found for this subject")

    review = result.get("review", {})
    return {
        "project_id": result.get("project_id", ""),
        "overall_score": review.get("overall_score", 0),
        "passed": review.get("passed", False),
        "summary": review.get("summary", ""),
        "milestone_reviews": review.get("milestone_reviews", []),
        "strengths": review.get("strengths", []),
        "improvements": review.get("improvements", []),
        "next_steps": review.get("next_steps", ""),
    }


@router.get("/me/curriculum/{subject}/node/{node_id}/resources")
async def get_node_resources(
    subject: str,
    node_id: str,
    current_user: dict = Depends(require_role("student")),
):
    """
    Get reference links for a curriculum node.
    Sources: YouTube Data API, Semantic Scholar API (when keys available).
    Falls back to cached/stored resources on the canonical node.
    """
    from core.curriculum_engine import normalize_subject, get_or_generate_tree

    subject_id = normalize_subject(subject)

    # Get tree to find node
    tree_doc = await get_or_generate_tree(subject_id)
    if not tree_doc:
        raise HTTPException(404, "Subject not found")

    node = None
    for n in tree_doc.get("nodes", []):
        if n["node_id"] == node_id:
            node = n
            break
    if not node:
        raise HTTPException(404, "Node not found")

    node_title = node.get("title", node_id)
    node_level = node.get("level", 1)

    # Check if resources already cached on the node
    from database import curricula_collection as _curricula_n11
    cached = await _curricula_n11.find_one(
        {"subject_id": subject_id},
        {"_id": 0, "resources": 1},
    )
    cached_resources = {}
    if cached and cached.get("resources"):
        cached_resources = cached["resources"]

    if node_id in cached_resources:
        return {"node_id": node_id, "resources": cached_resources[node_id]}

    # Generate resources via search APIs if available
    resources = await _fetch_resources(
        node_title, subject_id, node_level
    )

    # Cache on canonical node
    if resources:
        await _curricula_n11.update_one(
            {"subject_id": subject_id},
            {"$set": {
                "resources.{}".format(node_id): resources,
            }},
        )

    return {"node_id": node_id, "resources": resources}


async def _fetch_resources(topic_title, subject_id, node_level):
    """
    Fetch reference links from real APIs.
    YouTube Data API + Semantic Scholar when env keys set.
    Fallback: generate curated search URLs.
    """
    import os as _os_n11
    resources = []

    # YouTube Data API
    yt_key = _os_n11.environ.get("YOUTUBE_API_KEY")
    if yt_key:
        try:
            import aiohttp
            query = "{} tutorial explanation".format(topic_title)
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 3,
                "key": yt_key,
                "safeSearch": "strict",
                "relevanceLanguage": "en",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("items", []):
                            vid_id = item["id"].get("videoId", "")
                            if vid_id:
                                resources.append({
                                    "type": "video",
                                    "title": item["snippet"]["title"],
                                    "url": "https://youtube.com/watch?v={}".format(vid_id),
                                    "source": "YouTube",
                                    "level": "all",
                                })
        except Exception:
            pass
    else:
        # Fallback: YouTube search URL (not API, but real link)
        import urllib.parse as _up
        q = _up.quote_plus("{} tutorial".format(topic_title))
        resources.append({
            "type": "video",
            "title": "Search YouTube: {}".format(topic_title),
            "url": "https://www.youtube.com/results?search_query={}".format(q),
            "source": "YouTube Search",
            "level": "all",
        })

    # Semantic Scholar (papers — only for advanced/leaf nodes)
    if node_level >= 2:
        ss_key = _os_n11.environ.get("SEMANTIC_SCHOLAR_KEY", "")
        try:
            import aiohttp
            query = topic_title
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {"query": query, "limit": 2, "fields": "title,url,year"}
            headers = {}
            if ss_key:
                headers["x-api-key"] = ss_key
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for paper in data.get("data", []):
                            if paper.get("url"):
                                resources.append({
                                    "type": "paper",
                                    "title": paper.get("title", "Paper"),
                                    "url": paper["url"],
                                    "source": "Semantic Scholar",
                                    "level": "advanced",
                                    "year": paper.get("year"),
                                })
        except Exception:
            pass

    # Articles — real search API (Tavily) if configured, else Google Scholar search URL
    tavily_key = _os_n11.environ.get("TAVILY_API_KEY", "")
    got_articles = False
    if tavily_key:
        try:
            import aiohttp
            payload = {
                "api_key": tavily_key,
                "query": "{} {} explained tutorial".format(subject_id.replace("_", " "), topic_title),
                "max_results": 3,
                "search_depth": "basic",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.tavily.com/search", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for item in data.get("results", [])[:3]:
                            if item.get("url"):
                                resources.append({
                                    "type": "article",
                                    "title": item.get("title", "Article"),
                                    "url": item["url"],
                                    "source": "Web",
                                    "level": "all",
                                })
                                got_articles = True
        except Exception:
            pass

    if not got_articles:
        import urllib.parse as _up2
        q2 = _up2.quote_plus("{} {} explained".format(subject_id.replace("_", " "), topic_title))
        resources.append({
            "type": "article",
            "title": "Articles: {}".format(topic_title),
            "url": "https://scholar.google.com/scholar?q={}".format(q2),
            "source": "Google Scholar",
            "level": "all",
            "kind": "search",  # a search page — always reachable, not validated
        })

    # Validate every direct link (drop dead ones); leave search pages as-is
    resources = await _validate_resources(resources)
    return resources


async def _validate_resources(resources):
    """
    Keep only resources whose URLs are live. Direct links must return HTTP 200;
    YouTube watch URLs must be public+embeddable (oEmbed 200). Search pages
    (kind == "search") are passed through unvalidated.
    """
    try:
        import aiohttp
    except ImportError:
        # aiohttp not installed — skip live validation, return resources as-is
        # (fallback search links are always safe). Install aiohttp for full checks.
        return resources

    async def _ok(session, r):
        url = r.get("url", "")
        if r.get("kind") == "search" or not url:
            return True
        try:
            if "watch?v=" in url:
                oembed = "https://www.youtube.com/oembed?url={}&format=json".format(url)
                async with session.get(oembed, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                    return resp.status == 200
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                return resp.status == 200
        except Exception:
            return False

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            import asyncio as _a
            flags = await _a.gather(*[_ok(session, r) for r in resources])
        validated = []
        for r, ok in zip(resources, flags):
            if ok:
                r["verified"] = r.get("kind") != "search"
                validated.append(r)
        return validated
    except Exception:
        # If validation infra fails, return originals rather than nothing
        return resources


@router.post("/admin/revalidate-resources")
async def revalidate_resources(current_user: dict = Depends(require_role("admin"))):
    """
    Link-rot job: re-validate all cached node resources across curricula,
    drop dead links. Intended to be called on a weekly schedule.
    """
    from database import curricula_collection as _curricula_n11
    checked = 0
    removed = 0
    updated_nodes = 0
    cursor = _curricula_n11.find({"resources": {"$exists": True}})
    async for doc in cursor:
        subject_id = doc.get("subject_id")
        res_map = doc.get("resources", {}) or {}
        new_map = {}
        changed = False
        for node_id, res_list in res_map.items():
            checked += len(res_list)
            valid = await _validate_resources(res_list)
            if len(valid) != len(res_list):
                changed = True
                removed += len(res_list) - len(valid)
                updated_nodes += 1
            new_map[node_id] = valid
        if changed and subject_id:
            await _curricula_n11.update_one(
                {"subject_id": subject_id},
                {"$set": {"resources": new_map}},
            )
    return {"checked": checked, "removed": removed, "updated_nodes": updated_nodes}
