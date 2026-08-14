"""
Shared reward computation and student-state update math.

Used by both ProductionTutor.learn() and the offline training simulator.
All functions are pure (no DB, no async) — they mutate trait dicts in-place
and return the computed reward.
"""

import math


# ----------------------------------
# TEACHING MODE CONSTANTS
# ----------------------------------
MODE_DIRECT_QUESTION = 0
MODE_SOCRATIC_PROBE = 1
MODE_REVEAL_STEP = 2
MODE_CHALLENGE = 3


# ----------------------------------
# HELPERS
# ----------------------------------

def smooth_clip(x):
    """Sigmoid-based soft clamp to [0, 1]."""
    return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-4.0 * (x - 0.5)))))


# ----------------------------------
# STUDENT STATE UPDATE (MUTATES IN-PLACE)
# ----------------------------------

def update_student_traits(traits, concept, correct, time_taken, hint_used, difficulty,
                          mark_reviewed_fn=None):
    """
    Update student traits and concept state after an answer.

    Args:
        traits: dict with keys: learning_velocity, confidence, engagement, frustration,
                streak, fatigue, cognitive_load, hint_dependency, focus, curiosity,
                retention, speed
        concept: dict with keys: knowledge, concept_mastery
        correct: bool
        time_taken: float (seconds)
        hint_used: int (0, 1, or 2)
        difficulty: float (0.2, 0.4, 0.6)
        mark_reviewed_fn: optional callable(concept) for spaced repetition tracking

    Returns:
        (old_knowledge, old_engagement) — snapshots before update, needed for reward.
    """
    old_knowledge = concept["knowledge"]
    old_engagement = traits["engagement"]

    # =========================================================
    # 1. KNOWLEDGE + MASTERY (CONCEPT LEVEL)
    # =========================================================
    learning_rate = 0.08 + 0.12 * traits["focus"]

    if correct:
        concept["knowledge"] += learning_rate * (1.0 - concept["knowledge"])
        concept["concept_mastery"] += 0.06 * (1.0 - concept["concept_mastery"])
        if mark_reviewed_fn is not None:
            mark_reviewed_fn(concept)
    else:
        concept["knowledge"] -= 0.06 * concept["knowledge"]
        concept["concept_mastery"] -= 0.05 * concept["concept_mastery"]

    # =========================================================
    # 2. LEARNING VELOCITY
    # =========================================================
    knowledge_gain = concept["knowledge"] - old_knowledge
    alpha = 0.2
    traits["learning_velocity"] = (
        (1 - alpha) * traits["learning_velocity"]
        + alpha * knowledge_gain / max(1, time_taken)
    )

    # =========================================================
    # 3. GLOBAL BEHAVIOR
    # =========================================================
    if correct:
        traits["engagement"] += 0.1 * (1.0 - traits["engagement"])
    else:
        traits["engagement"] -= 0.12 * traits["engagement"]

    if correct:
        traits["confidence"] += 0.08 * (1.0 - traits["confidence"])
    else:
        traits["confidence"] -= 0.1 * traits["confidence"]

    if correct:
        traits["frustration"] -= 0.12 * traits["frustration"]
    else:
        traits["frustration"] += 0.15 * (1.0 - traits["frustration"])

    traits["streak"] = traits["streak"] + 1 if correct else 0

    # =========================================================
    # 4. FATIGUE + COGNITIVE LOAD
    # =========================================================
    if difficulty < 0.3:
        level = "easy"
    elif difficulty < 0.5:
        level = "medium"
    else:
        level = "hard"

    max_time = {"easy": 20, "medium": 40, "hard": 90}.get(level, 40)
    time_ratio = min(1.0, time_taken / max_time)
    traits["fatigue"] += 0.04 * difficulty + 0.02 * time_ratio
    traits["cognitive_load"] += 0.1 * difficulty + 0.05 * hint_used

    # =========================================================
    # 5. HINT DEPENDENCY
    # =========================================================
    traits["hint_dependency"] += 0.08 * hint_used

    # =========================================================
    # 6. COUPLED HUMAN EFFECTS
    # =========================================================
    traits["focus"] -= 0.4 * traits["fatigue"]
    traits["engagement"] -= 0.3 * traits["frustration"]
    traits["curiosity"] += 0.25 * traits["confidence"]
    traits["retention"] -= 0.2 * traits["cognitive_load"]
    traits["speed"] = 0.5 * traits["confidence"] + 0.5 * (1.0 - traits["fatigue"])

    # =========================================================
    # 7. APPLY BOUNDS
    # =========================================================
    concept["knowledge"] = smooth_clip(concept["knowledge"])
    concept["concept_mastery"] = smooth_clip(concept["concept_mastery"])

    for key in ["learning_velocity", "engagement", "confidence", "frustration",
                "fatigue", "focus", "curiosity", "hint_dependency", "retention",
                "cognitive_load", "speed"]:
        traits[key] = smooth_clip(traits[key])

    return old_knowledge, old_engagement


# ----------------------------------
# REWARD COMPUTATION
# ----------------------------------

def compute_reward(traits, concept, correct, time_taken, hint, difficulty, mode,
                   old_knowledge, old_engagement):
    """
    Compute the RL reward after student state has been updated.

    Args:
        traits: updated student traits dict
        concept: updated concept dict
        correct: bool
        time_taken: float
        hint: int (0, 1, 2)
        difficulty: float
        mode: int (0-3)
        old_knowledge: float (before update)
        old_engagement: float (before update)

    Returns:
        float reward
    """
    knowledge_gain = concept["knowledge"] - old_knowledge
    engagement_delta = traits["engagement"] - old_engagement

    challenge_match = 1.0 - abs(difficulty - concept["knowledge"])
    hint_cost = hint * 0.05
    hint_effect = hint_cost * ((1.0 - concept["knowledge"]) - 0.5)

    # Speed bonus
    if correct:
        if time_taken < 2:
            speed_bonus = 0.5
        elif time_taken < 5:
            speed_bonus = 0.2
        else:
            speed_bonus = 0.0
    else:
        speed_bonus = -0.1 if time_taken > 8 else 0.0

    # Streak bonus
    streak_bonus = min(0.5, 0.05 * traits["streak"])

    # =========================================================
    # MODE-SPECIFIC REWARD SHAPING
    # =========================================================
    mode_bonus = 0.0

    if mode == MODE_SOCRATIC_PROBE:
        if correct and hint == 0:
            mode_bonus = 0.8
        elif correct:
            mode_bonus = 0.3
        else:
            mode_bonus = -0.1
        mode_bonus += 0.15 * traits["engagement"]

    elif mode == MODE_REVEAL_STEP:
        if correct:
            mode_bonus = 0.4
        else:
            mode_bonus = 0.1

    elif mode == MODE_CHALLENGE:
        if correct:
            mode_bonus = 1.0 * difficulty
        else:
            mode_bonus = 0.0
        if traits["frustration"] > 0.6:
            mode_bonus -= 0.5

    # Final reward
    reward = (
        8.0 * knowledge_gain
        + 2.0 * engagement_delta
        + 1.0 * challenge_match
        + speed_bonus
        + hint_effect
        + streak_bonus
        + mode_bonus
    )

    return reward
