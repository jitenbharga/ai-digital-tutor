"""
Shared runtime singletons + cross-cutting helpers for the API layer.

Extracted from serve.py so the decomposed routers share ONE tutor + engine instance
and a single copy of the feature-gate and concept-mastery helpers.
"""

import logging

from fastapi import HTTPException

from api.inference import ProductionTutor
from core.hint_engine import HintGenerator
from core.knowledge_graph import KnowledgeGraphEngine
from core.review_engine import ReviewEngine
from core.study_planner import StudyPlanner
from core.progressive_challenge import ProgressiveChallengeEngine
from core.ab_experiment import get_experiment_manager

logger = logging.getLogger(__name__)


def _concept_mastery(concept) -> float:
    if concept is None:
        return 0.0
    if hasattr(concept, "concept_mastery"):
        return concept.concept_mastery
    if isinstance(concept, dict):
        return concept.get("concept_mastery", concept.get("knowledge", 0.0))
    return 0.0


class _LazyTutor:
    _inst = None

    def _get(self):
        if _LazyTutor._inst is None:
            _LazyTutor._inst = ProductionTutor()
        return _LazyTutor._inst

    def __getattr__(self, name):
        return getattr(self._get(), name)


tutor = _LazyTutor()
Hint = HintGenerator()
graph_engine = KnowledgeGraphEngine()
review_engine = ReviewEngine()
study_planner = StudyPlanner()
challenge_engine = ProgressiveChallengeEngine()


def _require_feature(flag: bool, name: str):
    if not flag:
        raise HTTPException(404, f"Feature '{name}' is not enabled")


_FEATURE_EXPERIMENTS = {
    "gamification": "gamification_v1",
    "leaderboard": "leaderboard_v1",
    "certificates": "certificates_v1",
    "quests": "quests_v1",
}


async def _is_feature_on_for_user(flag: bool, feature_name: str, student_id: str) -> bool:
    if flag:
        return True
    exp_id = _FEATURE_EXPERIMENTS.get(feature_name)
    if not exp_id:
        return False
    try:
        mgr = get_experiment_manager()
        arm = await mgr.get_arm(student_id, exp_id)
        return arm == "treatment"
    except Exception:
        return False