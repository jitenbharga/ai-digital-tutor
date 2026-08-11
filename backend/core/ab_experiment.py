"""
P4.1 — A/B Experiment Framework

Deterministic hash-based user assignment to experiment arms.
Tracks per-arm metrics: learning gain, frustration, retention.

Design:
  - Experiments stored in MongoDB `experiments` collection
  - Assignments in `experiment_assignments` (one per user per experiment)
  - Hash(student_id + experiment_id) → arm (deterministic, no re-randomization)
  - Metrics accumulated on every answer submission via track_metric()

Usage:
  exp = get_experiment_manager()
  arm = await exp.get_arm(student_id, "rl_vs_rule")
  # arm == "control" (mastery_rule) or "treatment" (dqn)
  await exp.track_metric(student_id, "rl_vs_rule", "learning_gain", 0.35)
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ab_experiment")


class ExperimentManager:
    """
    Manages A/B experiments with deterministic assignment and metric tracking.
    """

    def __init__(self, db=None):
        self._db = db
        self._experiments_col = None
        self._assignments_col = None
        self._metrics_col = None
        self._cache: Dict[str, Dict] = {}  # experiment_id → config cache

    def _get_collections(self):
        if self._experiments_col is None:
            if self._db is None:
                from database import db
                self._db = db
            self._experiments_col = self._db["experiments"]
            self._assignments_col = self._db["experiment_assignments"]
            self._metrics_col = self._db["experiment_metrics"]
        return self._experiments_col, self._assignments_col, self._metrics_col

    # ------------------------------------------------------------------
    # EXPERIMENT LIFECYCLE
    # ------------------------------------------------------------------

    async def create_experiment(
        self,
        experiment_id: str,
        description: str,
        arms: List[str],
        traffic_pct: float = 1.0,
        win_conditions: Optional[Dict] = None,
        min_sample_size: int = 30,
    ) -> Dict:
        """
        Create a new experiment.

        Args:
            experiment_id: Unique slug (e.g. "rl_vs_rule_v1")
            description: What we're testing
            arms: List of arm names (e.g. ["control", "treatment"])
            traffic_pct: Fraction of users enrolled (0.0-1.0)
            win_conditions: Pre-registered criteria for declaring a winner
            min_sample_size: Minimum users per arm before analysis
        """
        experiments_col, _, _ = self._get_collections()

        doc = {
            "experiment_id": experiment_id,
            "description": description,
            "arms": arms,
            "traffic_pct": traffic_pct,
            "win_conditions": win_conditions or {
                "primary_metric": "normalized_learning_gain",
                "min_effect_size": 0.1,
                "significance_level": 0.05,
            },
            "min_sample_size": min_sample_size,
            "status": "active",  # active | paused | concluded
            "conclusion": None,  # "treatment_wins" | "control_wins" | "no_difference"
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        await experiments_col.update_one(
            {"experiment_id": experiment_id},
            {"$set": doc},
            upsert=True,
        )
        self._cache[experiment_id] = doc
        logger.info("Experiment created: %s (%d arms, %.0f%% traffic)",
                     experiment_id, len(arms), traffic_pct * 100)
        return doc

    async def get_experiment(self, experiment_id: str) -> Optional[Dict]:
        """Load experiment config (cached)."""
        if experiment_id in self._cache:
            return self._cache[experiment_id]

        experiments_col, _, _ = self._get_collections()
        doc = await experiments_col.find_one({"experiment_id": experiment_id})
        if doc:
            self._cache[experiment_id] = doc
        return doc

    async def conclude_experiment(
        self, experiment_id: str, conclusion: str
    ) -> None:
        """Mark experiment as concluded with a verdict."""
        experiments_col, _, _ = self._get_collections()
        await experiments_col.update_one(
            {"experiment_id": experiment_id},
            {"$set": {
                "status": "concluded",
                "conclusion": conclusion,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        if experiment_id in self._cache:
            self._cache[experiment_id]["status"] = "concluded"
            self._cache[experiment_id]["conclusion"] = conclusion
        logger.info("Experiment %s concluded: %s", experiment_id, conclusion)

    # ------------------------------------------------------------------
    # ASSIGNMENT
    # ------------------------------------------------------------------

    def _hash_to_arm(
        self, student_id: str, experiment_id: str, arms: List[str]
    ) -> str:
        """Deterministic hash-based assignment. Stable across restarts."""
        key = f"{experiment_id}:{student_id}"
        h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        return arms[h % len(arms)]

    def _in_traffic(
        self, student_id: str, experiment_id: str, traffic_pct: float
    ) -> bool:
        """Deterministic check: is this user in the experiment traffic?"""
        if traffic_pct >= 1.0:
            return True
        key = f"traffic:{experiment_id}:{student_id}"
        h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        return (h % 10000) < int(traffic_pct * 10000)

    async def get_arm(
        self, student_id: str, experiment_id: str
    ) -> Optional[str]:
        """
        Get this user's arm for an experiment.
        Returns None if experiment doesn't exist, is not active,
        or user is outside traffic allocation.
        """
        exp = await self.get_experiment(experiment_id)
        if not exp or exp.get("status") != "active":
            return None

        if not self._in_traffic(student_id, experiment_id, exp.get("traffic_pct", 1.0)):
            return None

        # Check for existing assignment (allows manual overrides)
        _, assignments_col, _ = self._get_collections()
        existing = await assignments_col.find_one({
            "student_id": student_id,
            "experiment_id": experiment_id,
        })
        if existing:
            return existing["arm"]

        # Assign deterministically
        arm = self._hash_to_arm(student_id, experiment_id, exp["arms"])

        await assignments_col.insert_one({
            "student_id": student_id,
            "experiment_id": experiment_id,
            "arm": arm,
            "assigned_at": datetime.now(timezone.utc),
        })

        logger.info("Assigned %s to arm '%s' in experiment '%s'",
                     student_id, arm, experiment_id)
        return arm

    # ------------------------------------------------------------------
    # METRIC TRACKING
    # ------------------------------------------------------------------

    async def track_metric(
        self,
        student_id: str,
        experiment_id: str,
        metric_name: str,
        value: float,
        properties: Optional[Dict] = None,
    ) -> None:
        """Record a metric data point for a user in an experiment."""
        _, _, metrics_col = self._get_collections()

        await metrics_col.insert_one({
            "student_id": student_id,
            "experiment_id": experiment_id,
            "metric": metric_name,
            "value": value,
            "properties": properties or {},
            "timestamp": datetime.now(timezone.utc),
        })

    async def track_answer_metrics(
        self,
        student_id: str,
        experiment_id: str,
        correct: bool,
        frustration: float,
        mastery: float,
        response_time: float,
        policy_tag: str,
    ) -> None:
        """Convenience: track standard per-answer metrics for the A/B test."""
        _, _, metrics_col = self._get_collections()

        await metrics_col.insert_one({
            "student_id": student_id,
            "experiment_id": experiment_id,
            "metric": "answer_outcome",
            "value": 1.0 if correct else 0.0,
            "properties": {
                "frustration": frustration,
                "mastery": mastery,
                "response_time": response_time,
                "policy": policy_tag,
            },
            "timestamp": datetime.now(timezone.utc),
        })

    # ------------------------------------------------------------------
    # ANALYSIS
    # ------------------------------------------------------------------

    async def get_results(self, experiment_id: str) -> Dict:
        """
        Aggregate results per arm: sample size, mean metrics, distributions.
        """
        exp = await self.get_experiment(experiment_id)
        if not exp:
            return {"error": "experiment_not_found"}

        _, assignments_col, metrics_col = self._get_collections()

        # Get all assignments
        assignments = {}
        async for doc in assignments_col.find({"experiment_id": experiment_id}):
            assignments[doc["student_id"]] = doc["arm"]

        # Aggregate metrics per arm
        arm_data: Dict[str, Dict[str, list]] = {
            arm: {} for arm in exp["arms"]
        }

        async for doc in metrics_col.find({"experiment_id": experiment_id}):
            sid = doc["student_id"]
            arm = assignments.get(sid)
            if arm is None:
                continue

            metric = doc["metric"]
            if metric not in arm_data[arm]:
                arm_data[arm][metric] = []
            arm_data[arm][metric].append(doc["value"])

        # Compute summaries
        results = {
            "experiment_id": experiment_id,
            "status": exp.get("status"),
            "conclusion": exp.get("conclusion"),
            "win_conditions": exp.get("win_conditions"),
            "arms": {},
        }

        for arm_name, metrics in arm_data.items():
            arm_summary = {
                "n_users": sum(1 for a in assignments.values() if a == arm_name),
                "metrics": {},
            }
            for metric_name, values in metrics.items():
                if not values:
                    continue
                n = len(values)
                mean = sum(values) / n
                sorted_v = sorted(values)
                arm_summary["metrics"][metric_name] = {
                    "n": n,
                    "mean": round(mean, 4),
                    "median": round(sorted_v[n // 2], 4),
                    "min": round(sorted_v[0], 4),
                    "max": round(sorted_v[-1], 4),
                    "std": round(
                        (sum((v - mean) ** 2 for v in values) / max(n - 1, 1)) ** 0.5, 4
                    ),
                }
            results["arms"][arm_name] = arm_summary

        # Check if min sample reached
        min_sample = exp.get("min_sample_size", 30)
        all_arms_ready = all(
            results["arms"].get(a, {}).get("n_users", 0) >= min_sample
            for a in exp["arms"]
        )
        results["min_sample_reached"] = all_arms_ready

        return results


# ------------------------------------------------------------------
# SINGLETON
# ------------------------------------------------------------------

_manager_instance: Optional[ExperimentManager] = None


def get_experiment_manager() -> ExperimentManager:
    """Return shared ExperimentManager singleton."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ExperimentManager()
    return _manager_instance


# ------------------------------------------------------------------
# DEFAULT RL-VS-RULE EXPERIMENT
# ------------------------------------------------------------------

# The canonical experiment ID for Phase 4
RL_VS_RULE_EXPERIMENT = "rl_vs_rule_v1"

# Arm names
ARM_CONTROL = "control"       # mastery_rule policy
ARM_TREATMENT = "treatment"   # DQN policy


async def ensure_rl_experiment() -> None:
    """
    Create the RL-vs-rule experiment if it doesn't exist.
    Called at startup.
    """
    mgr = get_experiment_manager()
    existing = await mgr.get_experiment(RL_VS_RULE_EXPERIMENT)
    if existing:
        return

    await mgr.create_experiment(
        experiment_id=RL_VS_RULE_EXPERIMENT,
        description=(
            "Phase 4: Compare DQN RL policy (treatment) vs simple mastery-based "
            "rule policy (control) on real users. Primary metric: normalized "
            "learning gain from pre/post tests. Secondary: frustration, retention."
        ),
        arms=[ARM_CONTROL, ARM_TREATMENT],
        traffic_pct=1.0,
        win_conditions={
            "primary_metric": "normalized_learning_gain",
            "min_effect_size": 0.1,       # treatment must beat control by ≥0.1
            "significance_level": 0.05,   # p < 0.05
            "secondary_metrics": [
                "mean_frustration",       # lower is better for treatment
                "day7_retention",         # higher is better for treatment
            ],
        },
        min_sample_size=30,
    )
    logger.info("RL-vs-rule experiment initialized")
