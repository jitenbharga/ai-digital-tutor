"""
Prompt templates for canonical curriculum tree generation (N10).
"""

VERSION = "v1"


def build_curriculum_tree_prompt(subject: str) -> str:
    """
    Generate a canonical 3-level curriculum tree for a subject.
    Subject -> Topics -> Subtopics.
    Returns JSON array of nodes.
    """
    return f"""You are a curriculum designer. Generate a comprehensive, ordered curriculum tree for the subject: "{subject}".

Rules:
- Exactly 3 levels: Subject (level 0) -> Topics (level 1) -> Subtopics (level 2)
- The root node is the subject itself
- Each topic should have 3-6 subtopics
- Include 5-10 topics total (appropriate for the subject)
- Order topics from foundational to advanced
- For each node, specify prerequisites (other node_ids that must be completed first)
- Prerequisites should only reference nodes at the SAME level or lower
- Use snake_case for node_id (e.g., "algebra_basics", "linear_equations")
- node_id must be unique across the entire tree
- For every node, add "concept_aliases": a list of 2-4 alternative concept names a tutoring
  system might record mastery under for this node (synonyms, singular/plural, common phrasings).
  Example: for "Linked Lists" -> ["linked list", "singly linked list", "linked-list"].

BRANCH CHOICE NODES:
When a subject naturally splits into parallel tracks (e.g., "pick a programming language",
"choose a specialization"), model this as:
1. A "choice" node (node_type: "choice") — the parent that asks the student to pick
2. Multiple "branch" nodes (node_type: "branch") as children of the choice node,
   all sharing the same branch_group string (e.g., "lang_choice")
3. Each branch node has its own subtopics as children
The student picks ONE branch; the other branches' subtopics are hidden.
Only use choice/branch when the subject genuinely has parallel tracks.
Most subjects need 0-1 choice points. Default node_type is "topic".

Return ONLY a JSON object with this structure:
{{
  "subject": "{subject}",
  "nodes": [
    {{
      "node_id": "root",
      "title": "{subject}",
      "level": 0,
      "parent_id": null,
      "prerequisites": [],
      "order": 0,
      "node_id": "topic_1",
      "title": "Topic Name",
      "level": 1,
      "parent_id": "root",
      "prerequisites": [],
      "order": 1,
      "node_type": "topic"
    }},
    {{
      "node_id": "subtopic_1_1",
      "title": "Subtopic Name",
      "level": 2,
      "parent_id": "topic_1",
      "prerequisites": [],
      "order": 1,
      "node_type": "topic",
      "concept_aliases": ["subtopic name", "alt name", "another phrasing"]
    }},
    {{
      "node_id": "lang_choice",
      "title": "Choose Your Language",
      "level": 1,
      "parent_id": "root",
      "prerequisites": ["topic_1"],
      "order": 3,
      "node_type": "choice"
    }},
    {{
      "node_id": "python_track",
      "title": "Python Track",
      "level": 2,
      "parent_id": "lang_choice",
      "prerequisites": [],
      "order": 1,
      "node_type": "branch",
      "branch_group": "lang_choice"
    }}
  ]
}}

Important:
- First topic should have no prerequisites (entry point)
- Later topics should list earlier topic node_ids as prerequisites
- Subtopics within a topic should be ordered logically
- Each subtopic's prerequisites should be other subtopics or its parent topic
- node_type defaults to "topic" — only use "choice"/"branch" when genuinely applicable
- branch_group is only set on "branch" nodes and must match across sibling options
- Make the curriculum realistic and pedagogically sound
- No markdown, no explanation — ONLY the JSON object"""
