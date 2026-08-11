"""
Lightweight RL observability: tracks action distribution, reward, and loss.

No external dependencies — pure Python with collections.deque for rolling windows.
Designed to be embedded in DQNAgent.
"""

import time
from collections import deque


class RLMetrics:
    """
    Rolling counters for RL observability.

    Tracks:
    - Action distribution (mode, hint, difficulty counts)
    - Rolling mean reward (last N learn() calls)
    - Rolling mean loss (last N train steps)
    - Decision count, learn count
    """

    def __init__(self, reward_window=500, loss_window=500):
        # Rolling reward/loss
        self.rewards = deque(maxlen=reward_window)
        self.losses = deque(maxlen=loss_window)

        # Action distribution counters
        self.mode_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.hint_counts = {0: 0, 1: 0, 2: 0}
        self.difficulty_counts = {}  # keyed by float (0.2, 0.4, 0.6)

        # Totals
        self.total_decisions = 0
        self.total_learns = 0
        self.total_train_steps = 0

        # Timestamps
        self.created_at = time.time()
        self.last_decision_at = None
        self.last_learn_at = None

    # ----------------------------------
    # RECORD EVENTS
    # ----------------------------------

    def record_decision(self, mode, hint, difficulty, epsilon):
        """Called after every get_action() in production."""
        self.total_decisions += 1
        self.last_decision_at = time.time()

        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1
        self.hint_counts[hint] = self.hint_counts.get(hint, 0) + 1

        # Round difficulty to avoid float key issues
        d_key = round(difficulty, 2)
        self.difficulty_counts[d_key] = self.difficulty_counts.get(d_key, 0) + 1

    def record_reward(self, reward):
        """Called after every learn() call."""
        self.rewards.append(reward)
        self.total_learns += 1
        self.last_learn_at = time.time()

    def record_loss(self, loss_value):
        """Called after every successful train_step() with actual gradient update."""
        self.losses.append(loss_value)
        self.total_train_steps += 1

    # ----------------------------------
    # QUERY
    # ----------------------------------

    def mean_reward(self):
        if not self.rewards:
            return 0.0
        return sum(self.rewards) / len(self.rewards)

    def mean_loss(self):
        if not self.losses:
            return 0.0
        return sum(self.losses) / len(self.losses)

    def action_distribution(self):
        """Return normalized action distribution."""
        total = max(1, self.total_decisions)

        mode_names = {
            0: "direct_question",
            1: "socratic_probe",
            2: "reveal_step",
            3: "challenge",
        }

        return {
            "mode": {
                mode_names.get(k, str(k)): round(v / total, 4)
                for k, v in sorted(self.mode_counts.items())
            },
            "hint": {
                str(k): round(v / total, 4)
                for k, v in sorted(self.hint_counts.items())
            },
            "difficulty": {
                str(k): round(v / total, 4)
                for k, v in sorted(self.difficulty_counts.items())
            },
        }

    def snapshot(self, epsilon, step_counter):
        """Full stats snapshot for the /rl-stats endpoint."""
        uptime = time.time() - self.created_at

        return {
            "epsilon": round(epsilon, 6),
            "step_counter": step_counter,
            "total_decisions": self.total_decisions,
            "total_learns": self.total_learns,
            "total_train_steps": self.total_train_steps,
            "mean_reward": round(self.mean_reward(), 4),
            "mean_loss": round(self.mean_loss(), 6),
            "reward_window_size": len(self.rewards),
            "loss_window_size": len(self.losses),
            "action_distribution": self.action_distribution(),
            "uptime_seconds": round(uptime, 1),
            "last_decision_at": self.last_decision_at,
            "last_learn_at": self.last_learn_at,
        }
