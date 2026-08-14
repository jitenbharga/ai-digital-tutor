from typing import Dict, List

from adaptive.core.llm_registry import build_models_cheap
from adaptive.core.llm_utils import call_llm
from adaptive.core.prompts import knowledge_graph as prompt_tmpl


class KnowledgeGraphEngine:

    def __init__(self):
        self.models = build_models_cheap()  # P3.1: classification uses cheap tier

    async def generate_graph(self, topics_with_mastery: List[Dict]) -> Dict:

        if len(topics_with_mastery) < 2:
            return {
                "nodes": topics_with_mastery,
                "edges": [],
                "weak_links": [],
                "suggested_focus": "Study more topics to build a knowledge graph.",
                "model_used": "skip"
            }

        prompt = prompt_tmpl.build(topics_with_mastery)

        data = await call_llm(
            self.models, prompt, required_key="nodes",
            engine_name="knowledge_graph",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "nodes": data.get("nodes", topics_with_mastery),
                "edges": data.get("edges", []),
                "weak_links": data.get("weak_links", []),
                "suggested_focus": data.get("suggested_focus", ""),
                "model_used": data.get("model_used", "unknown")
            }

        return {
            "nodes": topics_with_mastery,
            "edges": [],
            "weak_links": [],
            "suggested_focus": "Unable to generate prerequisite map. Continue studying and try again.",
            "model_used": "fallback"
        }
