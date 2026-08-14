"""
Learning Path Engine.

Given a student's goal topic, builds an ordered learning path by:
1. Recursively resolving prerequisites via PrerequisiteEngine
2. Topological-sorting so foundational topics come first
3. Annotating each node with mastery and lock/unlock state

Paths are persisted per-student in MongoDB and rebuilt on goal change.
"""

import logging
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any

from adaptive.core.prerequisite_engine import PrerequisiteEngine

logger = logging.getLogger("learning_path")

# Mastery thresholds
UNLOCK_MASTERY = 0.4   # prereq mastery needed to unlock next topic
MASTERED_THRESHOLD = 0.8  # topic considered mastered

_prereq_engine: Optional[PrerequisiteEngine] = None


def _get_prereq_engine() -> PrerequisiteEngine:
    global _prereq_engine
    if _prereq_engine is None:
        _prereq_engine = PrerequisiteEngine()
    return _prereq_engine


async def _resolve_prereqs(goal: str, max_depth: int = 3) -> Dict[str, List[str]]:
    """
    Recursively resolve prerequisites for a goal topic.
    Returns adjacency dict: topic -> [list of prereqs].
    Stops at max_depth to prevent infinite LLM loops.
    """
    engine = _get_prereq_engine()
    adjacency: Dict[str, List[str]] = {}
    visited = set()
    queue = deque([(goal, 0)])

    while queue:
        topic, depth = queue.popleft()
        topic_lower = topic.lower().strip()

        if topic_lower in visited:
            continue
        visited.add(topic_lower)

        if depth >= max_depth:
            adjacency[topic_lower] = []
            continue

        try:
            prereqs = await engine.get_prerequisites(topic_lower)
            # Filter self-references and already visited
            prereqs = [p for p in prereqs if p.lower().strip() != topic_lower]
            adjacency[topic_lower] = prereqs
            for p in prereqs:
                if p.lower().strip() not in visited:
                    queue.append((p, depth + 1))
        except Exception as e:
            logger.warning("Failed to get prereqs for %s: %s", topic_lower, e)
            adjacency[topic_lower] = []

    return adjacency


def _topological_sort(adjacency: Dict[str, List[str]], goal: str) -> List[str]:
    """
    Topological sort with goal at the end.
    adjacency: topic -> [prereqs that must come before it]
    Returns list from foundational -> goal.
    """
    # Build in-degree map (how many things depend on each topic)
    all_topics = set(adjacency.keys())
    for prereqs in adjacency.values():
        all_topics.update(prereqs)

    # Reverse: for each topic, what depends on it
    dependents: Dict[str, List[str]] = defaultdict(list)
    in_degree: Dict[str, int] = {t: 0 for t in all_topics}

    for topic, prereqs in adjacency.items():
        in_degree[topic] = len(prereqs)
        for p in prereqs:
            dependents[p].append(topic)
            if p not in in_degree:
                in_degree[p] = 0

    # Kahn's algorithm
    queue = deque([t for t, d in in_degree.items() if d == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dep in dependents[node]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # If cycle detected, append remaining
    remaining = [t for t in all_topics if t not in result]
    result.extend(remaining)

    # Ensure goal is last
    goal_lower = goal.lower().strip()
    if goal_lower in result:
        result.remove(goal_lower)
        result.append(goal_lower)

    return result


async def build_path(goal: str, max_depth: int = 3) -> List[Dict[str, Any]]:
    """
    Build an ordered learning path toward a goal.
    Returns list of {topic, order, prereqs} from foundational to goal.
    """
    adjacency = await _resolve_prereqs(goal, max_depth=max_depth)
    ordered = _topological_sort(adjacency, goal)

    path_nodes = []
    for i, topic in enumerate(ordered):
        path_nodes.append({
            "topic": topic,
            "order": i,
            "prereqs": adjacency.get(topic, []),
        })

    return path_nodes


def annotate_path(
    path_nodes: List[Dict[str, Any]],
    student_concepts: Dict,
) -> List[Dict[str, Any]]:
    """
    Annotate each path node with mastery and lock state based on student data.

    States:
    - "mastered": mastery >= MASTERED_THRESHOLD
    - "unlocked": all prereqs meet UNLOCK_MASTERY (or no prereqs), not yet mastered
    - "locked": some prereq hasn't reached UNLOCK_MASTERY
    - "current": first unlocked, non-mastered node (the suggested next topic)
    """
    def _get_mastery(topic: str) -> float:
        concept = student_concepts.get(topic)
        if concept is None:
            return 0.0
        if hasattr(concept, "concept_mastery"):
            return concept.concept_mastery
        if isinstance(concept, dict):
            return concept.get("concept_mastery", concept.get("knowledge", 0.0))
        return 0.0

    annotated = []
    found_current = False

    for node in path_nodes:
        topic = node["topic"]
        mastery = round(_get_mastery(topic), 3)
        prereqs = node.get("prereqs", [])

        # Check if all prereqs are met
        prereqs_met = all(
            _get_mastery(p) >= UNLOCK_MASTERY for p in prereqs
        ) if prereqs else True

        if mastery >= MASTERED_THRESHOLD:
            state = "mastered"
        elif prereqs_met:
            if not found_current:
                state = "current"
                found_current = True
            else:
                state = "unlocked"
        else:
            state = "locked"

        annotated.append({
            "topic": topic,
            "order": node["order"],
            "mastery": mastery,
            "state": state,
            "prereqs": prereqs,
        })

    return annotated


def create_path_document(
    student_id: str,
    goal: str,
    path_nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a MongoDB document for a learning path."""
    return {
        "student_id": student_id,
        "goal": goal.lower().strip(),
        "path": path_nodes,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
