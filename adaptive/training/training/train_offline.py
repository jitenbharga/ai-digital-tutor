"""
Offline RL training pipeline for the DQN tutor agent.

Runs simulated episodes against a SimStudent, using shared reward math
from core/reward.py. Produces a checkpoint and prints a rising mean-reward curve.

Usage:
    python -m training.train_offline
    python -m training.train_offline --episodes 10000 --config configs/default.yaml
"""

import argparse
import os
import sys
import random
import time
from collections import deque

import yaml
import torch

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.dqn import DQNAgent
from core.reward import update_student_traits, compute_reward
from training.simulator import SimStudent


# ----------------------------------
# LOAD CONFIG
# ----------------------------------

def load_config(path="configs/default.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ----------------------------------
# BUILD ACTION SPACE (same as ProductionTutor)
# ----------------------------------

def build_action_space():
    actions = []
    for mode in range(4):
        for hint in range(3):
            for diff in [0.2, 0.4, 0.6]:
                actions.append((mode, hint, diff))
    return actions


# ----------------------------------
# SIMULATED STUDENT ADAPTER
# ----------------------------------
# DQNAgent.get_action() expects a student object with get_current_concept()
# and the trait attributes. This adapter wraps SimStudent for that interface.

class SimStudentAdapter:
    """Wraps SimStudent to satisfy DQNAgent.get_state() interface."""

    def __init__(self, sim):
        self._sim = sim
        # Copy traits as attributes
        self._sync_from_sim()

    def _sync_from_sim(self):
        for key, val in self._sim.traits.items():
            setattr(self, key, val)
        self.conversation_turns = self._sim.conversation_turns
        self.last_mode = self._sim.last_mode

    def get_current_concept(self):
        """Return a concept-like object with .knowledge and .concept_mastery."""
        return _ConceptProxy(self._sim.concept)


class _ConceptProxy:
    """Minimal proxy so DQNAgent.get_state() can read concept.knowledge etc."""
    def __init__(self, concept_dict):
        self.knowledge = concept_dict["knowledge"]
        self.concept_mastery = concept_dict["concept_mastery"]


# ----------------------------------
# MAIN TRAINING LOOP
# ----------------------------------

def train(config_path="configs/default.yaml", episodes_override=None):

    cfg = load_config(config_path)
    rl_cfg = cfg["rl"]
    train_cfg = cfg["training"]

    episodes = episodes_override or train_cfg["episodes"]
    max_steps = train_cfg["max_steps_per_episode"]
    checkpoint_freq = train_cfg["checkpoint_freq"]
    log_interval = train_cfg["log_interval"]
    checkpoint_path = train_cfg["checkpoint_path"]
    trait_ranges = train_cfg.get("sim_trait_ranges", None)

    # Build agent (no DB collection — offline training)
    action_space = build_action_space()
    agent = DQNAgent(
        action_space=action_space,
        db_collection=None,
        min_buffer=rl_cfg["min_buffer"],
    )

    # Try to load existing checkpoint (resume training)
    agent.load_checkpoint(checkpoint_path)

    # Override epsilon from config if starting fresh
    if agent.step_counter == 0:
        agent.epsilon = rl_cfg["epsilon_start"]

    # Tracking
    reward_window = deque(maxlen=100)
    total_steps = 0
    best_avg_reward = float("-inf")

    print("=" * 60)
    print("OFFLINE RL TRAINING")
    print("=" * 60)
    print("Episodes: %d | Max steps/ep: %d | Min buffer: %d" % (episodes, max_steps, rl_cfg["min_buffer"]))
    print("Epsilon: %.2f -> %.2f (decay=%.4f)" % (agent.epsilon, rl_cfg["epsilon_end"], rl_cfg["epsilon_decay"]))
    print("Checkpoint: %s (every %d episodes)" % (checkpoint_path, checkpoint_freq))
    print("=" * 60)
    print()

    start_time = time.time()

    for ep in range(1, episodes + 1):

        sim = SimStudent(trait_ranges=trait_ranges)
        adapter = SimStudentAdapter(sim)

        episode_reward = 0.0

        for step in range(max_steps):

            # Get state BEFORE action
            state = agent.get_state(adapter).tolist()

            # Agent picks action (explore=True for training)
            action_idx, action = agent.get_action(adapter, explore=True)
            mode, hint, difficulty = action

            # Sim student responds
            correct, response_time = sim.respond(mode, hint, difficulty)

            # Update traits + compute reward (shared math)
            old_k, old_e = update_student_traits(
                sim.traits, sim.concept, correct, response_time, hint, difficulty
            )

            reward = compute_reward(
                sim.traits, sim.concept, correct, response_time, hint, difficulty,
                mode, old_k, old_e
            )

            # Sync adapter so next get_state() sees updated traits
            adapter._sync_from_sim()

            # Get next state
            next_state = agent.get_state(adapter).tolist()

            # Check if episode should end (student too fatigued or disengaged)
            done = (
                sim.traits["fatigue"] > 0.9
                or sim.traits["engagement"] < 0.1
                or sim.traits["frustration"] > 0.9
            )

            # Store and train
            agent.store_transition(state, action_idx, reward, next_state, done)
            agent.train_step()

            episode_reward += reward
            total_steps += 1

            if done:
                break

        reward_window.append(episode_reward)
        avg_reward = sum(reward_window) / len(reward_window)

        # Log
        if ep % log_interval == 0:
            elapsed = time.time() - start_time
            buf_len = len(agent.replay_buffer)
            print(
                "Ep %5d | Avg Reward: %7.2f | Ep Reward: %7.2f | "
                "Eps: %.4f | Buffer: %5d | Steps: %6d | Time: %.0fs"
                % (ep, avg_reward, episode_reward, agent.epsilon, buf_len, total_steps, elapsed)
            )

        # Checkpoint
        if ep % checkpoint_freq == 0:
            agent.save_checkpoint(checkpoint_path)
            if avg_reward > best_avg_reward:
                best_avg_reward = avg_reward
                agent.save_checkpoint(checkpoint_path.replace(".pt", "_best.pt"))
                print("  -> New best avg reward: %.2f (saved _best checkpoint)" % avg_reward)

    # Final checkpoint
    agent.save_checkpoint(checkpoint_path)
    elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print("Total episodes: %d | Total steps: %d | Time: %.1fs" % (episodes, total_steps, elapsed))
    print("Final avg reward (last 100): %.2f" % avg_reward)
    print("Best avg reward: %.2f" % best_avg_reward)
    print("Final epsilon: %.4f | Step counter: %d" % (agent.epsilon, agent.step_counter))
    print("Checkpoint: %s" % checkpoint_path)


# ----------------------------------
# CLI
# ----------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline RL Training for Digital Tutor")
    parser.add_argument("--config", default="configs/default.yaml", help="Config file path")
    parser.add_argument("--episodes", type=int, default=None, help="Override number of episodes")
    args = parser.parse_args()

    train(config_path=args.config, episodes_override=args.episodes)
