"""
Baseline tutoring policies for RL evaluation.

Each policy takes the current student state and returns (mode, hint, difficulty).
These are compared against the trained DQN to verify it learns something meaningful.

Policies:
  - RandomPolicy:           uniform random actions
  - FixedLadderPolicy:      easy -> medium -> hard based on streak
  - MasteryThresholdPolicy: adapts difficulty by mastery/frustration thresholds
"""

import random as rng


# Action space constants (match ProductionTutor)
MODES = [0, 1, 2, 3]         # direct, socratic, reveal_step, challenge
HINTS = [0, 1, 2]
DIFFS = [0.2, 0.4, 0.6]      # easy, medium, hard


class RandomPolicy:
    """Uniform random over the full action space."""

    name = "Random"

    def select_action(self, traits, concept):
        return (
            rng.choice(MODES),
            rng.choice(HINTS),
            rng.choice(DIFFS),
        )


class FixedLadderPolicy:
    """
    Difficulty ladder based on streak.
    - streak < 2:  easy  (0.2), mode=direct, hint=2 (full hints)
    - streak 2-4:  medium (0.4), mode=direct, hint=1 (partial hint)
    - streak >= 5: hard  (0.6), mode=challenge, hint=0 (no hints)

    This is a common "common sense" tutoring heuristic.
    """

    name = "FixedLadder"

    def select_action(self, traits, concept):
        streak = traits.get("streak", 0)

        if streak < 2:
            return (0, 2, 0.2)   # direct, full hint, easy
        elif streak < 5:
            return (0, 1, 0.4)   # direct, partial hint, medium
        else:
            return (3, 0, 0.6)   # challenge, no hint, hard


class MasteryThresholdPolicy:
    """
    Pedagogically-informed policy using mastery and frustration thresholds.

    Rules:
    - If frustration > 0.6:  drop to easy + hints + reveal_step (scaffold)
    - If mastery > 0.7:      push to hard + challenge mode
    - If mastery > 0.4:      medium + socratic probing
    - Else:                  easy + direct + hints

    This models a thoughtful human tutor who reads the room.
    """

    name = "MasteryThreshold"

    def select_action(self, traits, concept):
        mastery = concept.get("knowledge", 0.5)
        frustration = traits.get("frustration", 0.0)
        fatigue = traits.get("fatigue", 0.0)
        confidence = traits.get("confidence", 0.5)

        # Rule 1: Frustrated or fatigued student -> scaffold
        if frustration > 0.6 or fatigue > 0.7:
            return (2, 2, 0.2)   # reveal_step, full hint, easy

        # Rule 2: High mastery + confident -> challenge
        if mastery > 0.7 and confidence > 0.5:
            return (3, 0, 0.6)   # challenge, no hint, hard

        # Rule 3: Moderate mastery -> socratic probing at medium
        if mastery > 0.4:
            hint = 1 if confidence < 0.4 else 0
            return (1, hint, 0.4)   # socratic, adaptive hint, medium

        # Rule 4: Low mastery -> direct instruction with support
        hint = 2 if confidence < 0.3 else 1
        return (0, hint, 0.2)   # direct, hints, easy
