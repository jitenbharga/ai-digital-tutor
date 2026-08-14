"""
Shared 16-dim state vector builder for the DQN agent.

Single source of truth — used by:
  - DQNAgent.get_state()          (models/dqn.py)
  - StudentState.to_vector()      (models/student_state.py)
  - SimStudent.get_state_vector() (training/simulator.py)

All 16 dimensions are guaranteed to be in [0, 1].
"""


def _clamp01(x):
    """Hard clamp to [0, 1]."""
    return max(0.0, min(1.0, float(x)))


# Scaling constants
_LV_MAX = 0.05        # learning_velocity empirical max (~0.002 default, can spike to ~0.05)
_STREAK_MAX = 10.0    # streak cap for normalization
_CONV_TURNS_MAX = 20  # conversation turns cap
_MODE_MAX = 3.0       # last_mode range (0-3)


def build_state_vector(knowledge, learning_velocity, confidence, concept_mastery,
                       engagement, speed, hint_dependency, streak,
                       fatigue, frustration, curiosity, focus,
                       retention, cognitive_load,
                       conversation_turns=0, last_mode=0):
    """
    Build a normalized 16-dim state vector. All outputs in [0, 1].

    Args:
        knowledge: concept knowledge level
        learning_velocity: raw velocity (typically ~0.002, can spike)
        confidence, concept_mastery, engagement, speed, hint_dependency: [0,1] traits
        streak: integer streak count (unbounded)
        fatigue, frustration, curiosity, focus, retention, cognitive_load: [0,1] traits
        conversation_turns: integer turn count
        last_mode: integer 0-3

    Returns:
        list of 16 floats, each in [0, 1]
    """
    return [
        # --- 14 base dims ---
        _clamp01(knowledge),
        _clamp01(learning_velocity / _LV_MAX),   # scaled into usable range
        _clamp01(confidence),
        _clamp01(concept_mastery),

        _clamp01(engagement),
        _clamp01(speed),
        _clamp01(hint_dependency),
        _clamp01(streak / _STREAK_MAX),           # clamped, not just divided

        _clamp01(fatigue),
        _clamp01(frustration),
        _clamp01(curiosity),
        _clamp01(focus),

        _clamp01(retention),
        _clamp01(cognitive_load),

        # --- 2 socratic context dims ---
        _clamp01(conversation_turns / _CONV_TURNS_MAX),
        _clamp01(last_mode / _MODE_MAX),
    ]
