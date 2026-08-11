"""
P4 — A/B Experiment Analysis Script

Compares experiment arms on key metrics:
  - Normalized learning gain (primary)
  - Mean frustration (lower is better)
  - Accuracy rate (higher is better)
  - Day-7 retention proxy (sessions per user)

Uses Mann-Whitney U test for significance (non-parametric, works with small N).

Usage:
  python scripts/analyze_ab.py --experiment rl_vs_rule_v1
  python scripts/analyze_ab.py --experiment rl_vs_rule_v1 --conclude
"""

import argparse
import asyncio
import logging
import sys
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("analyze_ab")


def mann_whitney_u(x, y):
    """
    Simple Mann-Whitney U test (two-sided).
    Returns (U statistic, approximate p-value via normal approximation).
    """
    import math

    nx, ny = len(x), len(y)
    if nx == 0 or ny == 0:
        return 0, 1.0

    # Combine and rank
    combined = [(v, 'x') for v in x] + [(v, 'y') for v in y]
    combined.sort(key=lambda t: t[0])

    # Assign ranks (average ties)
    ranks = []
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2  # 1-indexed
        for k in range(i, j):
            ranks.append((avg_rank, combined[k][1]))
        i = j

    r_x = sum(r for r, g in ranks if g == 'x')
    u_x = r_x - nx * (nx + 1) / 2

    # Normal approximation
    mu = nx * ny / 2
    sigma = math.sqrt(nx * ny * (nx + ny + 1) / 12)
    if sigma == 0:
        return u_x, 1.0

    z = (u_x - mu) / sigma

    # Two-sided p-value via standard normal CDF approximation
    p = 2 * (1 - _norm_cdf(abs(z)))
    return u_x, p


def _norm_cdf(z):
    """Approximate standard normal CDF (Abramowitz & Stegun)."""
    import math
    if z < 0:
        return 1.0 - _norm_cdf(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-z * z / 2) * t * (
        0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    return 1.0 - p


def cohens_d(x, y):
    """Effect size (Cohen's d)."""
    import math
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return 0.0
    mx, my = sum(x) / nx, sum(y) / ny
    sx = math.sqrt(sum((v - mx) ** 2 for v in x) / (nx - 1))
    sy = math.sqrt(sum((v - my) ** 2 for v in y) / (ny - 1))
    pooled = math.sqrt(((nx - 1) * sx ** 2 + (ny - 1) * sy ** 2) / (nx + ny - 2))
    if pooled == 0:
        return 0.0
    return (mx - my) / pooled


async def analyze(experiment_id: str, conclude: bool = False):
    from database import db

    experiments_col = db["experiments"]
    assignments_col = db["experiment_assignments"]
    metrics_col = db["experiment_metrics"]

    # Load experiment
    exp = await experiments_col.find_one({"experiment_id": experiment_id})
    if not exp:
        logger.error("Experiment '%s' not found", experiment_id)
        return

    print(f"\n{'='*70}")
    print(f"  A/B EXPERIMENT ANALYSIS: {experiment_id}")
    print(f"  Status: {exp.get('status', '?')}")
    print(f"  Created: {exp.get('created_at', '?')}")
    print(f"{'='*70}\n")

    arms = exp.get("arms", ["control", "treatment"])
    win_conditions = exp.get("win_conditions", {})

    # Load assignments
    user_arms = {}
    async for doc in assignments_col.find({"experiment_id": experiment_id}):
        user_arms[doc["student_id"]] = doc["arm"]

    print(f"  Total enrolled users: {len(user_arms)}")
    for arm in arms:
        n = sum(1 for a in user_arms.values() if a == arm)
        print(f"    {arm}: {n} users")
    print()

    # Load metrics per arm
    arm_metrics = {arm: defaultdict(list) for arm in arms}
    async for doc in metrics_col.find({"experiment_id": experiment_id}):
        sid = doc["student_id"]
        arm = user_arms.get(sid)
        if arm is None:
            continue
        arm_metrics[arm][doc["metric"]].append(doc["value"])

    # Analyze each metric
    all_metrics = set()
    for am in arm_metrics.values():
        all_metrics.update(am.keys())

    if not all_metrics:
        print("  No metrics recorded yet.\n")
        return

    print(f"  {'Metric':<30} | {'Control':>12} | {'Treatment':>12} | {'p-value':>8} | {'Cohen d':>8} | Verdict")
    print(f"  {'-'*30}-+-{'-'*12}-+-{'-'*12}-+-{'-'*8}-+-{'-'*8}-+--------")

    primary = win_conditions.get("primary_metric", "")
    sig_level = win_conditions.get("significance_level", 0.05)
    min_effect = win_conditions.get("min_effect_size", 0.1)
    primary_verdict = None

    for metric in sorted(all_metrics):
        ctrl = arm_metrics.get("control", {}).get(metric, [])
        treat = arm_metrics.get("treatment", {}).get(metric, [])

        ctrl_mean = sum(ctrl) / max(len(ctrl), 1)
        treat_mean = sum(treat) / max(len(treat), 1)

        if ctrl and treat:
            _, p_val = mann_whitney_u(treat, ctrl)
            d = cohens_d(treat, ctrl)
        else:
            p_val = 1.0
            d = 0.0

        sig = "*" if p_val < sig_level else ""
        verdict = ""
        if p_val < sig_level:
            if treat_mean > ctrl_mean:
                verdict = "treat+" + sig
            else:
                verdict = "ctrl+" + sig

        if metric == primary:
            if p_val < sig_level and d >= min_effect:
                primary_verdict = "treatment_wins" if treat_mean > ctrl_mean else "control_wins"
            elif len(ctrl) >= exp.get("min_sample_size", 30) and len(treat) >= exp.get("min_sample_size", 30):
                primary_verdict = "no_difference"

        print(f"  {metric:<30} | {ctrl_mean:>10.4f} ({len(ctrl):>2}) | {treat_mean:>10.4f} ({len(treat):>2}) | {p_val:>8.4f} | {d:>+8.3f} | {verdict}")

    print()

    # Min sample check
    min_sample = exp.get("min_sample_size", 30)
    for arm in arms:
        n = sum(1 for a in user_arms.values() if a == arm)
        if n < min_sample:
            print(f"  WARNING: {arm} has {n} users, need {min_sample} minimum")

    # Primary metric verdict
    if primary_verdict:
        print(f"\n  PRIMARY METRIC ({primary}) VERDICT: {primary_verdict}")
    else:
        print(f"\n  PRIMARY METRIC ({primary}): insufficient data or not significant")

    # Conclude if requested
    if conclude and primary_verdict:
        from core.ab_experiment import get_experiment_manager
        mgr = get_experiment_manager()
        await mgr.conclude_experiment(experiment_id, primary_verdict)
        print(f"\n  Experiment CONCLUDED: {primary_verdict}")
        if primary_verdict == "control_wins" or primary_verdict == "no_difference":
            print("  RECOMMENDATION: Delete DQN code. Simple mastery rule is sufficient.")
        else:
            print("  RECOMMENDATION: Ship DQN. Set RL_ENABLED=true globally.")

    print(f"\n{'='*70}\n")


async def main():
    parser = argparse.ArgumentParser(description="A/B Experiment Analysis (P4)")
    parser.add_argument("--experiment", default="rl_vs_rule_v1", help="Experiment ID")
    parser.add_argument("--conclude", action="store_true", help="Conclude experiment with verdict")
    args = parser.parse_args()

    await analyze(args.experiment, conclude=args.conclude)


if __name__ == "__main__":
    asyncio.run(main())
