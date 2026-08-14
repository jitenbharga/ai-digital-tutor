"""
T1.4 — RL reward + gamification logic tests (deterministic, no torch/LLM/DB).

Covers:
  * core/reward.py           — smooth_clip bounds/monotonicity; compute_reward shaping
  * api/inference.py         — _check_dqn_gate serving guard (fails closed)
  * core/gamification.py     — streak state machine (continue/reset/freeze/advance)
  * core/daily_quests.py     — quest completion thresholding
"""
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from core import reward as reward_mod
from core import gamification as gam
from core import daily_quests as dq

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)  # noon → past grace cutoff


def _fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def _base_traits(streak=0, engagement=0.5, frustration=0.0):
    return {"engagement": engagement, "streak": streak, "frustration": frustration}


# ───────────────────────── reward: smooth_clip ─────────────────────────

class TestSmoothClip:
    def test_bounded_0_1_over_realistic_domain(self):
        # smooth_clip receives trait/knowledge values, which live in ~[0, 1];
        # test a generous margin around that. (Extreme |x| overflows — see below.)
        for x in (-5, -1, -0.25, 0, 0.5, 1, 1.25, 5):
            assert 0.0 <= reward_mod.smooth_clip(x) <= 1.0

    def test_monotonic_nondecreasing(self):
        xs = [i / 20.0 for i in range(-40, 41)]
        ys = [reward_mod.smooth_clip(x) for x in xs]
        assert all(b >= a - 1e-12 for a, b in zip(ys, ys[1:]))

    def test_midpoint_is_half(self):
        assert reward_mod.smooth_clip(0.5) == pytest.approx(0.5)

    @pytest.mark.xfail(
        raises=OverflowError, strict=True,
        reason="LATENT BUG: smooth_clip() calls math.exp(-4*(x-0.5)) with no guard, "
               "so it raises OverflowError for x < ~-177 instead of clamping to 0.0. "
               "Not reachable with normal [0,1] inputs. Fix: clamp the exponent or "
               "except OverflowError -> 0.0. This xfail flips to xpass once fixed.",
    )
    def test_smooth_clip_extreme_negative_should_clamp_not_crash(self):
        assert reward_mod.smooth_clip(-1e6) == pytest.approx(0.0)


# ───────────────────────── reward: compute_reward ─────────────────────────

class TestComputeReward:
    def _reward(self, *, knowledge, old_knowledge, streak=0, correct=True,
                time_taken=3.0, hint=0, difficulty=0.5, engagement=0.5, old_engagement=0.5):
        traits = _base_traits(streak=streak, engagement=engagement)
        concept = {"knowledge": knowledge}
        return reward_mod.compute_reward(
            traits, concept, correct, time_taken, hint, difficulty,
            reward_mod.MODE_DIRECT_QUESTION, old_knowledge, old_engagement,
        )

    def test_reward_increases_with_knowledge_gain(self):
        low = self._reward(knowledge=0.40, old_knowledge=0.40)   # gain 0
        high = self._reward(knowledge=0.60, old_knowledge=0.40)  # gain +0.2
        assert high > low

    def test_faster_correct_answer_scores_at_least_as_high(self):
        fast = self._reward(knowledge=0.5, old_knowledge=0.5, time_taken=1.0)
        slow = self._reward(knowledge=0.5, old_knowledge=0.5, time_taken=6.0)
        assert fast >= slow
        assert fast - slow == pytest.approx(0.5)  # speed_bonus 0.5 vs 0.0

    def test_streak_bonus_is_monotonic_and_capped(self):
        r0 = self._reward(knowledge=0.5, old_knowledge=0.5, streak=0)
        r6 = self._reward(knowledge=0.5, old_knowledge=0.5, streak=6)
        r100 = self._reward(knowledge=0.5, old_knowledge=0.5, streak=100)
        assert r6 - r0 == pytest.approx(0.05 * 6)      # linear below the cap
        assert r100 - r0 == pytest.approx(0.5)         # capped at 0.5, not 5.0
        assert r100 >= r6 >= r0


# ───────────────────────── DQN serving gate ─────────────────────────

class TestDQNServingGate:
    """R9: only serve the learned DQN policy if it beats pedagogical baselines;
    otherwise fall back (gate returns False). Fails closed on any error."""

    def _gate_with(self, monkeypatch, impl):
        fake = types.ModuleType("training.eval_policies")
        fake.check_dqn_beats_baselines = impl
        monkeypatch.setitem(sys.modules, "training", types.ModuleType("training"))
        monkeypatch.setitem(sys.modules, "training.eval_policies", fake)
        from api.inference import ProductionTutor
        # _check_dqn_gate doesn't touch instance state — call it unbound.
        return ProductionTutor._check_dqn_gate(object())

    def test_gate_false_when_policy_does_not_beat_baseline(self, monkeypatch):
        assert self._gate_with(monkeypatch, lambda path: False) is False

    def test_gate_true_when_policy_beats_baseline(self, monkeypatch):
        assert self._gate_with(monkeypatch, lambda path: True) is True

    def test_gate_fails_closed_on_error(self, monkeypatch):
        def boom(path):
            raise RuntimeError("eval blew up")
        assert self._gate_with(monkeypatch, boom) is False


# ───────────────────────── streak state machine ─────────────────────────

class TestStreakStateMachine:
    def test_continues_when_active_yesterday(self):
        state = {"streak": 5, "last_active_date": _fmt(NOW - timedelta(days=1))}
        out = gam.compute_streak(state, NOW)
        assert out["streak_alive"] is True and out["streak"] == 5

    def test_resets_with_no_history(self):
        out = gam.compute_streak({}, NOW)
        assert out["streak_alive"] is False and out["streak"] == 0

    def test_freeze_used_to_save_streak_after_gap(self):
        state = {
            "streak": 5,
            "last_active_date": _fmt(NOW - timedelta(days=3)),
            "streak_freezes_used_this_week": 0,
            "freeze_week_start": NOW.isoformat(),
        }
        out = gam.compute_streak(state, NOW)
        assert out["streak_alive"] is True
        assert out["streak_freezes_used_this_week"] == 1
        assert out["streak"] == 5

    def test_breaks_when_freezes_exhausted(self):
        state = {
            "streak": 5,
            "last_active_date": _fmt(NOW - timedelta(days=3)),
            "streak_freezes_used_this_week": gam.MAX_STREAK_FREEZES,
            "freeze_week_start": NOW.isoformat(),
        }
        out = gam.compute_streak(state, NOW)
        assert out["streak_alive"] is False and out["streak"] == 0

    def test_advance_increments_on_new_day(self):
        state = {"streak": 5, "last_active_date": _fmt(NOW - timedelta(days=1))}
        out = gam.advance_streak(state, NOW)
        assert out["streak"] == 6 and out["last_active_date"] == _fmt(NOW)

    def test_advance_does_not_double_count_same_day(self):
        state = {"streak": 5, "last_active_date": _fmt(NOW)}
        out = gam.advance_streak(state, NOW)
        assert out["streak"] == 5


# ───────────────────────── quest completion ─────────────────────────

class TestQuestCompletion:
    def _quest(self, target=5, metric="answers_done", topic=""):
        return {"metric": metric, "target": target, "topic": topic, "progress": 0, "completed": False}

    def test_incomplete_below_target(self):
        out = dq.check_quest_progress(self._quest(target=5), {}, {"answers_done": 3})
        assert out["completed"] is False and out["progress"] == 3

    def test_complete_at_target(self):
        out = dq.check_quest_progress(self._quest(target=5), {}, {"answers_done": 5})
        assert out["completed"] is True and out["progress"] == 5

    def test_progress_capped_at_target(self):
        out = dq.check_quest_progress(self._quest(target=5), {}, {"answers_done": 10})
        assert out["completed"] is True and out["progress"] == 5
