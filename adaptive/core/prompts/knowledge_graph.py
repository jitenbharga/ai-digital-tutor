"""Versioned prompt template for KnowledgeGraphEngine."""

from typing import Dict, List

VERSION = "v1"


def build(topics_with_mastery: List[Dict]) -> str:

    topic_list = "\n".join(
        f"- {t['topic']}: mastery={t['mastery']:.2f}"
        for t in topics_with_mastery
    )

    return f"""You are an expert curriculum designer.

Given these topics the student has studied:
{topic_list}

Map the prerequisite relationships between them.

Rules:
- Only create edges where a genuine prerequisite relationship exists
- "strength" must be "strong", "moderate", or "weak"
- "weak_links" should list edges where the prerequisite topic has LOW mastery (< 0.5) but the dependent topic is being studied
- "suggested_focus" should be a concise actionable recommendation
- If there are no meaningful relationships, return empty edges

Output ONLY valid JSON:
{{
  "nodes": [
    {{"topic": "...", "mastery": 0.0}}
  ],
  "edges": [
    {{"from": "...", "to": "...", "strength": "strong|moderate|weak", "reason": "why this prerequisite matters"}}
  ],
  "weak_links": ["TopicA -> TopicB"],
  "suggested_focus": "actionable recommendation based on the weak links"
}}"""
