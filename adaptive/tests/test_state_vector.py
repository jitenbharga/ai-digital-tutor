"""
Test that all 16 state vector dimensions are bounded to [0, 1]
for a wide range of random student states, including edge cases.
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adaptive.utils.state_vector import build_state_vector
from training.simulator import SimStudent
from adaptive.models.student_state import StudentState


# ----------------------------------
# TEST 1: Random SimStudents
# ----------------------------------

def test_sim_student_state_vector_bounds():
    """All 16 dims should be in [0, 1] for 1000 random SimStudents."""
    for i in range(1000):
        sim = SimStudent()
        # Run a few random steps to push traits around
        for _ in range(random.randint(0, 20)):
            sim.respond(
                mode=random.randint(0, 3),
                hint=random.randint(0, 2),
                difficulty=random.choice([0.2, 0.4, 0.6]),
            )
        vec = sim.get_state_vector()
        assert len(vec) == 16, "Expected 16 dims, got %d" % len(vec)
        for j, val in enumerate(vec):
            assert 0.0 <= val <= 1.0, (
                "Dim %d out of bounds: %.6f (iter %d)" % (j, val, i)
            )


# ----------------------------------
# TEST 2: Edge-case inputs
# ----------------------------------

def test_edge_case_inputs():
    """Extreme values should still produce [0, 1] outputs."""
    edge_cases = [
        # All zeros
        dict(knowledge=0, learning_velocity=0, confidence=0, concept_mastery=0,
             engagement=0, speed=0, hint_dependency=0, streak=0,
             fatigue=0, frustration=0, curiosity=0, focus=0,
             retention=0, cognitive_load=0, conversation_turns=0, last_mode=0),
        # All ones / high
        dict(knowledge=1, learning_velocity=1.0, confidence=1, concept_mastery=1,
             engagement=1, speed=1, hint_dependency=1, streak=100,
             fatigue=1, frustration=1, curiosity=1, focus=1,
             retention=1, cognitive_load=1, conversation_turns=100, last_mode=3),
        # Negative values (shouldn't happen but should be clamped)
        dict(knowledge=-0.5, learning_velocity=-0.01, confidence=-1, concept_mastery=-0.3,
             engagement=-1, speed=-1, hint_dependency=-1, streak=-5,
             fatigue=-1, frustration=-1, curiosity=-1, focus=-1,
             retention=-1, cognitive_load=-1, conversation_turns=-10, last_mode=-1),
        # Very large values
        dict(knowledge=50, learning_velocity=10, confidence=99, concept_mastery=50,
             engagement=50, speed=50, hint_dependency=50, streak=9999,
             fatigue=50, frustration=50, curiosity=50, focus=50,
             retention=50, cognitive_load=50, conversation_turns=1000, last_mode=99),
    ]

    for i, kwargs in enumerate(edge_cases):
        vec = build_state_vector(**kwargs)
        assert len(vec) == 16
        for j, val in enumerate(vec):
            assert 0.0 <= val <= 1.0, (
                "Edge case %d, dim %d out of bounds: %.6f" % (i, j, val)
            )


# ----------------------------------
# TEST 3: StudentState.to_vector() matches build_state_vector
# ----------------------------------

def test_student_state_to_vector_bounds():
    """StudentState.to_vector() should produce 16 dims all in [0, 1]."""
    for _ in range(100):
        ss = StudentState(
            student_id="test_%d" % random.randint(0, 9999),
            learning_velocity=random.uniform(-0.01, 0.1),
            confidence=random.uniform(0, 1),
            engagement=random.uniform(0, 1),
            speed=random.uniform(0, 1),
            hint_dependency=random.uniform(0, 1),
            streak=random.randint(0, 20),
            fatigue=random.uniform(0, 1),
            frustration=random.uniform(0, 1),
            curiosity=random.uniform(0, 1),
            focus=random.uniform(0, 1),
            retention=random.uniform(0, 1),
            cognitive_load=random.uniform(0, 1),
        )
        ss.conversation_turns = random.randint(0, 50)
        ss.last_mode = random.randint(0, 3)

        vec = ss.to_vector()
        assert len(vec) == 16
        for j, val in enumerate(vec):
            assert 0.0 <= val <= 1.0, (
                "StudentState dim %d out of bounds: %.6f" % (j, val)
            )


# ----------------------------------
# TEST 4: SimStudent and StudentState produce identical vectors for same inputs
# ----------------------------------

def test_vectors_match():
    """SimStudent.get_state_vector() and StudentState.to_vector() should match for same inputs."""
    for _ in range(50):
        # Create matching states
        k = random.uniform(0, 1)
        m = random.uniform(0, 1)
        lv = random.uniform(0, 0.05)
        conf = random.uniform(0, 1)
        eng = random.uniform(0, 1)
        spd = random.uniform(0, 1)
        hd = random.uniform(0, 1)
        streak = random.randint(0, 15)
        fat = random.uniform(0, 1)
        frust = random.uniform(0, 1)
        cur = random.uniform(0, 1)
        foc = random.uniform(0, 1)
        ret = random.uniform(0, 1)
        cl = random.uniform(0, 1)
        ct = random.randint(0, 30)
        lm = random.randint(0, 3)

        # Via build_state_vector directly
        vec_direct = build_state_vector(
            knowledge=k, learning_velocity=lv, confidence=conf, concept_mastery=m,
            engagement=eng, speed=spd, hint_dependency=hd, streak=streak,
            fatigue=fat, frustration=frust, curiosity=cur, focus=foc,
            retention=ret, cognitive_load=cl, conversation_turns=ct, last_mode=lm,
        )

        # Via StudentState
        ss = StudentState(student_id="test")
        c = ss.get_current_concept()
        c.knowledge = k
        c.concept_mastery = m
        ss.learning_velocity = lv
        ss.confidence = conf
        ss.engagement = eng
        ss.speed = spd
        ss.hint_dependency = hd
        ss.streak = streak
        ss.fatigue = fat
        ss.frustration = frust
        ss.curiosity = cur
        ss.focus = foc
        ss.retention = ret
        ss.cognitive_load = cl
        ss.conversation_turns = ct
        ss.last_mode = lm
        vec_ss = ss.to_vector()

        for j in range(16):
            assert abs(vec_direct[j] - vec_ss[j]) < 1e-9, (
                "Mismatch at dim %d: direct=%.10f, ss=%.10f" % (j, vec_direct[j], vec_ss[j])
            )


if __name__ == "__main__":
    test_sim_student_state_vector_bounds()
    print("test_sim_student_state_vector_bounds: PASS")

    test_edge_case_inputs()
    print("test_edge_case_inputs: PASS")

    test_student_state_to_vector_bounds()
    print("test_student_state_to_vector_bounds: PASS")

    test_vectors_match()
    print("test_vectors_match: PASS")

    print("\nAll state vector tests passed.")
