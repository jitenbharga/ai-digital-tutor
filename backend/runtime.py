"""
Shared runtime singletons + cross-cutting helpers for the API layer.

Extracted from serve.py so the decomposed routers — and serve.py's own
lifespan / leftover routes — share ONE tutor + engine instance and a single
copy of the feature-gate and concept-mastery helpers, instead of importing
them from the serve.py monolith.

Import direction is strictly downward (engines, core.*); this module never
imports serve, so `serve -> runtime -> engines` has no import cycle. The lazy
`from serve import tutor, ...` call sites keep working because serve.py
re-exports these names (`from runtime import ...`).
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
    """Read a concept's mastery from either a Concept object or a dict.

    Concept exposes ``concept_mastery`` / ``knowledge`` — there is no
    ``.mastery`` attribute, so naive ``concept.mastery`` reads always fell
    back to 0 and certificates were never awarded.
    """
    if concept is None:
        return 0.0
    if hasattr(concept, "concept_mastery"):
        return concept.concept_mastery
    if isinstance(concept, dict):
        return concept.get("concept_mastery", concept.get("knowledge", 0.0))
    return 0.0


# PERF/testability (W4): the RL tutor loads a torch DQN + checkpoint, which is
# slow and pulls the full ML stack. Build it lazily on first use (not at import)
# so cold start is faster and the app module can be imported for route/smoke
# tests without torch. The proxy forwards every attribute so existing `tutor.*`
# call sites are unchanged.
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


# ── Feature gating ─────────────────────────────────────────────────
def _require_feature(flag: bool, name: str):
    """Raise 404 if a feature is disabled."""
    if not flag:
        raise HTTPException(404, f"Feature '{name}' is not enabled")


# P5: Experiment-aware feature gate
# Maps feature name -> experiment_id for per-user A/B testing
_FEATURE_EXPERIMENTS = {
    "gamification": "gamification_v1",
    "leaderboard": "leaderboard_v1",
    "certificates": "certificates_v1",
    # No quests_v1 experiment is created at startup, so get_arm returns None and
    # this behaves as global-flag-only — but the gating path is now consistent.
    "quests": "quests_v1",
}


async def _is_feature_on_for_user(flag: bool, feature_name: str, student_id: str) -> bool:
    """
    Check if a feature is enabled for a specific user.
    Priority: global flag ON -> always on. Flag OFF + experiment active -> check arm.
    """
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
