"""
Persistent AI mentor persona with rolling memory.

Builds a system-level directive that is injected into every student-facing
LLM prompt.  The directive includes:

  1. Persona identity (configurable name, encouragement style).
  2. Student's display name (so the AI greets them personally).
  3. Tone adaptation (reuses get_tone_directive).
  4. Recent progress highlights from mentor memory.
  5. Leakage-guard reminder for Socratic modes.

Mentor memory is a short rolling list of key facts (goals, struggles, wins)
persisted per student in MongoDB.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import yaml

# ── Load persona config from default.yaml ──────────────────────
_config_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "configs", "default.yaml"
)
try:
    with open(_config_path) as _f:
        _mentor_cfg = yaml.safe_load(_f).get("mentor", {})
except FileNotFoundError:
    _mentor_cfg = {}

MENTOR_NAME: str = _mentor_cfg.get("name", "Sage")
ENCOURAGEMENT_STYLE: str = _mentor_cfg.get(
    "encouragement_style",
    "warm and supportive, celebrating effort over perfection",
)
MEMORY_LIMIT: int = _mentor_cfg.get("memory_limit", 10)


# ── Memory helpers (async, MongoDB-backed) ─────────────────────

async def load_memory(
    collection, student_id: str, limit: int = MEMORY_LIMIT
) -> List[Dict[str, Any]]:
    """Load the most recent mentor memory items for a student."""
    cursor = collection.find(
        {"student_id": student_id},
        {"_id": 0, "fact": 1, "category": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit)
    items = await cursor.to_list(limit)
    items.reverse()  # oldest-first for narrative flow
    return items


async def save_memory_item(
    collection,
    student_id: str,
    fact: str,
    category: str = "general",
) -> None:
    """Persist a single mentor memory fact.

    Categories: goal, struggle, win, preference, general.
    """
    await collection.insert_one({
        "student_id": student_id,
        "fact": fact,
        "category": category,
        "created_at": time.time(),
    })

    # Trim to MEMORY_LIMIT — keep newest, delete oldest overflow
    total = await collection.count_documents({"student_id": student_id})
    if total > MEMORY_LIMIT:
        overflow = total - MEMORY_LIMIT
        oldest = collection.find(
            {"student_id": student_id},
            {"_id": 1},
        ).sort("created_at", 1).limit(overflow)
        ids = [doc["_id"] async for doc in oldest]
        if ids:
            await collection.delete_many({"_id": {"$in": ids}})


# ── Directive builder ──────────────────────────────────────────

def build_mentor_directive(
    display_name: str,
    tone_directive: str = "",
    memory_items: Optional[List[Dict[str, Any]]] = None,
    is_socratic: bool = False,
) -> str:
    """Build the full mentor system directive for prompt injection.

    Parameters
    ----------
    display_name : str
        The student's chosen display name.
    tone_directive : str
        Output of get_tone_directive() — emotional adaptation.
    memory_items : list
        Recent mentor memory facts (from load_memory).
    is_socratic : bool
        If True, add an extra reminder to never reveal answers.
    """

    lines = [
        f"You are {MENTOR_NAME}, a personal AI mentor.",
        f"Your encouragement style: {ENCOURAGEMENT_STYLE}.",
        f"The student's name is {display_name}. Address them by name occasionally — "
        f"not every sentence, but enough that it feels personal.",
        "",
        "RULES:",
        "- Be age-appropriate and encouraging.",
        "- Reference the student's real recent activity when you can.",
        "- Keep your personality consistent across sessions.",
        "- Never fabricate facts about the student; use only what's provided below.",
    ]

    if is_socratic:
        lines.append(
            "- CRITICAL: You are in Socratic mode. Do NOT reveal the answer. "
            "Guide the student to discover it themselves."
        )

    # Memory block
    if memory_items:
        lines.append("")
        lines.append(f"WHAT YOU REMEMBER ABOUT {display_name.upper()}:")
        for item in memory_items:
            cat = item.get("category", "general")
            fact = item.get("fact", "")
            lines.append(f"  [{cat}] {fact}")

    # Tone
    if tone_directive:
        lines.append("")
        lines.append(tone_directive)

    return "\n".join(lines)


# ── Memory extraction (called after an answer is evaluated) ────

def extract_memory_facts(
    student_id: str,
    topic: str,
    correct: bool,
    streak: int,
    concept_mastery: float,
    evaluation: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Derive mentor memory facts from a learning interaction.

    Returns a list of {fact, category} dicts to persist.
    """
    facts: List[Dict[str, str]] = []

    # Win: streak milestone
    if correct and streak in (3, 5, 10, 20):
        facts.append({
            "fact": f"Hit a {streak}-answer streak on {topic}!",
            "category": "win",
        })

    # Win: mastery milestone
    if correct and concept_mastery >= 0.8:
        facts.append({
            "fact": f"Reached strong mastery ({concept_mastery:.0%}) on {topic}.",
            "category": "win",
        })

    # Struggle: repeated wrong answers (streak reset)
    if not correct and streak == 0:
        misconception = ""
        if evaluation:
            misconception = evaluation.get("misconception") or ""
        if misconception:
            facts.append({
                "fact": f"Struggled with {topic}: {misconception}",
                "category": "struggle",
            })
        else:
            facts.append({
                "fact": f"Got one wrong on {topic} — keep at it.",
                "category": "struggle",
            })

    return facts
