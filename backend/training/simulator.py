"""
Simulated student for offline RL training.

SimStudent responds to (mode, hint, difficulty) with correctness and response_time,
then updates its own traits using the shared math from core/reward.py.
"""

import random
import math

from utils.state_vector import build_state_vector


class SimStudent:
    """
    Lightweight simulated student. Holds traits as a flat dict (no DB, no Concept objects).
    Produces deterministic-ish responses based on current state + action taken.
    """

    def __init__(self, trait_ranges=None):
        """
        Initialize with random traits drawn from trait_ranges.
        trait_ranges: dict of {trait_name: [low, high]}
        """
        defaults = {
            "knowledge": [0.1, 0.8],
            "concept_mastery": [0.1, 0.6],
            "learning_velocity": [0.3, 0.7],
            "confidence": [0.2, 0.8],
            "engagement": [0.3, 0.9],
            "frustration": [0.0, 0.4],
            "streak": [0, 3],
            "fatigue": [0.0, 0.3],
            "cognitive_load": [0.1, 0.4],
            "hint_dependency": [0.0, 0.3],
            "focus": [0.4, 0.8],
            "curiosity": [0.3, 0.7],
            "retention": [0.4, 0.8],
            "speed": [0.3, 0.7],
        }
        ranges = trait_ranges or defaults

        self.traits = {}
        for key, (lo, hi) in ranges.items():
            if key == "streak":
                self.traits[key] = random.randint(int(lo), int(hi))
            else:
                self.traits[key] = random.uniform(lo, hi)

        self.concept = {
            "knowledge": self.traits.pop("knowledge"),
            "concept_mastery": self.traits.pop("concept_mastery"),
        }

        # Socratic context (for state vector)
        self.conversation_turns = 0
        self.last_mode = 0

    # ----------------------------------
    # RESPOND TO AN ACTION
    # ----------------------------------

    def respond(self, mode, hint, difficulty):
        """
        Simulate a student answering a question.

        Returns:
            correct: bool
            response_time: float (seconds)
        """
        knowledge = self.concept["knowledge"]
        focus = self.traits["focus"]
        confidence = self.traits["confidence"]
        fatigue = self.traits["fatigue"]
        frustration = self.traits["frustration"]

        # --- Probability of correct answer ---
        # Base: knowledge vs difficulty gap
        base_p = knowledge - difficulty + 0.5  # centered at 0.5 when matched

        # Hints boost probability
        hint_boost = hint * 0.12

        # Focus and confidence help
        focus_boost = 0.1 * (focus - 0.5)
        conf_boost = 0.05 * (confidence - 0.5)

        # Fatigue and frustration hurt
        fatigue_penalty = -0.15 * fatigue
        frust_penalty = -0.1 * frustration

        # Mode effects
        mode_adj = 0.0
        if mode == 1:  # Socratic: harder without hints
            mode_adj = -0.08 if hint == 0 else 0.0
        elif mode == 2:  # Reveal step: scaffold helps
            mode_adj = 0.06
        elif mode == 3:  # Challenge: harder
            mode_adj = -0.12

        p_correct = base_p + hint_boost + focus_boost + conf_boost + fatigue_penalty + frust_penalty + mode_adj
        p_correct = max(0.05, min(0.95, p_correct))  # clamp

        correct = random.random() < p_correct

        # --- Response time ---
        # Harder questions + fatigue = slower
        base_time = 3.0 + 8.0 * difficulty + 5.0 * fatigue
        # Hints speed things up
        base_time -= hint * 1.5
        # Knowledge speeds things up
        base_time -= 3.0 * knowledge
        # Add noise
        response_time = max(1.0, base_time + random.gauss(0, 1.5))

        # Update conversation context
        self.conversation_turns += 1
        self.last_mode = mode

        return correct, response_time

    # ----------------------------------
    # STATE VECTOR (uses shared helper)
    # ----------------------------------

    def get_state_vector(self):
        """Return 16-dim state vector matching DQNAgent.get_state()."""

        return build_state_vector(
            knowledge=self.concept["knowledge"],
            learning_velocity=self.traits["learning_velocity"],
            confidence=self.traits["confidence"],
            concept_mastery=self.concept["concept_mastery"],
            engagement=self.traits["engagement"],
            speed=self.traits["speed"],
            hint_dependency=self.traits["hint_dependency"],
            streak=self.traits["streak"],
            fatigue=self.traits["fatigue"],
            frustration=self.traits["frustration"],
            curiosity=self.traits["curiosity"],
            focus=self.traits["focus"],
            retention=self.traits["retention"],
            cognitive_load=self.traits["cognitive_load"],
            conversation_turns=self.conversation_turns,
            last_mode=self.last_mode,
        )

    # ----------------------------------
    # RESET FOR NEW EPISODE
    # ----------------------------------

    def reset(self, trait_ranges=None):
        """Re-randomize all traits for a new episode."""
        self.__init__(trait_ranges=trait_ranges)
