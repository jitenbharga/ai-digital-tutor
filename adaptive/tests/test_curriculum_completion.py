"""
Tests for robust subtopic completion (curriculum_engine):
  1. Name-variant mastery still completes the node (alias/normalized matching).
  2. A done node with decayed mastery stays done and is flagged needs_review.
  3. Manual complete unlocks dependents (prerequisite gating).
"""

from adaptive.core.curriculum_engine import (
    overlay_progress,
    resolve_mastery,
    compute_unlocks,
    _normalize_concept,
    MASTERY_DONE,
    REVIEW_THRESHOLD,
)


def _node(nid, title, prereqs=None, aliases=None, level=2, parent="t1"):
    return {
        "node_id": nid,
        "title": title,
        "level": level,
        "parent_id": parent,
        "prerequisites": prereqs or [],
        "order": 1,
        "concept_aliases": aliases or [],
    }


# ---------------------------------------------------------------------------
# 1. Name-variant mastery completes the node
# ---------------------------------------------------------------------------

def test_normalize_handles_plurals_and_punctuation():
    assert _normalize_concept("Linked Lists") == _normalize_concept("linked list")
    assert _normalize_concept("Arrays!") == _normalize_concept("array")
    assert _normalize_concept("Binary-Trees") == "binary tree"


def test_alias_match_completes_node():
    node = _node("linked_lists", "Linked Lists", aliases=["singly linked list"])
    # KT recorded mastery under a name variant, not the node_id/title
    concepts = {"linked list": {"concept_mastery": 0.9}}
    m = resolve_mastery(node, concepts)
    assert m >= MASTERY_DONE

    enriched = overlay_progress([node], {"linked_lists": "in_progress"}, concepts)
    n = enriched[0]
    assert n["status"] == "done"
    assert n["auto_complete"] is True


def test_exact_alias_field_match():
    node = _node("ll", "Linked List Ops", aliases=["Linked Lists"])
    concepts = {"Linked Lists": {"concept_mastery": 0.85}}
    assert resolve_mastery(node, concepts) >= MASTERY_DONE


def test_low_mastery_variant_does_not_complete():
    node = _node("stacks", "Stacks", aliases=["stack"])
    concepts = {"stack": {"concept_mastery": 0.3}}
    enriched = overlay_progress([node], {"stacks": "in_progress"}, concepts)
    assert enriched[0]["status"] == "in_progress"
    assert enriched[0]["auto_complete"] is False


# ---------------------------------------------------------------------------
# 2. Done node with decayed mastery stays done + needs_review
# ---------------------------------------------------------------------------

def test_done_stays_done_on_decay_with_review_flag():
    node = _node("arrays", "Arrays", aliases=["array"])
    # Persisted as done, but mastery has decayed below the review threshold
    concepts = {"array": {"concept_mastery": 0.4}}
    enriched = overlay_progress([node], {"arrays": "done"}, concepts)
    n = enriched[0]
    assert n["status"] == "done"          # never reverts
    assert n["needs_review"] is True
    assert n["mastery"] < REVIEW_THRESHOLD


def test_done_no_review_when_mastery_healthy():
    node = _node("arrays", "Arrays", aliases=["array"])
    concepts = {"array": {"concept_mastery": 0.75}}
    enriched = overlay_progress([node], {"arrays": "done"}, concepts)
    assert enriched[0]["status"] == "done"
    assert enriched[0]["needs_review"] is False


# ---------------------------------------------------------------------------
# 3. Manual complete unlocks dependents
# ---------------------------------------------------------------------------

def test_manual_complete_unlocks_dependent():
    prereq = _node("intro", "Intro", prereqs=[])
    dependent = _node("advanced", "Advanced", prereqs=["intro"])
    nodes = [prereq, dependent]

    # Before completion, dependent is locked (not unlockable)
    progress = {"intro": "in_progress", "advanced": "not_started"}
    assert compute_unlocks(nodes, progress) == []

    # Manual complete of the prereq (source doesn't affect gating)
    progress["intro"] = "done"
    assert "advanced" in compute_unlocks(nodes, progress)


def test_skip_also_satisfies_prerequisite():
    prereq = _node("intro", "Intro")
    dependent = _node("advanced", "Advanced", prereqs=["intro"])
    progress = {"intro": "skipped", "advanced": "not_started"}
    assert "advanced" in compute_unlocks([prereq, dependent], progress)


def test_partial_prereqs_do_not_unlock():
    a = _node("a", "A")
    b = _node("b", "B")
    dep = _node("c", "C", prereqs=["a", "b"])
    progress = {"a": "done", "b": "in_progress", "c": "not_started"}
    assert "c" not in compute_unlocks([a, b, dep], progress)
