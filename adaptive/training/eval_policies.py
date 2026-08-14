#!/usr/bin/env python3
"""
RL Policy Evaluation Harness.

Runs multiple tutoring policies (DQN + baselines) on simulated learners
and produces a comparison table of pedagogical metrics.

Metrics per policy:
  - Mean knowledge gain (final - initial knowledge)
  - Mean cumulative reward
  - Mean final frustration
  - Mean questions to reach mastery (knowledge > 0.8)
  - Mean final engagement

Usage:
  python -m training.eval_policies
  python -m training.eval_policies --learners 200 --steps 50 --checkpoint checkpoints/dqn_model.pt
  python -m training.eval_policies --seed 42       # reproducible
  python -m training.eval_policies --frozen-seed 42 --checkpoint-a A.pt --checkpoint-b B.pt  # compare checkpoints
"""

import argparse
import os
import sys
import random
import copy
import json
from collections import defaultdict

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptive.models.dqn import DQNAgent
from adaptive.core.reward import update_student_traits, compute_reward
from training.simulator import SimStudent
from training.train_offline import SimStudentAdapter, build_action_space
from training.baselines import RandomPolicy, FixedLadderPolicy, MasteryThresholdPolicy


# ─── DQN Policy Wrapper ───

class DQNPolicy:
    """Wraps a trained DQNAgent as a policy for evaluation."""

    def __init__(self, checkpoint_path, name="DQN"):
        self.name = name
        self.agent = DQNAgent(
            action_space=build_action_space(),
            db_collection=None,
            min_buffer=0,
        )
        loaded = self.agent.load_checkpoint(checkpoint_path)
        if not loaded:
            print(f"WARNING: Could not load checkpoint {checkpoint_path}")

    def select_action(self, traits, concept):
        """Select action using greedy DQN policy."""
        # Build a SimStudent-like object for get_state
        sim = SimStudent.__new__(SimStudent)
        sim.traits = dict(traits)
        sim.concept = dict(concept)
        sim.conversation_turns = 0
        sim.last_mode = 0

        adapter = SimStudentAdapter(sim)
        _, action = self.agent.get_action(adapter, explore=False, serve_epsilon=0.0)
        return action  # (mode, hint, difficulty)


# ─── Evaluation Engine ───

def create_frozen_learners(n_learners, seed=None):
    """Create n_learners SimStudents with a fixed seed for reproducibility."""
    if seed is not None:
        random.seed(seed)

    learners = []
    for _ in range(n_learners):
        sim = SimStudent()
        # Snapshot initial state
        init_state = {
            "traits": copy.deepcopy(sim.traits),
            "concept": copy.deepcopy(sim.concept),
        }
        learners.append(init_state)

    return learners


def run_policy(policy, learner_snapshots, max_steps=50, seed=None):
    """
    Run a policy on a set of frozen learner initial states.

    Returns per-learner metrics list.
    """
    results = []

    for i, snapshot in enumerate(learner_snapshots):
        # Reset random state for this learner (same noise across policies)
        if seed is not None:
            random.seed(seed + i * 7919)  # deterministic per-learner noise

        sim = SimStudent.__new__(SimStudent)
        sim.traits = copy.deepcopy(snapshot["traits"])
        sim.concept = copy.deepcopy(snapshot["concept"])
        sim.conversation_turns = 0
        sim.last_mode = 0

        init_knowledge = sim.concept["knowledge"]
        cumulative_reward = 0.0
        mastery_step = None  # step at which knowledge > 0.8

        for step in range(max_steps):
            # Policy selects action
            mode, hint, difficulty = policy.select_action(sim.traits, sim.concept)

            # Student responds
            correct, response_time = sim.respond(mode, hint, difficulty)

            # Update traits + compute reward
            old_k, old_e = update_student_traits(
                sim.traits, sim.concept, correct, response_time, hint, difficulty
            )
            reward = compute_reward(
                sim.traits, sim.concept, correct, response_time,
                hint, difficulty, mode, old_k, old_e
            )
            cumulative_reward += reward

            # Check mastery milestone
            if mastery_step is None and sim.concept["knowledge"] > 0.8:
                mastery_step = step + 1

            # Early termination
            if sim.traits["fatigue"] > 0.9 or sim.traits["frustration"] > 0.9:
                break

        results.append({
            "init_knowledge": init_knowledge,
            "final_knowledge": sim.concept["knowledge"],
            "knowledge_gain": sim.concept["knowledge"] - init_knowledge,
            "cumulative_reward": cumulative_reward,
            "final_frustration": sim.traits["frustration"],
            "final_engagement": sim.traits["engagement"],
            "final_fatigue": sim.traits["fatigue"],
            "questions_to_mastery": mastery_step,  # None if never reached
            "steps_completed": step + 1,
        })

    return results


def aggregate_metrics(results):
    """Compute summary statistics from per-learner results."""
    n = len(results)
    if n == 0:
        return {}

    knowledge_gains = [r["knowledge_gain"] for r in results]
    rewards = [r["cumulative_reward"] for r in results]
    frustrations = [r["final_frustration"] for r in results]
    engagements = [r["final_engagement"] for r in results]
    mastery_steps = [r["questions_to_mastery"] for r in results if r["questions_to_mastery"] is not None]
    reached_mastery = len(mastery_steps)

    return {
        "n_learners": n,
        "mean_knowledge_gain": sum(knowledge_gains) / n,
        "mean_reward": sum(rewards) / n,
        "mean_frustration": sum(frustrations) / n,
        "mean_engagement": sum(engagements) / n,
        "mastery_rate": reached_mastery / n,
        "mean_questions_to_mastery": sum(mastery_steps) / max(reached_mastery, 1),
        "mean_final_knowledge": sum(r["final_knowledge"] for r in results) / n,
    }


def print_comparison_table(policy_results):
    """Print a formatted comparison table."""
    print()
    print("=" * 100)
    print("RL POLICY EVALUATION REPORT")
    print("=" * 100)

    # Header
    cols = [
        ("Policy", 20),
        ("Know. Gain", 12),
        ("Mean Reward", 12),
        ("Frustration", 12),
        ("Engagement", 12),
        ("Mastery %", 10),
        ("Q-to-Master", 12),
    ]
    header = "".join(name.ljust(width) for name, width in cols)
    print(header)
    print("-" * 100)

    for policy_name, metrics in policy_results.items():
        row = [
            policy_name.ljust(20),
            f"{metrics['mean_knowledge_gain']:+.4f}".ljust(12),
            f"{metrics['mean_reward']:.2f}".ljust(12),
            f"{metrics['mean_frustration']:.4f}".ljust(12),
            f"{metrics['mean_engagement']:.4f}".ljust(12),
            f"{metrics['mastery_rate']*100:.1f}%".ljust(10),
            f"{metrics['mean_questions_to_mastery']:.1f}".ljust(12),
        ]
        print("".join(row))

    print("=" * 100)

    # Verdict
    print()
    dqn_names = [n for n in policy_results if "DQN" in n.upper()]
    baseline_names = [n for n in policy_results if n not in dqn_names]

    for dqn_name in dqn_names:
        dqn = policy_results[dqn_name]
        print(f"[{dqn_name}] Comparison:")
        all_beat = True
        for bl_name in baseline_names:
            bl = policy_results[bl_name]
            reward_diff = dqn["mean_reward"] - bl["mean_reward"]
            kg_diff = dqn["mean_knowledge_gain"] - bl["mean_knowledge_gain"]
            status = "PASS" if reward_diff > 0 and kg_diff > 0 else "FAIL"
            if status == "FAIL":
                all_beat = False
            print(f"  vs {bl_name:20s}: reward {reward_diff:+.2f}, "
                  f"knowledge_gain {kg_diff:+.4f}  [{status}]")

        verdict = "SHIP-READY" if all_beat else "NEEDS MORE TRAINING"
        print(f"  -> Verdict: {verdict}")
    print()


def compare_checkpoints(checkpoint_a, checkpoint_b, n_learners=100, max_steps=50, seed=42):
    """
    Offline policy evaluation: compare two DQN checkpoints on
    the same frozen set of simulated learners.
    """
    learners = create_frozen_learners(n_learners, seed=seed)

    policy_a = DQNPolicy(checkpoint_a, name=f"DQN({os.path.basename(checkpoint_a)})")
    policy_b = DQNPolicy(checkpoint_b, name=f"DQN({os.path.basename(checkpoint_b)})")

    results = {}
    for policy in [policy_a, policy_b]:
        raw = run_policy(policy, learners, max_steps=max_steps, seed=seed)
        results[policy.name] = aggregate_metrics(raw)

    print_comparison_table(results)
    return results


# ─── Main ───

def main():
    parser = argparse.ArgumentParser(description="RL Policy Evaluation Harness")
    parser.add_argument("--learners", type=int, default=100, help="Number of simulated learners")
    parser.add_argument("--steps", type=int, default=50, help="Max steps per learner")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--checkpoint", default="checkpoints/dqn_model.pt", help="DQN checkpoint path")
    parser.add_argument("--checkpoint-a", default=None, help="First checkpoint for comparison")
    parser.add_argument("--checkpoint-b", default=None, help="Second checkpoint for comparison")
    parser.add_argument("--output-json", default=None, help="Save results as JSON")
    parser.add_argument("--output-markdown", default=None, help="Save markdown comparison table")
    args = parser.parse_args()

    # Mode: checkpoint comparison
    if args.checkpoint_a and args.checkpoint_b:
        compare_checkpoints(args.checkpoint_a, args.checkpoint_b,
                            n_learners=args.learners, max_steps=args.steps, seed=args.seed)
        return

    # Mode: full policy comparison
    learners = create_frozen_learners(args.learners, seed=args.seed)

    policies = [
        RandomPolicy(),
        FixedLadderPolicy(),
        MasteryThresholdPolicy(),
    ]

    # Only add DQN if checkpoint exists
    if os.path.exists(args.checkpoint):
        policies.append(DQNPolicy(args.checkpoint))
    else:
        print(f"NOTE: No DQN checkpoint at {args.checkpoint}, evaluating baselines only.")

    all_results = {}
    for policy in policies:
        print(f"Evaluating {policy.name}...", end=" ", flush=True)
        raw = run_policy(policy, learners, max_steps=args.steps, seed=args.seed)
        metrics = aggregate_metrics(raw)
        all_results[policy.name] = metrics
        print(f"done (reward={metrics['mean_reward']:.2f})")

    print_comparison_table(all_results)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"Results saved to {args.output_json}")

    if args.output_markdown:
        md = generate_markdown_table(all_results)
        with open(args.output_markdown, "w") as f:
            f.write(md)
        print(f"Markdown table saved to {args.output_markdown}")


def generate_markdown_table(policy_results):
    """Generate a markdown comparison table for embedding in README."""
    lines = [
        "| Policy | Knowledge Gain | Mean Reward | Frustration | Engagement | Mastery % | Q-to-Mastery |",
        "|--------|---------------|-------------|-------------|------------|-----------|-------------|",
    ]
    for name, m in policy_results.items():
        lines.append(
            f"| {name} "
            f"| {m['mean_knowledge_gain']:+.4f} "
            f"| {m['mean_reward']:.2f} "
            f"| {m['mean_frustration']:.4f} "
            f"| {m['mean_engagement']:.4f} "
            f"| {m['mastery_rate']*100:.1f}% "
            f"| {m['mean_questions_to_mastery']:.1f} |"
        )

    # Verdict
    dqn_names = [n for n in policy_results if "DQN" in n.upper()]
    baseline_names = [n for n in policy_results if n not in dqn_names]
    for dqn_name in dqn_names:
        dqn = policy_results[dqn_name]
        beats_all = all(
            dqn["mean_reward"] > policy_results[bl]["mean_reward"]
            and dqn["mean_knowledge_gain"] > policy_results[bl]["mean_knowledge_gain"]
            for bl in baseline_names
        )
        verdict = "SHIP-READY" if beats_all else "NEEDS MORE TRAINING"
        lines.append("")
        lines.append(f"**Verdict: {verdict}** -- DQN {'beats' if beats_all else 'does NOT beat'} all pedagogical baselines.")

    return "\n".join(lines) + "\n"


def check_dqn_beats_baselines(json_path="eval_results.json"):
    """
    Read saved evaluation results and return True if DQN beats all
    non-random baselines on both mean_reward and mean_knowledge_gain.

    Used by production startup to gate DQN serving.
    """
    if not os.path.exists(json_path):
        return False

    with open(json_path) as f:
        results = json.load(f)

    dqn_names = [n for n in results if "DQN" in n.upper()]
    if not dqn_names:
        return False

    # Baselines to beat: everything except Random and the DQN itself
    baselines_to_beat = [
        n for n in results
        if n not in dqn_names and n.lower() != "random"
    ]

    for dqn_name in dqn_names:
        dqn = results[dqn_name]
        for bl_name in baselines_to_beat:
            bl = results[bl_name]
            if dqn["mean_reward"] <= bl["mean_reward"]:
                return False
            if dqn["mean_knowledge_gain"] <= bl["mean_knowledge_gain"]:
                return False

    return True


if __name__ == "__main__":
    main()
