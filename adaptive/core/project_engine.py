"""
Project Engine (N13).

Manages capstone projects tied to N10 curriculum topics.
- Classifies topics as technical/buildable vs non-technical
- Generates scoped capstone projects (technical) or applied tasks (non-technical)
- Maps subtopic concepts to project parts
- Reviews student submissions against rubric + milestones
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from adaptive.database import projects_collection

logger = logging.getLogger("project_engine")

# ---------------------------------------------------------------------------
# Topic-type classification
# ---------------------------------------------------------------------------

TECHNICAL_SUBJECTS = {
    "computer_science", "algebra", "calculus", "statistics", "geometry",
    "physics", "chemistry",
}

# Keywords that strongly signal a buildable/technical topic
TECHNICAL_KEYWORDS = {
    "programming", "algorithm", "data structure", "code", "software",
    "web", "app", "database", "api", "function", "class", "loop",
    "array", "linked list", "tree", "graph", "sort", "search",
    "machine learning", "neural", "automation", "script",
    "circuit", "calculation", "equation", "formula", "proof",
    "experiment", "lab", "reaction", "synthesis",
    "probability", "regression", "hypothesis", "test",
}


def classify_topic_type(subject_id: str, topic_title: str = "") -> str:
    """
    Classify whether a topic is technical/buildable or non-technical.
    Returns 'technical' or 'non_technical'.
    """
    # Subject-level check
    if subject_id in TECHNICAL_SUBJECTS:
        return "technical"

    # Keyword check on topic title
    title_lower = topic_title.lower()
    for kw in TECHNICAL_KEYWORDS:
        if kw in title_lower:
            return "technical"

    return "non_technical"


# ---------------------------------------------------------------------------
# Project generation
# ---------------------------------------------------------------------------

async def get_or_generate_project(
    user_id: str,
    subject_id: str,
    topic_title: str,
    subtopics: List[str],
    tree_nodes: List[Dict],
) -> Optional[Dict[str, Any]]:
    """
    Get existing project for user+subject or generate a new one.
    Projects are per-user (unlike curriculum trees which are shared).
    """
    # Check if project exists
    existing = await projects_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0},
    )
    if existing:
        return existing

    # Generate new project
    topic_type = classify_topic_type(subject_id, topic_title)
    project = await _generate_project_llm(
        subject_id, topic_title, subtopics, topic_type,
    )
    if not project:
        return None

    # Map milestones to tree node IDs
    project["milestones"] = _map_milestones_to_nodes(
        project.get("milestones", []), tree_nodes
    )

    # Persist
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    doc = {
        "project_id": project_id,
        "user_id": user_id,
        "subject_id": subject_id,
        "topic_type": topic_type,
        "title": project.get("title", "Capstone Project"),
        "goal": project.get("goal", ""),
        "description": project.get("description", ""),
        "skills_required": project.get("skills_required", []),
        "milestones": project.get("milestones", []),
        "rubric": project.get("rubric", []),
        "status": "active",
        "submission": None,
        "review": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }

    await projects_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def _generate_project_llm(
    subject_id: str,
    topic_title: str,
    subtopics: List[str],
    topic_type: str,
) -> Optional[Dict]:
    """Call LLM to generate project brief."""
    from core.prompts.project import build_project_generation_prompt
    from core.llm_utils import call_llm
    from core.llm_registry import build_models

    is_technical = topic_type == "technical"
    subject_title = subject_id.replace("_", " ").title()

    prompt = build_project_generation_prompt(
        subject_title, topic_title, subtopics, is_technical,
    )
    models = build_models()

    result = await call_llm(
        models, prompt,
        required_key="title",
        engine_name="project_gen",
        prompt_version="v1",
    )

    if not result or "title" not in result:
        logger.error("LLM failed to generate project for %s/%s", subject_id, topic_title)
        return None

    return result


def _map_milestones_to_nodes(
    milestones: List[Dict],
    tree_nodes: List[Dict],
) -> List[Dict]:
    """
    Map milestone related_subtopics (titles) to actual node_ids from tree.
    """
    # Build title→node_id lookup
    title_to_id = {}
    for node in tree_nodes:
        title_to_id[node.get("title", "").lower()] = node["node_id"]

    for ms in milestones:
        related = ms.get("related_subtopics", [])
        node_ids = []
        for sub_title in related:
            # Try exact match first, then fuzzy
            lower = sub_title.lower()
            if lower in title_to_id:
                node_ids.append(title_to_id[lower])
            else:
                # Partial match
                for t, nid in title_to_id.items():
                    if lower in t or t in lower:
                        node_ids.append(nid)
                        break
        ms["related_nodes"] = node_ids
        # Clean up LLM field
        ms.pop("related_subtopics", None)
        # Ensure milestone_id
        if "milestone_id" not in ms:
            ms["milestone_id"] = f"m{ms.get('order', 0)}"

    return milestones


# ---------------------------------------------------------------------------
# Concept → Project mapping
# ---------------------------------------------------------------------------

async def get_concept_project_link(
    user_id: str,
    subject_id: str,
    node_id: str,
    node_title: str,
) -> Optional[Dict[str, str]]:
    """
    Get the concept→project link for a specific node.
    Returns {"project_part": "...", "milestone_id": "..."} or None.
    """
    project = await projects_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0},
    )
    if not project:
        return None

    # Check if any milestone already references this node
    for ms in project.get("milestones", []):
        if node_id in ms.get("related_nodes", []):
            return {
                "project_part": f"You'll use this for: {ms.get('title', 'your project')}",
                "milestone_id": ms.get("milestone_id", ""),
            }

    # Generate via LLM for nodes not directly mapped
    link = await _generate_concept_link_llm(
        node_title, project,
    )
    return link


async def _generate_concept_link_llm(
    node_title: str,
    project: Dict,
) -> Optional[Dict[str, str]]:
    """Generate concept→project link via LLM."""
    from core.prompts.project import build_concept_project_link_prompt
    from core.llm_utils import call_llm
    from core.llm_registry import build_models

    prompt = build_concept_project_link_prompt(
        node_title,
        project.get("title", ""),
        project.get("goal", ""),
        project.get("milestones", []),
    )
    models = build_models()

    result = await call_llm(
        models, prompt,
        required_key="project_part",
        engine_name="concept_link",
        prompt_version="v1",
    )

    if not result:
        return {"project_part": f"This concept supports your project: {project.get('title', '')}", "milestone_id": ""}

    return {
        "project_part": result.get("project_part", ""),
        "milestone_id": result.get("milestone_id", ""),
    }


# ---------------------------------------------------------------------------
# Milestone management
# ---------------------------------------------------------------------------

async def complete_milestone(
    user_id: str,
    subject_id: str,
    milestone_id: str,
) -> bool:
    """Mark a milestone as completed (self-attest)."""
    result = await projects_collection.update_one(
        {
            "user_id": user_id,
            "subject_id": subject_id,
            "milestones.milestone_id": milestone_id,
        },
        {
            "$set": {
                "milestones.$.completed": True,
                "milestones.$.completed_at": time.time(),
                "updated_at": time.time(),
            }
        },
    )
    return result.modified_count > 0


async def get_project_progress(user_id: str, subject_id: str) -> Dict:
    """Get milestone completion stats."""
    project = await projects_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0, "milestones": 1, "status": 1},
    )
    if not project:
        return {"milestones_done": 0, "milestones_total": 0}

    milestones = project.get("milestones", [])
    done = sum(1 for m in milestones if m.get("completed"))
    return {
        "milestones_done": done,
        "milestones_total": len(milestones),
        "status": project.get("status", "active"),
    }


# ---------------------------------------------------------------------------
# Project submission + review
# ---------------------------------------------------------------------------

async def submit_project(
    user_id: str,
    subject_id: str,
    submission_type: str,
    content: str,
) -> Optional[Dict]:
    """
    Submit project for AI review. Stores submission and generates review.
    """
    project = await projects_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0},
    )
    if not project:
        return None

    # Store submission
    submission = {
        "type": submission_type,
        "content": content,
        "submitted_at": time.time(),
    }

    # Generate AI review
    review = await _review_submission_llm(project, content, submission_type)

    # Update milestone pass/fail from review
    if review and "milestone_reviews" in review:
        milestones = project.get("milestones", [])
        for mr in review["milestone_reviews"]:
            for ms in milestones:
                if ms.get("milestone_id") == mr.get("milestone_id"):
                    ms["completed"] = mr.get("passed", False)
                    if mr.get("passed"):
                        ms["completed_at"] = time.time()

    await projects_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {
            "$set": {
                "submission": submission,
                "review": review,
                "status": "reviewed",
                "milestones": project.get("milestones", []),
                "updated_at": time.time(),
            }
        },
    )

    return {
        "project_id": project.get("project_id", ""),
        "review": review,
    }


async def _review_submission_llm(
    project: Dict,
    content: str,
    submission_type: str,
) -> Optional[Dict]:
    """Review submission via LLM."""
    from core.prompts.project import build_project_review_prompt
    from core.llm_utils import call_llm
    from core.llm_registry import build_models

    prompt = build_project_review_prompt(
        project.get("title", ""),
        project.get("goal", ""),
        project.get("milestones", []),
        project.get("rubric", []),
        content,
        submission_type,
    )
    models = build_models()

    result = await call_llm(
        models, prompt,
        required_key="overall_score",
        engine_name="project_review",
        prompt_version="v1",
    )

    if not result:
        logger.error("LLM failed to review project submission")
        return {
            "overall_score": 0,
            "passed": False,
            "summary": "Review could not be completed. Please try again.",
            "milestone_reviews": [],
            "strengths": [],
            "improvements": [],
            "next_steps": "Try submitting again.",
        }

    return result
