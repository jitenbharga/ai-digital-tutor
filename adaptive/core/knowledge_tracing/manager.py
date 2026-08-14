"""
Knowledge Tracing Manager — unified interface for mastery prediction.

Priority chain:
  1. DKT (if trained checkpoint exists and student has enough interactions)
  2. BKT (if student has >= MIN_BKT_INTERACTIONS for the skill)
  3. Heuristic fallback (concept.knowledge from the existing system)

This is the single entry point the rest of the codebase calls.
"""

import logging
from typing import Dict, List, Optional, Tuple

from adaptive.core.knowledge_tracing.bkt import (
    run_bkt, predict_correct, fit_params, DEFAULT_PARAMS,
)
from adaptive.config.features import DKT_ENABLED
from adaptive.database import interactions_collection

logger = logging.getLogger("knowledge_tracing.manager")

# Minimum interactions per skill before BKT is used
MIN_BKT_INTERACTIONS = 5
# Minimum total interactions before DKT is trusted
MIN_DKT_INTERACTIONS = 20


class KnowledgeTracingManager:
    """
    Unified mastery prediction with cold-start fallback.
    """

    def __init__(self, dkt_checkpoint: str = "checkpoints/dkt_model.pt"):
        # Kill List K3: DKT removed from hot path unless DKT_ENABLED=true
        if DKT_ENABLED:
            from adaptive.core.knowledge_tracing.dkt import DKTPredictor
            self.dkt = DKTPredictor(dkt_checkpoint)
            self._dkt_loaded = self.dkt.load()
        else:
            self.dkt = None
            self._dkt_loaded = False

        # Per-student BKT parameter cache: {(student_id, skill): params}
        self._bkt_params_cache: Dict[Tuple[str, str], Dict] = {}

        # Per-student interaction cache: {student_id: [(skill, correct), ...]}
        self._interaction_cache: Dict[str, List[Tuple[str, bool]]] = {}

    async def _load_student_interactions(
        self, student_id: str
    ) -> List[Tuple[str, bool]]:
        """Load a student's interaction history from MongoDB."""
        if student_id in self._interaction_cache:
            return self._interaction_cache[student_id]

        interactions = []
        cursor = interactions_collection.find(
            {"student_id": student_id}
        ).sort("timestamp", 1)

        async for doc in cursor:
            skill = doc.get("skill_id", "")
            correct = bool(doc.get("correct", False))
            interactions.append((skill, correct))

        self._interaction_cache[student_id] = interactions
        return interactions

    def invalidate_cache(self, student_id: str):
        """Call after a new interaction is logged to refresh predictions."""
        self._interaction_cache.pop(student_id, None)
        # Clear BKT params for this student
        keys_to_remove = [k for k in self._bkt_params_cache if k[0] == student_id]
        for k in keys_to_remove:
            del self._bkt_params_cache[k]

    async def predict_mastery(
        self,
        student_id: str,
        topic: str,
        heuristic_fallback: float = 0.5,
    ) -> Dict:
        """
        Predict P(correct) for this student on this topic.

        Returns:
            {
                "p_correct": float,     # calibrated P(correct on next item)
                "method": str,          # "dkt" | "bkt" | "heuristic"
                "confidence": float,    # how much data backs this estimate
                "n_interactions": int,  # interactions for this skill
            }
        """
        interactions = await self._load_student_interactions(student_id)

        # Filter to this topic
        topic_responses = [correct for skill, correct in interactions if skill == topic]
        n_topic = len(topic_responses)

        # All interactions (for DKT, which uses cross-skill info)
        n_total = len(interactions)

        # ── Strategy 1: DKT (if available and enough data) ──
        if self._dkt_loaded and n_total >= MIN_DKT_INTERACTIONS:
            p = self.dkt.predict_skill(interactions, topic)
            if p is not None:
                return {
                    "p_correct": p,
                    "method": "dkt",
                    "confidence": min(1.0, n_total / 100),
                    "n_interactions": n_topic,
                }

        # ── Strategy 2: BKT (per-skill, if enough skill-specific data) ──
        if n_topic >= MIN_BKT_INTERACTIONS:
            cache_key = (student_id, topic)
            if cache_key not in self._bkt_params_cache:
                self._bkt_params_cache[cache_key] = fit_params(topic_responses)

            params = self._bkt_params_cache[cache_key]
            p_known = run_bkt(topic_responses, params)
            p_correct = predict_correct(p_known, params["p_G"], params["p_S"])

            return {
                "p_correct": round(p_correct, 4),
                "method": "bkt",
                "confidence": min(1.0, n_topic / 30),
                "n_interactions": n_topic,
            }

        # ── Strategy 3: Heuristic fallback ──
        return {
            "p_correct": heuristic_fallback,
            "method": "heuristic",
            "confidence": 0.0,
            "n_interactions": n_topic,
        }

    def reload_dkt(self):
        """Reload DKT model from checkpoint (after retraining)."""
        if not DKT_ENABLED or self.dkt is None:
            logger.info("DKT disabled by feature flag; skipping reload")
            return
        self._dkt_loaded = self.dkt.load()
        self._interaction_cache.clear()
        logger.info("DKT model reloaded: available=%s", self._dkt_loaded)
