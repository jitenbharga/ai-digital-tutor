"""
Admin / ops — RL + cache + LLM telemetry stats and A/B experiment control.
Extracted from serve.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Body, Query

from adaptive.dependencies import get_current_user
from adaptive.runtime import tutor
from adaptive.api.schemas import RLStatsResponse
from adaptive.core.ab_experiment import get_experiment_manager, RL_VS_RULE_EXPERIMENT
from adaptive.core.llm_cache import get_llm_cache
from adaptive.core.llm_telemetry import get_telemetry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


# ── Extracted admin / stats / experiment routes (verbatim from serve.py) ──
@router.get("/rl-stats", response_model=RLStatsResponse)
async def rl_stats(current_user: str = Depends(get_current_user)):
    """RL observability: current epsilon, step count, action distribution, mean reward/loss."""
    return tutor.agent.metrics.snapshot(
        epsilon=tutor.agent.epsilon,
        step_counter=tutor.agent.step_counter,
    )


@router.get("/cache-stats")
async def cache_stats(current_user: str = Depends(get_current_user)):
    """LLM response cache statistics."""
    cache = get_llm_cache()
    if cache is None:
        return {"enabled": False}
    return {"enabled": True, **cache.stats()}


@router.get("/llm-stats")
async def llm_stats(
    window_hours: float = Query(default=24.0, ge=0.1, le=168.0),
    current_user: str = Depends(get_current_user),
):
    """LLM telemetry: per-model call count, avg latency, failure rate."""
    telemetry = get_telemetry()
    return telemetry.summary(window_hours=window_hours)


@router.get("/llm-cost")
async def llm_cost(
    window_hours: float = Query(default=24.0, ge=0.1, le=168.0),
    current_user: str = Depends(get_current_user),
):
    """P3.3: Estimated LLM cost breakdown by model and tier."""
    telemetry = get_telemetry()
    return telemetry.cost_summary(window_hours=window_hours)


@router.post("/experiments")
async def create_experiment(
    experiment_id: str = Body(...),
    description: str = Body(""),
    arms: list = Body(["control", "treatment"]),
    traffic_pct: float = Body(1.0),
    min_sample_size: int = Body(30),
    current_user: str = Depends(get_current_user),
):
    """P4: Create a new A/B experiment."""
    mgr = get_experiment_manager()
    result = await mgr.create_experiment(
        experiment_id=experiment_id,
        description=description,
        arms=arms,
        traffic_pct=traffic_pct,
        min_sample_size=min_sample_size,
    )
    return {"status": "created", "experiment_id": experiment_id}


@router.get("/experiments/{experiment_id}/results")
async def experiment_results(
    experiment_id: str,
    current_user: str = Depends(get_current_user),
):
    """P4: Get A/B experiment results with per-arm metric summaries."""
    mgr = get_experiment_manager()
    results = await mgr.get_results(experiment_id)
    if "error" in results:
        raise HTTPException(404, results["error"])
    return results


@router.post("/experiments/{experiment_id}/conclude")
async def conclude_experiment(
    experiment_id: str,
    conclusion: str = Body(..., embed=True),
    current_user: str = Depends(get_current_user),
):
    """P4: Conclude an experiment with a verdict."""
    mgr = get_experiment_manager()
    exp = await mgr.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(404, "experiment_not_found")
    await mgr.conclude_experiment(experiment_id, conclusion)
    return {"status": "concluded", "conclusion": conclusion}


@router.get("/me/experiment")
async def my_experiment(
    current_user: str = Depends(get_current_user),
):
    """P4: Check which experiment arm the current user is assigned to."""
    mgr = get_experiment_manager()
    arm = await mgr.get_arm(current_user, RL_VS_RULE_EXPERIMENT)
    return {
        "experiment_id": RL_VS_RULE_EXPERIMENT,
        "arm": arm,
        "assigned": arm is not None,
    }
