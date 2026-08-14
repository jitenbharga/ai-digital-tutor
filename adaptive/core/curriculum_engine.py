"""
Curriculum Engine (N10).

Manages canonical curriculum trees (shared across users) and per-user progress overlay.
Trees are generated ONCE via LLM, then cached in MongoDB `curricula` collection.
Per-user progress lives in `curriculum_progress` collection.
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional

from adaptive.database import curricula_collection, curriculum_progress_collection

logger = logging.getLogger("curriculum_engine")

# Completion thresholds
MASTERY_DONE = 0.8       # auto-complete a node at/above this mastery
REVIEW_THRESHOLD = 0.6   # a done node below this is flagged needs_review (not reverted)


# ---------------------------------------------------------------------------
# Concept <-> node matching (normalize + alias)
# ---------------------------------------------------------------------------

def _normalize_concept(s: str) -> str:
    """Lowercase, strip punctuation, collapse spaces, naive singularization."""
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    out = []
    for w in s.split():
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.append(w)
    return " ".join(out)


def _concept_mastery(concept) -> Optional[float]:
    """Extract concept_mastery from a Concept object or dict."""
    if concept is None:
        return None
    if hasattr(concept, "concept_mastery"):
        return concept.concept_mastery
    if isinstance(concept, dict):
        return concept.get("concept_mastery", concept.get("knowledge", 0.0))
    return None


def resolve_mastery(node: Dict, student_concepts: Dict) -> float:
    """
    Resolve a node's mastery from the student's KT concepts via:
      exact key -> normalized key -> alias (node.concept_aliases) match.
    """
    if not student_concepts:
        return 0.0

    candidates = [node.get("node_id", ""), node.get("title", "")]
    candidates += list(node.get("concept_aliases", []) or [])

    # 1) exact match
    for c in candidates:
        if c and c in student_concepts:
            m = _concept_mastery(student_concepts[c])
            if m is not None:
                return m

    # 2) normalized match (also covers alias -> concept-name variants)
    norm_map = {_normalize_concept(k): v for k, v in student_concepts.items()}
    for c in candidates:
        nc = _normalize_concept(c)
        if nc and nc in norm_map:
            m = _concept_mastery(norm_map[nc])
            if m is not None:
                return m

    return 0.0

# ---------------------------------------------------------------------------
# Supported subjects (v1 — hardcoded list, expandable later)
# ---------------------------------------------------------------------------
SUBJECTS = [
    {"id": "algebra", "title": "Algebra", "icon": "calculator", "color": "#3B82F6"},
    {"id": "calculus", "title": "Calculus", "icon": "brain", "color": "#8B5CF6"},
    {"id": "physics", "title": "Physics", "icon": "atom", "color": "#10B981"},
    {"id": "chemistry", "title": "Chemistry", "icon": "beaker", "color": "#F59E0B"},
    {"id": "biology", "title": "Biology", "icon": "globe", "color": "#059669"},
    {"id": "computer_science", "title": "Computer Science", "icon": "code", "color": "#6366F1"},
    {"id": "statistics", "title": "Statistics", "icon": "bar_chart", "color": "#EC4899"},
    {"id": "geometry", "title": "Geometry", "icon": "shapes", "color": "#14B8A6"},
]

SUBJECT_IDS = {s["id"] for s in SUBJECTS}


def normalize_subject(subject: str) -> str:
    """Normalize subject string to canonical id."""
    return subject.lower().strip().replace(" ", "_")


# ---------------------------------------------------------------------------
# Canonical tree generation (one-time per subject)
# ---------------------------------------------------------------------------

async def get_or_generate_tree(subject: str) -> Optional[Dict[str, Any]]:
    """
    Get canonical curriculum tree from DB. If not found, generate via LLM and cache.
    Returns the full tree document or None on failure.
    """
    subject_id = normalize_subject(subject)

    # Check cache first
    doc = await curricula_collection.find_one(
        {"subject_id": subject_id}, {"_id": 0}
    )
    if doc:
        return doc

    # Generate via LLM
    tree = await _generate_tree_llm(subject_id)
    if not tree:
        return None

    # Persist
    doc = {
        "subject_id": subject_id,
        "subject_title": next(
            (s["title"] for s in SUBJECTS if s["id"] == subject_id),
            subject.title(),
        ),
        "nodes": tree,
        "version": 1,
        "created_at": time.time(),
    }
    await curricula_collection.update_one(
        {"subject_id": subject_id},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def _generate_tree_llm(subject_id: str) -> Optional[List[Dict]]:
    """Call LLM to produce the canonical node list for a subject."""
    from core.prompts.curriculum import build_curriculum_tree_prompt
    from core.llm_utils import call_llm
    from core.llm_registry import build_models

    subject_title = next(
        (s["title"] for s in SUBJECTS if s["id"] == subject_id),
        subject_id.replace("_", " ").title(),
    )

    prompt = build_curriculum_tree_prompt(subject_title)
    models = build_models()

    try:
        result = await call_llm(
            models, prompt,
            required_key="nodes",
            engine_name="curriculum_tree",
            prompt_version="v1",
        )
    except Exception as exc:
        logger.error("LLM exception generating curriculum tree for %s: %s", subject_id, exc)
        return None

    if not result or "nodes" not in result:
        logger.error("LLM returned empty/invalid result for curriculum tree %s: %r", subject_id, result)
        return None

    nodes = result["nodes"]
    # Validate & clean
    seen_ids = set()
    cleaned = []
    for node in nodes:
        nid = node.get("node_id", "")
        if not nid or nid in seen_ids:
            continue
        seen_ids.add(nid)
        cleaned.append({
            "node_id": nid,
            "title": node.get("title", nid.replace("_", " ").title()),
            "level": node.get("level", 1),
            "parent_id": node.get("parent_id"),
            "prerequisites": [p for p in node.get("prerequisites", []) if p in seen_ids or p == nid],
            "order": node.get("order", 0),
            "node_type": node.get("node_type", "topic"),
            "branch_group": node.get("branch_group"),
            # 2-4 likely KT concept names for this node (stored once, canonical)
            "concept_aliases": [a for a in (node.get("concept_aliases") or []) if a][:4],
        })

    # Fix prerequisites — only allow references to previously defined nodes
    valid_ids = {n["node_id"] for n in cleaned}
    for node in cleaned:
        node["prerequisites"] = [p for p in node["prerequisites"] if p in valid_ids and p != node["node_id"]]

    return cleaned


# ---------------------------------------------------------------------------
# Per-user progress
# ---------------------------------------------------------------------------

async def get_user_progress(user_id: str, subject_id: str) -> Dict[str, str]:
    """
    Get user's progress for a subject.
    Returns dict: node_id -> status (not_started|in_progress|done|skipped).
    """
    doc = await curriculum_progress_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0},
    )
    if not doc:
        return {}
    return doc.get("progress", {})


async def start_subject(user_id: str, subject_id: str, tree_nodes: List[Dict]) -> Dict[str, str]:
    """
    Initialize progress for a user on a subject.
    First node (level 1, order 0 or 1) set to in_progress, rest not_started.
    """
    progress = {}
    first_topic = None

    for node in tree_nodes:
        if node["level"] == 0:
            progress[node["node_id"]] = "in_progress"
        else:
            progress[node["node_id"]] = "not_started"
            if node["level"] == 1 and first_topic is None:
                first_topic = node["node_id"]

    # Set first topic + its subtopics to in_progress
    if first_topic:
        progress[first_topic] = "in_progress"
        for node in tree_nodes:
            if node.get("parent_id") == first_topic and not node.get("prerequisites"):
                progress[node["node_id"]] = "in_progress"
                break  # just first subtopic

    await curriculum_progress_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"$set": {
            "user_id": user_id,
            "subject_id": subject_id,
            "progress": progress,
            "started_at": time.time(),
            "updated_at": time.time(),
        }},
        upsert=True,
    )
    return progress


async def update_node_status(
    user_id: str,
    subject_id: str,
    node_id: str,
    status: str,
) -> None:
    """Update a single node's status."""
    await curriculum_progress_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {
            "$set": {
                f"progress.{node_id}": status,
                "updated_at": time.time(),
            }
        },
    )


def compute_skip_warnings(
    node_id: str,
    tree_nodes: List[Dict],
    progress: Dict[str, str],
) -> List[str]:
    """
    Check if skipping node_id would leave dependents blocked.
    Returns list of warning strings.
    """
    warnings = []

    # Find nodes that list this node as a prerequisite
    dependents = [
        n for n in tree_nodes
        if node_id in n.get("prerequisites", [])
    ]

    for dep in dependents:
        dep_status = progress.get(dep["node_id"], "not_started")
        if dep_status not in ("done", "skipped"):
            warnings.append(
                f"'{dep['title']}' requires '{next((n['title'] for n in tree_nodes if n['node_id'] == node_id), node_id)}' as a prerequisite"
            )

    return warnings


def overlay_progress(
    tree_nodes: List[Dict],
    progress: Dict[str, str],
    student_concepts: Dict = None,
    completion_meta: Dict = None,
) -> List[Dict[str, Any]]:
    """
    Merge canonical tree nodes with per-user progress + mastery data.

    Ratchet semantics:
      - A node stored not_started/in_progress with mastery >= MASTERY_DONE is
        surfaced as done and flagged auto_complete (the endpoint persists it).
      - A node already done stays done even if mastery decays; if mastery drops
        below REVIEW_THRESHOLD it gets needs_review=True (FSRS handles review).
    """
    completion_meta = completion_meta or {}
    result = []
    for node in tree_nodes:
        nid = node["node_id"]
        stored = progress.get(nid, "not_started")

        mastery = resolve_mastery(node, student_concepts)

        auto_complete = mastery >= MASTERY_DONE and stored in ("not_started", "in_progress")
        status = "done" if auto_complete else stored

        # Ratchet: a done node never reverts; flag for review if mastery decayed
        needs_review = status == "done" and mastery < REVIEW_THRESHOLD

        meta = completion_meta.get(nid, {}) if isinstance(completion_meta, dict) else {}

        result.append({
            "node_id": nid,
            "title": node.get("title", nid),
            "level": node.get("level", 1),
            "parent_id": node.get("parent_id"),
            "prerequisites": node.get("prerequisites", []),
            "order": node.get("order", 0),
            "status": status,
            "mastery": round(mastery, 3),
            "auto_complete": auto_complete,          # endpoint persists these
            "needs_review": needs_review,
            "completion_source": meta.get("source"),
            "completed_at": meta.get("completed_at"),
            "node_type": node.get("node_type", "topic"),
            "branch_group": node.get("branch_group"),
        })

    return result


async def get_completion_meta(user_id: str, subject_id: str) -> Dict[str, Any]:
    """Return {node_id: {source, completed_at, mastery_at_completion}} for a user/subject."""
    doc = await curriculum_progress_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0, "completion_meta": 1},
    )
    return (doc or {}).get("completion_meta", {})


async def mark_node_complete(
    user_id: str, subject_id: str, node_id: str,
    source: str = "mastery", mastery: Optional[float] = None,
) -> None:
    """Persist a node as done with completion metadata (source: mastery|manual)."""
    now = time.time()
    await curriculum_progress_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"$set": {
            f"progress.{node_id}": "done",
            f"completion_meta.{node_id}": {
                "source": source,
                "completed_at": now,
                "mastery_at_completion": mastery,
            },
            "updated_at": now,
        }},
        upsert=True,
    )


def compute_unlocks(nodes: List[Dict], progress: Dict[str, str]) -> List[str]:
    """Pure: node_ids that should move not_started -> in_progress (all prereqs done/skipped)."""
    unlocks = []
    for n in nodes:
        if progress.get(n["node_id"], "not_started") == "not_started" and n.get("prerequisites"):
            if all(progress.get(p, "not_started") in ("done", "skipped") for p in n["prerequisites"]):
                unlocks.append(n["node_id"])
    return unlocks


async def unlock_dependents(
    user_id: str, subject_id: str, nodes: List[Dict], progress: Dict[str, str],
) -> None:
    """Set not_started nodes to in_progress once all their prerequisites are done/skipped."""
    for nid in compute_unlocks(nodes, progress):
        await update_node_status(user_id, subject_id, nid, "in_progress")
        progress[nid] = "in_progress"


async def get_chosen_branches(user_id: str, subject_id: str) -> Dict[str, str]:
    """Return {branch_group: chosen_node_id} from user progress doc."""
    doc = await curriculum_progress_collection.find_one(
        {"user_id": user_id, "subject_id": subject_id},
        {"_id": 0, "chosen_branches": 1},
    )
    return (doc or {}).get("chosen_branches", {})


async def set_chosen_branch(
    user_id: str, subject_id: str, branch_group: str, chosen_node_id: str
) -> None:
    """Persist a branch choice and unlock the chosen branch's children."""
    await curriculum_progress_collection.update_one(
        {"user_id": user_id, "subject_id": subject_id},
        {
            "$set": {
                f"chosen_branches.{branch_group}": chosen_node_id,
                "updated_at": time.time(),
            }
        },
    )


def get_pending_choices(
    tree_nodes: List[Dict], chosen_branches: Dict[str, str]
) -> List[str]:
    """Return branch_group ids that exist in the tree but user hasn't chosen yet."""
    groups = set()
    for n in tree_nodes:
        bg = n.get("branch_group")
        if bg and n.get("node_type") == "branch":
            groups.add(bg)
    return [g for g in groups if g not in chosen_branches]


def filter_tree_by_branches(
    tree_nodes: List[Dict], chosen_branches: Dict[str, str]
) -> List[Dict]:
    """
    Remove unchosen branch nodes (and their descendants) from the tree.
    Choice nodes stay visible. Branch nodes only stay if chosen.
    """
    if not chosen_branches:
        return tree_nodes

    # Collect node_ids of unchosen branches
    hidden_ids = set()
    for node in tree_nodes:
        bg = node.get("branch_group")
        if bg and node.get("node_type") == "branch":
            chosen = chosen_branches.get(bg)
            if chosen and node["node_id"] != chosen:
                hidden_ids.add(node["node_id"])

    if not hidden_ids:
        return tree_nodes

    # Also hide descendants of hidden branches
    def _collect_descendants(parent_id: str):
        for n in tree_nodes:
            if n.get("parent_id") == parent_id and n["node_id"] not in hidden_ids:
                hidden_ids.add(n["node_id"])
                _collect_descendants(n["node_id"])

    for hid in list(hidden_ids):
        _collect_descendants(hid)

    return [n for n in tree_nodes if n["node_id"] not in hidden_ids]


def compute_progress_stats(nodes_with_progress: List[Dict]) -> Dict[str, Any]:
    """Compute % complete, counts, estimated time left."""
    total = len([n for n in nodes_with_progress if n["level"] > 0])
    done = len([n for n in nodes_with_progress if n["level"] > 0 and n["status"] in ("done", "skipped")])
    in_prog = len([n for n in nodes_with_progress if n["level"] > 0 and n["status"] == "in_progress"])

    pct = round(done / max(total, 1) * 100, 1)
    remaining = total - done
    est_minutes = remaining * 15  # ~15 min per node estimate

    # Find current node (first in_progress at deepest level, or first not_started)
    current = None
    for n in nodes_with_progress:
        if n["status"] == "in_progress" and n["level"] > 0:
            current = n["node_id"]
            break
    if not current:
        for n in nodes_with_progress:
            if n["status"] == "not_started" and n["level"] > 0:
                current = n["node_id"]
                break

    return {
        "total": total,
        "done": done,
        "in_progress": in_prog,
        "not_started": total - done - in_prog,
        "progress_pct": pct,
        "est_minutes_left": est_minutes,
        "current_node_id": current,
    }
