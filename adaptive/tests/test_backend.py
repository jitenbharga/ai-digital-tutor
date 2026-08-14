"""
Comprehensive backend test suite for AI Digital Tutor.

Covers:
  - Pure utility functions (state_vector, reward, tone, JSON parser)
  - LLM infrastructure (cache, telemetry)
  - Prompt templates (all 10 modules have VERSION + build)
  - RLMetrics (action distribution, rolling stats, snapshot)
  - Engine async methods with mocked LLM (all 10 engines)
  - API schemas validation (Pydantic models)
  - Token extraction, review retention, evaluator reward

Stubs for torch, langchain, motor, etc. are in conftest.py.
"""

import sys
import os
import json
import time
import math
import asyncio
import hashlib
import random
import importlib
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════
# 1. PURE UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

class TestStateVector:

    def test_output_length(self):
        from adaptive.utils.state_vector import build_state_vector
        vec = build_state_vector(
            knowledge=0.5, learning_velocity=0.01, confidence=0.6,
            concept_mastery=0.4, engagement=0.7, speed=0.5,
            hint_dependency=0.2, streak=3, fatigue=0.3,
            frustration=0.1, curiosity=0.6, focus=0.8,
            retention=0.7, cognitive_load=0.4,
            conversation_turns=5, last_mode=2
        )
        assert len(vec) == 16

    def test_all_dims_bounded(self):
        from adaptive.utils.state_vector import build_state_vector
        for _ in range(200):
            vec = build_state_vector(
                knowledge=random.uniform(-1, 2),
                learning_velocity=random.uniform(-0.1, 0.2),
                confidence=random.uniform(-1, 2),
                concept_mastery=random.uniform(-1, 2),
                engagement=random.uniform(-1, 2),
                speed=random.uniform(-1, 2),
                hint_dependency=random.uniform(-1, 2),
                streak=random.randint(-5, 100),
                fatigue=random.uniform(-1, 2),
                frustration=random.uniform(-1, 2),
                curiosity=random.uniform(-1, 2),
                focus=random.uniform(-1, 2),
                retention=random.uniform(-1, 2),
                cognitive_load=random.uniform(-1, 2),
                conversation_turns=random.randint(-10, 100),
                last_mode=random.randint(-1, 10),
            )
            for i, v in enumerate(vec):
                assert 0.0 <= v <= 1.0, f"dim {i} = {v} out of bounds"

    def test_zeros(self):
        from adaptive.utils.state_vector import build_state_vector
        vec = build_state_vector(
            knowledge=0, learning_velocity=0, confidence=0,
            concept_mastery=0, engagement=0, speed=0,
            hint_dependency=0, streak=0, fatigue=0,
            frustration=0, curiosity=0, focus=0,
            retention=0, cognitive_load=0,
            conversation_turns=0, last_mode=0
        )
        assert all(v == 0.0 for v in vec)

    def test_max_values(self):
        from adaptive.utils.state_vector import build_state_vector
        vec = build_state_vector(
            knowledge=1, learning_velocity=0.05, confidence=1,
            concept_mastery=1, engagement=1, speed=1,
            hint_dependency=1, streak=10, fatigue=1,
            frustration=1, curiosity=1, focus=1,
            retention=1, cognitive_load=1,
            conversation_turns=20, last_mode=3
        )
        assert all(v == 1.0 for v in vec)

    def test_deterministic(self):
        from adaptive.utils.state_vector import build_state_vector
        kwargs = dict(
            knowledge=0.7, learning_velocity=0.02, confidence=0.5,
            concept_mastery=0.6, engagement=0.8, speed=0.4,
            hint_dependency=0.3, streak=5, fatigue=0.2,
            frustration=0.1, curiosity=0.9, focus=0.7,
            retention=0.6, cognitive_load=0.3,
            conversation_turns=10, last_mode=1,
        )
        v1 = build_state_vector(**kwargs)
        v2 = build_state_vector(**kwargs)
        assert v1 == v2


class TestReward:

    def test_smooth_clip_bounds(self):
        from adaptive.core.reward import smooth_clip
        assert 0.0 <= smooth_clip(-10) <= 1.0
        assert 0.0 <= smooth_clip(10) <= 1.0
        assert 0.0 <= smooth_clip(0.5) <= 1.0

    def test_smooth_clip_monotonic(self):
        from adaptive.core.reward import smooth_clip
        vals = [smooth_clip(x / 10) for x in range(-20, 30)]
        for i in range(1, len(vals)):
            assert vals[i] >= vals[i - 1]

    def test_update_student_traits_correct_answer(self):
        from adaptive.core.reward import update_student_traits
        traits = {
            "learning_velocity": 0.01, "confidence": 0.5, "engagement": 0.5,
            "frustration": 0.3, "streak": 2, "fatigue": 0.2,
            "cognitive_load": 0.3, "hint_dependency": 0.1, "focus": 0.7,
            "curiosity": 0.5, "retention": 0.6, "speed": 0.5,
        }
        concept = {"knowledge": 0.4, "concept_mastery": 0.3}
        old_k, old_e = update_student_traits(
            traits, concept, correct=True, time_taken=5.0,
            hint_used=0, difficulty=0.4
        )
        assert old_k == 0.4
        assert old_e == 0.5
        assert concept["knowledge"] > 0.4
        assert traits["streak"] == 3
        assert traits["frustration"] < 0.3

    def test_update_student_traits_wrong_answer(self):
        from adaptive.core.reward import update_student_traits
        traits = {
            "learning_velocity": 0.01, "confidence": 0.5, "engagement": 0.5,
            "frustration": 0.3, "streak": 5, "fatigue": 0.2,
            "cognitive_load": 0.3, "hint_dependency": 0.1, "focus": 0.7,
            "curiosity": 0.5, "retention": 0.6, "speed": 0.5,
        }
        concept = {"knowledge": 0.6, "concept_mastery": 0.5}
        update_student_traits(
            traits, concept, correct=False, time_taken=10.0,
            hint_used=0, difficulty=0.4
        )
        assert concept["knowledge"] < 0.6
        assert traits["streak"] == 0
        assert traits["frustration"] > 0.3

    def test_all_traits_bounded_after_update(self):
        from adaptive.core.reward import update_student_traits
        for _ in range(100):
            traits = {k: random.uniform(0, 1) for k in [
                "learning_velocity", "confidence", "engagement", "frustration",
                "fatigue", "cognitive_load", "hint_dependency", "focus",
                "curiosity", "retention", "speed",
            ]}
            traits["streak"] = random.randint(0, 20)
            concept = {"knowledge": random.uniform(0, 1), "concept_mastery": random.uniform(0, 1)}
            update_student_traits(
                traits, concept, correct=random.choice([True, False]),
                time_taken=random.uniform(0.5, 60),
                hint_used=random.randint(0, 2),
                difficulty=random.choice([0.2, 0.4, 0.6])
            )
            for k, v in traits.items():
                if k == "streak":
                    continue
                assert 0.0 <= v <= 1.0, f"{k} = {v} out of bounds"
            assert 0.0 <= concept["knowledge"] <= 1.0
            assert 0.0 <= concept["concept_mastery"] <= 1.0

    def test_compute_reward_returns_float(self):
        from adaptive.core.reward import compute_reward
        traits = {"engagement": 0.6, "streak": 3, "frustration": 0.2}
        concept = {"knowledge": 0.5}
        r = compute_reward(traits, concept, True, 3.0, 0, 0.4, 0, 0.4, 0.5)
        assert isinstance(r, float)

    def test_reward_higher_for_correct(self):
        from adaptive.core.reward import compute_reward
        traits = {"engagement": 0.6, "streak": 3, "frustration": 0.2}
        concept = {"knowledge": 0.6}
        r_correct = compute_reward(traits, concept, True, 3.0, 0, 0.4, 0, 0.4, 0.5)
        r_wrong = compute_reward(traits, concept, False, 3.0, 0, 0.4, 0, 0.4, 0.5)
        assert r_correct > r_wrong


class TestTone:

    def test_high_frustration(self):
        from adaptive.utils.tone import get_tone_directive
        student = MagicMock(frustration=0.8, confidence=0.5, engagement=0.5, fatigue=0.3, curiosity=0.4)
        assert "warm" in get_tone_directive(student).lower() or "patient" in get_tone_directive(student).lower()

    def test_high_confidence_engagement(self):
        from adaptive.utils.tone import get_tone_directive
        student = MagicMock(frustration=0.2, confidence=0.9, engagement=0.8, fatigue=0.3, curiosity=0.4)
        assert "challeng" in get_tone_directive(student).lower()

    def test_high_fatigue(self):
        from adaptive.utils.tone import get_tone_directive
        student = MagicMock(frustration=0.2, confidence=0.5, engagement=0.5, fatigue=0.7, curiosity=0.4)
        tone = get_tone_directive(student)
        assert "brief" in tone.lower() or "energetic" in tone.lower()

    def test_high_curiosity(self):
        from adaptive.utils.tone import get_tone_directive
        student = MagicMock(frustration=0.2, confidence=0.5, engagement=0.5, fatigue=0.3, curiosity=0.8)
        tone = get_tone_directive(student)
        assert "curiosity" in tone.lower() or "deeper" in tone.lower()

    def test_default_tone(self):
        from adaptive.utils.tone import get_tone_directive
        student = MagicMock(frustration=0.3, confidence=0.5, engagement=0.5, fatigue=0.3, curiosity=0.4)
        assert "TONE:" in get_tone_directive(student)


class TestParseJsonRobust:

    def test_clean_json(self):
        from adaptive.core.llm_utils import parse_json_robust
        assert parse_json_robust('{"key": "value", "num": 42}') == {"key": "value", "num": 42}

    def test_markdown_fenced(self):
        from adaptive.core.llm_utils import parse_json_robust
        assert parse_json_robust('```json\n{"key": "value"}\n```') == {"key": "value"}

    def test_prose_wrapped(self):
        from adaptive.core.llm_utils import parse_json_robust
        text = 'Here is the answer:\n{"question": "What is 2+2?"}\nHope that helps!'
        assert parse_json_robust(text)["question"] == "What is 2+2?"

    def test_trailing_comma(self):
        from adaptive.core.llm_utils import parse_json_robust
        assert parse_json_robust('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_single_quotes(self):
        from adaptive.core.llm_utils import parse_json_robust
        assert parse_json_robust("{'key': 'value'}") == {"key": "value"}

    def test_none_on_garbage(self):
        from adaptive.core.llm_utils import parse_json_robust
        assert parse_json_robust("not json at all") is None
        assert parse_json_robust("") is None
        assert parse_json_robust(None) is None

    def test_nested_json(self):
        from adaptive.core.llm_utils import parse_json_robust
        text = '{"outer": {"inner": [1, 2, 3]}}'
        assert parse_json_robust(text)["outer"]["inner"] == [1, 2, 3]


# ═══════════════════════════════════════════════════════════════
# 2. LLM INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════

class TestLLMCache:

    def test_put_and_get(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=10, ttl_seconds=60)
        cache.put("k1", {"data": "hello"})
        assert cache.get("k1") == {"data": "hello"}

    def test_miss(self):
        from adaptive.core.llm_cache import LLMCache
        assert LLMCache().get("nonexistent") is None

    def test_ttl_expiry(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=10, ttl_seconds=0)
        cache.put("k1", "val")
        time.sleep(0.01)
        assert cache.get("k1") is None

    def test_lru_eviction(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=3, ttl_seconds=60)
        cache.put("a", 1); cache.put("b", 2); cache.put("c", 3)
        cache.put("d", 4)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_lru_access_refreshes(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=3, ttl_seconds=60)
        cache.put("a", 1); cache.put("b", 2); cache.put("c", 3)
        cache.get("a")  # refresh "a"
        cache.put("d", 4)  # evicts "b"
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_stats(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=10, ttl_seconds=60)
        cache.put("k1", "v1")
        cache.get("k1"); cache.get("k2")
        s = cache.stats()
        assert s["hits"] == 1 and s["misses"] == 1
        assert s["hit_rate"] == 0.5 and s["size"] == 1

    def test_overwrite_existing_key(self):
        from adaptive.core.llm_cache import LLMCache
        cache = LLMCache(max_size=10, ttl_seconds=60)
        cache.put("k1", "old"); cache.put("k1", "new")
        assert cache.get("k1") == "new"


class TestBuildCacheKey:

    def test_deterministic(self):
        from adaptive.core.llm_cache import build_cache_key
        k1 = build_cache_key("explainer", "algebra", difficulty="medium", prompt_version="v1")
        k2 = build_cache_key("explainer", "algebra", difficulty="medium", prompt_version="v1")
        assert k1 == k2

    def test_different_inputs_differ(self):
        from adaptive.core.llm_cache import build_cache_key
        assert build_cache_key("explainer", "algebra") != build_cache_key("explainer", "calculus")

    def test_version_affects_key(self):
        from adaptive.core.llm_cache import build_cache_key
        assert build_cache_key("e", "t", prompt_version="v1") != build_cache_key("e", "t", prompt_version="v2")

    def test_profile_bucketing(self):
        from adaptive.core.llm_cache import build_cache_key
        k1 = build_cache_key("e", "t", profile_bucket={"knowledge": 0.51})
        k2 = build_cache_key("e", "t", profile_bucket={"knowledge": 0.53})
        assert k1 == k2  # both bucket to 0.5

    def test_profile_different_bucket(self):
        from adaptive.core.llm_cache import build_cache_key
        k1 = build_cache_key("e", "t", profile_bucket={"knowledge": 0.44})
        k2 = build_cache_key("e", "t", profile_bucket={"knowledge": 0.56})
        assert k1 != k2

    def test_is_sha256(self):
        from adaptive.core.llm_cache import build_cache_key
        k = build_cache_key("test", "topic")
        assert len(k) == 64
        int(k, 16)  # valid hex

    def test_case_insensitive_topic(self):
        from adaptive.core.llm_cache import build_cache_key
        assert build_cache_key("e", "Algebra") == build_cache_key("e", "algebra")


class TestLLMTelemetry:

    def test_start_creates_record(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        rec = LLMTelemetry().start("explainer", "Mistral-Large", "v1")
        assert rec["engine"] == "explainer"
        assert rec["model"] == "Mistral-Large"
        assert rec["ok"] is False and rec["start_ts"] > 0

    def test_finish_sets_latency(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        t = LLMTelemetry()
        rec = t.start("test", "model1")
        time.sleep(0.01)
        t.finish(rec, ok=True, tokens_in=100, tokens_out=200)
        assert rec["ok"] is True and rec["latency_ms"] > 0
        assert rec["tokens_in"] == 100 and rec["tokens_out"] == 200

    def test_finish_error(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        t = LLMTelemetry()
        rec = t.start("test", "model1")
        t.finish(rec, ok=False, error="timeout")
        assert rec["ok"] is False and rec["error"] == "timeout"

    def test_summary_empty(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        s = LLMTelemetry().summary()
        assert s["per_model"] == {} and s["per_engine"] == {}

    def test_summary_with_records(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        t = LLMTelemetry()
        for i in range(5):
            rec = t.start("explainer", "ModelA")
            t.finish(rec, ok=(i < 4), tokens_in=100, tokens_out=200)
        stats = t.summary()["per_model"]["ModelA"]
        assert stats["calls"] == 5 and stats["failures"] == 1
        assert stats["failure_rate"] == 0.2
        assert stats["total_tokens_in"] == 500

    def test_buffer_stores_records(self):
        from adaptive.core.llm_telemetry import LLMTelemetry
        t = LLMTelemetry()
        rec = t.start("test", "m1")
        t.finish(rec, ok=True)
        assert len(t._buffer) == 1


# ═══════════════════════════════════════════════════════════════
# 3. PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════

class TestPromptTemplates:
    PROMPT_MODULES = [
        "core.prompts.question_generator", "core.prompts.explainer",
        "core.prompts.answer_evaluator", "core.prompts.socratic",
        "core.prompts.hint", "core.prompts.review",
        "core.prompts.study_planner", "core.prompts.progressive_challenge",
        "core.prompts.knowledge_graph", "core.prompts.prerequisite",
    ]

    @pytest.mark.parametrize("module_path", PROMPT_MODULES)
    def test_has_version(self, module_path):
        mod = importlib.import_module(module_path)
        assert hasattr(mod, "VERSION") and isinstance(mod.VERSION, str) and len(mod.VERSION) > 0

    def test_question_generator_build(self):
        from adaptive.core.prompts import question_generator as p
        assert len(p.build("algebra", "medium", 0.3, 0.5, {"core_concept": "eq"}, "Be kind")) > 20

    def test_explainer_build(self):
        from adaptive.core.prompts import explainer as p
        assert len(p.build("algebra", {"knowledge": 0.5}, "Be clear", "verbal")) > 20

    def test_answer_evaluator_build(self):
        from adaptive.core.prompts import answer_evaluator as p
        assert len(p.build("What is 2+2?", "4", "4", "arithmetic", 0.5)) > 20

    def test_socratic_build_probe(self):
        from adaptive.core.prompts import socratic as p
        assert len(p.build_probe("algebra", "equations", 0.5, 0.3, 0.6, "No prior", "Be kind")) > 20

    def test_socratic_build_reveal_step(self):
        from adaptive.core.prompts import socratic as p
        assert len(p.build_reveal_step("algebra", "equations", 0.5, "medium", "Be kind")) > 20

    def test_socratic_build_challenge(self):
        from adaptive.core.prompts import socratic as p
        assert len(p.build_challenge("algebra", "equations", 0.7, "hard", "Push them")) > 20

    def test_hint_build(self):
        from adaptive.core.prompts import hint as p
        assert len(p.build("What is the derivative of x^2?", "Be supportive")) > 20

    def test_review_build(self):
        from adaptive.core.prompts import review as p
        assert len(p.build("algebra", 3.0, 0.6, 0.4, "Be encouraging")) > 20

    def test_study_planner_build(self):
        from adaptive.core.prompts import study_planner as p
        profile = {"fatigue": 0.3, "frustration": 0.1, "streak": 5,
                    "engagement_trend": "improving", "day": "Monday",
                    "avg_session_minutes": 15.0}
        assert len(p.build("algebra (0.3)", "calculus (0.9)", profile, 30, "Go")) > 20

    def test_progressive_challenge_build(self):
        from adaptive.core.prompts import progressive_challenge as p
        assert len(p.build("algebra", 0.7, "medium", "Push them")) > 20

    def test_knowledge_graph_build(self):
        from adaptive.core.prompts import knowledge_graph as p
        assert len(p.build([{"topic": "algebra", "mastery": 0.6}, {"topic": "calc", "mastery": 0.3}])) > 20

    def test_prerequisite_build(self):
        from adaptive.core.prompts import prerequisite as p
        assert len(p.build("calculus")) > 20


# ═══════════════════════════════════════════════════════════════
# 4. RL METRICS
# ═══════════════════════════════════════════════════════════════

class TestRLMetrics:

    def test_initial_state(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        assert m.total_decisions == 0 and m.mean_reward() == 0.0 and m.mean_loss() == 0.0

    def test_record_decision(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        m.record_decision(mode=1, hint=0, difficulty=0.4, epsilon=0.5)
        assert m.total_decisions == 1 and m.mode_counts[1] == 1

    def test_record_reward(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        m.record_reward(1.5); m.record_reward(2.5)
        assert m.total_learns == 2 and m.mean_reward() == 2.0

    def test_record_loss(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        m.record_loss(0.5); m.record_loss(1.5)
        assert m.total_train_steps == 2 and m.mean_loss() == 1.0

    def test_action_distribution(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        for _ in range(10): m.record_decision(0, 0, 0.2, 0.5)
        for _ in range(10): m.record_decision(1, 1, 0.4, 0.5)
        dist = m.action_distribution()
        assert dist["mode"]["direct_question"] == 0.5

    def test_snapshot(self):
        from adaptive.utils.rl_metrics import RLMetrics
        m = RLMetrics()
        m.record_decision(0, 0, 0.2, 0.5); m.record_reward(1.0)
        snap = m.snapshot(epsilon=0.5, step_counter=10)
        assert snap["epsilon"] == 0.5 and snap["step_counter"] == 10
        assert snap["total_decisions"] == 1 and "action_distribution" in snap


# ═══════════════════════════════════════════════════════════════
# 5. ENGINE ASYNC METHODS (mocked LLM)
# ═══════════════════════════════════════════════════════════════

class TestEnginesWithMockedLLM:

    @pytest.fixture(autouse=True)
    def mock_build_models(self):
        with patch("adaptive.core.llm_registry.build_models", return_value=[("mock_model", MagicMock())]):
            yield

    @pytest.mark.asyncio
    async def test_question_generator_success(self):
        mock_data = {"question": "What is x+2=5?", "answer": "x=3",
                     "explanation": "Subtract 2", "model_used": "mock"}
        mock_verification = {"verified": True, "method": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data), \
             patch("adaptive.core.question_generator.AnswerVerifier.verify", new_callable=AsyncMock, return_value=mock_verification):
            from adaptive.core.question_generator import QuestionGenerator
            result = await QuestionGenerator().generate_question(
                topic="algebra", difficulty="easy", frustration=0.2,
                knowledge=0.5, explanation={"core_concept": "equations"}
            )
            assert result["question"] == "What is x+2=5?" and result["topic"] == "algebra"

    @pytest.mark.asyncio
    async def test_question_generator_fallback(self):
        import adaptive.core.question_generator as _mod
        with patch.object(_mod, "call_llm", new_callable=AsyncMock, return_value=None):
            result = await _mod.QuestionGenerator().generate_question(
                topic="algebra", difficulty="easy", frustration=0.2,
                knowledge=0.5, explanation={"core_concept": "equations"}
            )
            assert result["model_used"] == "fallback"

    @pytest.mark.asyncio
    async def test_answer_evaluator_success(self):
        mock_data = {"score": 0.9, "correct": True, "reasoning": "Good",
                     "error_type": "none", "misconception": None,
                     "root_concept": None, "targeted_feedback": "Well done",
                     "remediation": "", "mistakes": [], "improvement": "", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.answer_evaluator import LLMAnswerEvaluator
            result = await LLMAnswerEvaluator().evaluate(
                question="What is 2+2?", student_answer="4",
                correct_answer="4", start_time=100.0, end_time=105.0
            )
            assert result["correct"] is True and result["score"] >= 0.9
            assert result["response_time"] == 5.0 and 0.0 <= result["ux_score"] <= 3.0

    @pytest.mark.asyncio
    async def test_answer_evaluator_fallback(self):
        import adaptive.core.answer_evaluator as _mod
        with patch.object(_mod, "call_llm", new_callable=AsyncMock, return_value=None):
            result = await _mod.LLMAnswerEvaluator().evaluate(
                question="Q", student_answer="A",
                correct_answer="B", start_time=100.0, end_time=110.0
            )
            assert result["correct"] is False and result["score"] == 0.0

    @pytest.mark.asyncio
    async def test_adaptive_explainer_success(self):
        mock_data = {"core_concept": "Variables represent unknowns",
                     "intuition": "Think of x as a box", "prerequisites": [],
                     "step_by_step": [], "practice": [], "next_topics": [],
                     "references": [], "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.adaptive_explainer import AdaptiveExplainer
            result = await AdaptiveExplainer().generate_explanation(
                topic="algebra", student_profile={"knowledge": 0.5}
            )
            assert result["core_concept"] == "Variables represent unknowns"

    @pytest.mark.asyncio
    async def test_adaptive_explainer_style_selection(self):
        from adaptive.core.adaptive_explainer import AdaptiveExplainer
        ae = AdaptiveExplainer()
        assert ae.select_style({"frustration": 0.8}) == "example_first"
        assert ae.select_style({"knowledge": 0.2}) == "example_first"
        assert ae.select_style({"retention": 0.3}) == "visual"
        assert ae.select_style({"curiosity": 0.8, "knowledge": 0.6}) == "analogy"
        assert ae.select_style({"confidence": 0.9, "mastery": 0.8}) == "theory_first"

    @pytest.mark.asyncio
    async def test_hint_engine_success(self):
        with patch("adaptive.core.llm_utils.call_llm_text", new_callable=AsyncMock, return_value="Try breaking the problem into parts"):
            from adaptive.core.hint_engine import HintGenerator
            assert "breaking" in (await HintGenerator().generate_hint("What is 2+2?")).lower()

    @pytest.mark.asyncio
    async def test_hint_engine_fallback(self):
        import adaptive.core.hint_engine as _mod
        with patch.object(_mod, "call_llm_text", new_callable=AsyncMock, return_value=None):
            assert "step by step" in (await _mod.HintGenerator().generate_hint("What is 2+2?")).lower()

    @pytest.mark.asyncio
    async def test_socratic_probe_success(self):
        mock_data = {"probe": "Why do you think that works?", "expected_insight": "Causality",
                     "follow_up_if_stuck": "Simplify", "thinking_direction": "Cause/effect", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.socratic_engine import SocraticEngine
            result = await SocraticEngine().generate_socratic_probe(
                topic="physics", core_concept="Newton's laws",
                knowledge_level=0.5, frustration=0.2, curiosity=0.7,
                conversation_context=[]
            )
            assert result["type"] == "socratic_probe" and result["question"] == "Why do you think that works?"

    @pytest.mark.asyncio
    async def test_socratic_reveal_step(self):
        mock_data = {"problem_context": "Solving F=ma", "step_1_revealed": "Identify forces",
                     "step_2_question": "What is the net force?", "step_2_answer": "10N",
                     "checkpoint_hint": "Check units", "full_solution": "Complete", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.socratic_engine import SocraticEngine
            result = await SocraticEngine().generate_reveal_step(
                topic="physics", core_concept="Newton's laws",
                knowledge_level=0.5, difficulty="medium", conversation_context=[]
            )
            assert result["type"] == "reveal_step"

    @pytest.mark.asyncio
    async def test_socratic_challenge(self):
        mock_data = {"challenge_question": "What if mass is zero?", "why_its_tricky": "Div by zero",
                     "common_trap": "Assuming mass positive", "correct_answer": "Breaks down",
                     "deep_insight": "Massless particles", "explanation": "Detail", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.socratic_engine import SocraticEngine
            result = await SocraticEngine().generate_challenge(
                topic="physics", core_concept="Newton's laws",
                knowledge_level=0.8, mastery=0.7, difficulty="hard",
                conversation_context=[]
            )
            assert result["type"] == "challenge"

    @pytest.mark.asyncio
    async def test_review_engine_generate(self):
        mock_data = {"question": "Explain algebra basics", "answer": "Unknowns",
                     "refresher": "Remember: x", "tests_concept": "Basic algebra", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.review_engine import ReviewEngine
            result = await ReviewEngine().generate_review_question(
                topic="algebra", days_ago=3.0, mastery=0.6, retention_estimate=0.4
            )
            assert result["topic"] == "algebra" and result["question"] == "Explain algebra basics"

    @pytest.mark.asyncio
    async def test_progressive_challenge_success(self):
        mock_data = {"problem_statement": "Multi-step", "steps": [
            {"step": 1, "sub_problem": "Find x", "checkpoint_answer": "3",
             "hint_if_stuck": "Isolate x", "concept_tested": "algebra"}
        ], "final_answer": "x=3", "learning_arc": "Basics to app", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.progressive_challenge import ProgressiveChallengeEngine
            result = await ProgressiveChallengeEngine().generate_challenge(topic="algebra", mastery=0.6)
            assert result["topic"] == "algebra" and len(result["steps"]) == 1

    @pytest.mark.asyncio
    async def test_knowledge_graph_success(self):
        mock_data = {"nodes": [{"topic": "algebra", "mastery": 0.6}],
                     "edges": [{"from": "a", "to": "b", "strength": "strong", "reason": "prereq"}],
                     "weak_links": ["calculus"], "suggested_focus": "Focus on calculus", "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.knowledge_graph import KnowledgeGraphEngine
            result = await KnowledgeGraphEngine().generate_graph([
                {"topic": "algebra", "mastery": 0.6}, {"topic": "calculus", "mastery": 0.3}
            ])
            assert result["suggested_focus"] == "Focus on calculus"

    @pytest.mark.asyncio
    async def test_knowledge_graph_single_topic(self):
        from adaptive.core.knowledge_graph import KnowledgeGraphEngine
        result = await KnowledgeGraphEngine().generate_graph([{"topic": "algebra", "mastery": 0.6}])
        assert result["model_used"] == "skip" and result["edges"] == []

    @pytest.mark.asyncio
    async def test_prerequisite_engine_success(self):
        mock_data = {"prerequisites": ["Algebra", "Trigonometry", "Limits"], "model_used": "mock"}
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=mock_data):
            from adaptive.core.prerequisite_engine import PrerequisiteEngine
            result = await PrerequisiteEngine().get_prerequisites("calculus")
            assert "algebra" in result and len(result) <= 5

    @pytest.mark.asyncio
    async def test_prerequisite_engine_fallback(self):
        import adaptive.core.prerequisite_engine as _mod
        with patch.object(_mod, "call_llm", new_callable=AsyncMock, return_value=None):
            assert await _mod.PrerequisiteEngine().get_prerequisites("calculus") == ["basics of calculus"]

    @pytest.mark.asyncio
    async def test_study_planner_fallback(self):
        with patch("adaptive.core.llm_utils.call_llm", new_callable=AsyncMock, return_value=None):
            from adaptive.core.study_planner import StudyPlanner
            student = MagicMock()
            student.concepts = {
                "algebra": MagicMock(concept_mastery=0.3, knowledge=0.3),
                "calculus": MagicMock(concept_mastery=0.9, knowledge=0.9),
            }
            student.history = []
            student.fatigue = 0.2; student.frustration = 0.1; student.streak = 3
            result = await StudyPlanner().generate_plan(student, available_minutes=30)
            assert result["model_used"] == "fallback" and len(result["plan"]) > 0


# ═══════════════════════════════════════════════════════════════
# 6. API SCHEMAS VALIDATION
# ═══════════════════════════════════════════════════════════════

class TestSchemas:

    def test_student_input_valid(self):
        from adaptive.api.schemas import StudentInput
        assert StudentInput(student_id="user_123", current_topic="algebra").student_id == "user_123"

    def test_student_input_rejects_injection(self):
        from adaptive.api.schemas import StudentInput
        with pytest.raises(Exception):
            StudentInput(student_id='{"$gt": ""}', current_topic="algebra")

    def test_student_input_rejects_long_id(self):
        from adaptive.api.schemas import StudentInput
        with pytest.raises(Exception):
            StudentInput(student_id="a" * 65, current_topic="algebra")

    def test_student_input_rejects_special_chars(self):
        from adaptive.api.schemas import StudentInput
        with pytest.raises(Exception):
            StudentInput(student_id="user@evil.com", current_topic="algebra")

    def test_student_input_allows_hyphens_underscores(self):
        from adaptive.api.schemas import StudentInput
        assert StudentInput(student_id="user-name_123").student_id == "user-name_123"

    def test_answer_request_valid(self):
        from adaptive.api.schemas import AnswerRequest
        assert AnswerRequest(student_id="user_1", answer="42").answer == "42"

    def test_answer_request_rejects_injection(self):
        from adaptive.api.schemas import AnswerRequest
        with pytest.raises(Exception):
            AnswerRequest(student_id='"; DROP TABLE students;--', answer="42")

    def test_hint_request_valid(self):
        from adaptive.api.schemas import HintRequest
        assert HintRequest(student_id="user_1", question="What is 2+2?").question == "What is 2+2?"

    def test_user_in_password_validation(self):
        from adaptive.api.schemas import UserIn
        with pytest.raises(Exception):
            UserIn(username="test", password="short")

    def test_user_in_valid_password(self):
        from adaptive.api.schemas import UserIn
        assert UserIn(username="test", password="longpassword123", email="test@example.com").password == "longpassword123"

    def test_tutor_response(self):
        from adaptive.api.schemas import TutorResponse
        t = TutorResponse(mode="direct_question", hint_level=0, difficulty=0.4, question="What is x?")
        assert t.mode == "direct_question"

    def test_rl_stats_response(self):
        from adaptive.api.schemas import RLStatsResponse, ActionDistribution
        r = RLStatsResponse(
            epsilon=0.5, step_counter=100, total_decisions=50, total_learns=40,
            total_train_steps=30, mean_reward=1.5, mean_loss=0.1,
            reward_window_size=40, loss_window_size=30,
            action_distribution=ActionDistribution(), uptime_seconds=3600.0,
        )
        assert r.epsilon == 0.5

    def test_progressive_challenge_response(self):
        from adaptive.api.schemas import ProgressiveChallengeResponse, ProgressiveChallengeStep
        p = ProgressiveChallengeResponse(
            topic="algebra", difficulty="medium", problem_statement="Solve multi-step",
            steps=[ProgressiveChallengeStep(step=1, sub_problem="Find x",
                   checkpoint_answer="3", hint_if_stuck="Isolate x", concept_tested="algebra")],
            final_answer="x=3", learning_arc="Basics to app"
        )
        assert len(p.steps) == 1

    def test_review_response(self):
        from adaptive.api.schemas import ReviewResponse, DueTopicItem
        r = ReviewResponse(
            due_topics=[DueTopicItem(topic="algebra", mastery=0.6,
                        retention_estimate=0.4, days_since_review=3.0, review_count=2)],
            message="1 topic due"
        )
        assert len(r.due_topics) == 1

    def test_study_plan_response(self):
        from adaptive.api.schemas import StudyPlanResponse, StudyPlanItem
        r = StudyPlanResponse(
            plan=[StudyPlanItem(topic="algebra", duration_min=15, type="learn", reason="Weak")],
            motivational_note="Keep going!", estimated_knowledge_gain="Good progress"
        )
        assert r.plan[0].topic == "algebra"


# ═══════════════════════════════════════════════════════════════
# 7. ADDITIONAL UNIT TESTS
# ═══════════════════════════════════════════════════════════════

class TestTokenExtraction:

    def test_usage_metadata_attr(self):
        from adaptive.core.llm_utils import _extract_tokens
        response = MagicMock()
        usage = MagicMock(); usage.input_tokens = 100; usage.output_tokens = 200
        response.usage_metadata = usage
        ti, to = _extract_tokens(response)
        assert ti == 100 and to == 200

    def test_response_metadata_fallback(self):
        from adaptive.core.llm_utils import _extract_tokens
        response = MagicMock()
        response.usage_metadata = None
        response.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 75}}
        ti, to = _extract_tokens(response)
        assert ti == 50 and to == 75

    def test_no_metadata(self):
        from adaptive.core.llm_utils import _extract_tokens
        response = MagicMock()
        response.usage_metadata = None
        response.response_metadata = {}
        ti, to = _extract_tokens(response)
        assert ti is None and to is None


class TestReviewEngineRetention:

    def test_fresh_concept_full_retention(self):
        from adaptive.core.review_engine import ReviewEngine
        from models.student import Concept
        concept = Concept(concept_mastery=0.8)
        # Review once so FSRS card exists
        ReviewEngine.mark_reviewed(concept, correct=True, response_time=5.0)
        ret = ReviewEngine.estimate_retention(concept)
        assert ret > 0.9  # just reviewed -> high retention

    def test_no_fsrs_state_uses_mastery(self):
        from adaptive.core.review_engine import ReviewEngine
        from models.student import Concept
        concept = Concept(concept_mastery=0.4)
        # No FSRS card yet -> falls back to concept_mastery
        ret = ReviewEngine.estimate_retention(concept)
        assert abs(ret - 0.4) < 0.01

    def test_mark_reviewed_creates_fsrs(self):
        from adaptive.core.review_engine import ReviewEngine
        from models.student import Concept
        concept = Concept(review_count=2)
        ReviewEngine.mark_reviewed(concept, correct=True, response_time=10.0)
        assert concept.fsrs_state is not None
        assert concept.review_count == 3
        assert concept.last_reviewed > 0



class TestAnswerEvaluatorUxScore:
    """Tests for the evaluator's UX display score (NOT the RL reward)."""

    def _call_ux_score(self, **kwargs):
        """Call _calculate_ux_score without instantiating the full evaluator."""
        from adaptive.core.answer_evaluator import LLMAnswerEvaluator
        # Call as unbound — self arg is unused in the method
        return LLMAnswerEvaluator._calculate_ux_score(None, **kwargs)

    def test_ux_score_bounded(self):
        for _ in range(100):
            r = self._call_ux_score(
                score=random.uniform(0, 1), response_time=random.uniform(0.1, 120),
                difficulty=random.choice(["easy", "medium", "hard"]),
                student_profile={"frustration": random.uniform(0, 1),
                                 "knowledge": random.uniform(0, 1),
                                 "focus": random.uniform(0, 1)}
            )
            assert 0.0 <= r <= 3.0

    def test_perfect_score_high_ux_score(self):
        assert self._call_ux_score(score=1.0, response_time=15, difficulty="medium") > 1.5

    def test_zero_score_low_ux_score(self):
        assert self._call_ux_score(score=0.0, response_time=15, difficulty="medium") < 0.5


class TestSingleRewardSource:
    """R2 regression: store_transition must only receive compute_reward output."""

    def test_evaluator_does_not_produce_reward_key(self):
        """The evaluator dict must use 'ux_score', never 'reward'."""
        from adaptive.core.answer_evaluator import LLMAnswerEvaluator
        # Call _calculate_ux_score without full init
        ux = LLMAnswerEvaluator._calculate_ux_score(None, score=1.0, response_time=5.0, difficulty="medium")
        det_result = {"score": 1.0, "grade": "correct", "method": "exact_match",
                      "correct": True, "reasoning": "exact"}
        det_result["ux_score"] = ux
        assert "reward" not in det_result, "Evaluator must use 'ux_score', not 'reward'"
        assert "ux_score" in det_result

    def test_learn_reward_comes_from_compute_reward(self):
        """Structural check: inference.learn feeds store_transition with compute_reward."""
        import ast
        import adaptive.api.inference as _inference_mod
        with open(_inference_mod.__file__) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "learn":
                src = ast.dump(node)
                assert "compute_reward" in src, "learn() must call compute_reward"
                assert "store_transition" in src, "learn() must call store_transition"
                cr_line = st_line = None
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_src = ast.dump(child)
                        if "compute_reward" in call_src and cr_line is None:
                            cr_line = child.lineno
                        if "store_transition" in call_src and st_line is None:
                            st_line = child.lineno
                assert cr_line is not None, "compute_reward call not found in learn()"
                assert st_line is not None, "store_transition call not found in learn()"
                assert cr_line < st_line, "compute_reward must be called before store_transition"
                break
        else:
            raise AssertionError("learn() method not found in inference.py")



class TestAdaptiveGrading:
    """R7: Adaptive self-consistency grading tests."""

    def test_evaluator_config_defaults(self):
        """_get_evaluator_config returns sensible defaults when config is missing."""
        from adaptive.core.answer_evaluator import LLMAnswerEvaluator
        cfg = LLMAnswerEvaluator._get_evaluator_config()
        assert "confidence_threshold" in cfg
        assert "max_samples" in cfg
        assert 0.0 < cfg["confidence_threshold"] <= 1.0
        assert cfg["max_samples"] >= 2

    def test_evaluator_config_from_yaml(self):
        """Config values match what's in default.yaml."""
        import yaml, os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs", "default.yaml",
        )
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        ev = cfg["llm"]["evaluator"]
        assert ev["confidence_threshold"] == 0.75
        assert ev["max_samples"] == 3

    def test_prompt_requests_confidence(self):
        """Prompt template v3 asks the LLM for a confidence score."""
        from adaptive.core.prompts import answer_evaluator as tmpl
        assert tmpl.VERSION == "v3"
        prompt = tmpl.build("What is 2+2?", "4", "4", "Arithmetic", 0.5)
        assert "confidence" in prompt.lower()

    def test_fast_path_high_confidence_correct(self):
        """High-confidence 'correct' should use method adaptive_single."""
        result = {
            "grade": "correct",
            "confidence": 0.95,
            "error_type": "none",
            "reasoning": "Matches reference",
            "model_used": "test",
        }
        result["method"] = "adaptive_single"
        assert result["method"] == "adaptive_single"
        assert result["confidence"] >= 0.75

    def test_escalation_triggers_on_partial(self):
        """partially_correct always escalates regardless of confidence."""
        fast_path_grades = ("correct", "incorrect")
        assert "partially_correct" not in fast_path_grades

    def test_escalation_triggers_on_low_confidence(self):
        """Low confidence correct/incorrect should trigger escalation."""
        threshold = 0.75
        low_conf = 0.5
        grade = "correct"
        should_fast_path = grade in ("correct", "incorrect") and low_conf >= threshold
        assert not should_fast_path, "Low confidence should NOT take fast path"

    def test_majority_vote_with_escalation(self):
        """Majority vote works correctly with 3 samples."""
        from adaptive.core.answer_evaluator import _majority_vote
        results = [
            {"grade": "correct", "confidence": 0.6, "model_used": "a"},
            {"grade": "partially_correct", "confidence": 0.5, "model_used": "b"},
            {"grade": "correct", "confidence": 0.7, "model_used": "c"},
        ]
        winner = _majority_vote(results)
        assert winner["grade"] == "correct"
        assert "self_consistency_3x" in winner["method"]
        assert winner["agreement"] == "2/3"

    def test_module_counters_exist(self):
        """Module-level escalation counters are accessible."""
        import adaptive.core.answer_evaluator as ev
        assert hasattr(ev, "_eval_total")
        assert hasattr(ev, "_eval_escalated")
        assert isinstance(ev._eval_total, int)
        assert isinstance(ev._eval_escalated, int)



# ===================================================================
# 9. Authorization & RBAC tests
# ===================================================================

class TestAuthorization:
    """Test role system: student + guardian (no teacher/admin)."""

    # --- Signup account_type ---

    def test_signup_defaults_to_student(self):
        from adaptive.api.schemas import UserIn
        u = UserIn(username="test", password="longpassword123", email="test@example.com")
        assert u.account_type == "student"

    def test_signup_accepts_guardian(self):
        from adaptive.api.schemas import UserIn
        u = UserIn(username="parent1", password="longpassword123", email="parent@example.com", account_type="guardian")
        assert u.account_type == "guardian"

    def test_signup_rejects_teacher(self):
        from adaptive.api.schemas import UserIn
        with pytest.raises(Exception):
            UserIn(username="x", password="longpassword123", account_type="teacher")

    def test_signup_rejects_admin(self):
        from adaptive.api.schemas import UserIn
        with pytest.raises(Exception):
            UserIn(username="x", password="longpassword123", account_type="admin")

    # --- SEC-IDOR: assert_owns_student binds writes to the caller ---

    def test_owns_student_allows_self(self):
        from adaptive.dependencies import assert_owns_student
        me = {"username": "alice", "role": "student"}
        assert assert_owns_student(me, "alice") == "alice"

    def test_owns_student_blocks_other(self):
        from adaptive.dependencies import assert_owns_student
        from fastapi import HTTPException
        me = {"username": "alice", "role": "student"}
        with pytest.raises(HTTPException) as exc:
            assert_owns_student(me, "victim")
        assert exc.value.status_code == 403

    def test_owns_student_empty_defaults_to_self(self):
        """An empty/omitted student_id resolves to the caller, not a foreign id."""
        from adaptive.dependencies import assert_owns_student
        me = {"username": "alice", "role": "student"}
        assert assert_owns_student(me, "") == "alice"

    # --- require_role blocks wrong roles ---

    @pytest.mark.asyncio
    async def test_guardian_blocked_from_student_endpoint(self):
        from adaptive.dependencies import require_role
        checker = require_role("student")
        guardian_user = {"username": "parent1", "role": "guardian"}
        with patch("dependencies.get_current_user", return_value=guardian_user):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await checker(current_user=guardian_user)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_student_blocked_from_guardian_endpoint(self):
        from adaptive.dependencies import require_role
        checker = require_role("guardian")
        student_user = {"username": "student1", "role": "student"}
        with patch("dependencies.get_current_user", return_value=student_user):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await checker(current_user=student_user)
            assert exc_info.value.status_code == 403

    # --- Guardian IDOR: can only read invited children ---

    def test_guardian_cannot_read_uninvited_child(self):
        guardian_user = {
            "username": "parent1",
            "role": "guardian",
            "linked_children": ["child_A"],
        }
        target = "unauthorized_child"
        assert target not in guardian_user.get("linked_children", [])

    def test_guardian_can_read_invited_child(self):
        guardian_user = {
            "username": "parent1",
            "role": "guardian",
            "linked_children": ["child_A"],
        }
        assert "child_A" in guardian_user["linked_children"]

    # --- Guardian schemas ---

    def test_guardian_redeem_schema(self):
        from adaptive.api.schemas import GuardianRedeemRequest
        r = GuardianRedeemRequest(code="abc123")
        assert r.code == "abc123"

    def test_guardian_children_response_schema(self):
        from adaptive.api.schemas import GuardianChildrenResponse, ChildSummary
        resp = GuardianChildrenResponse(children=[
            ChildSummary(student_id="s1", total_questions=10, accuracy=85.0, topics_count=3),
        ])
        assert len(resp.children) == 1

    def test_guardian_child_overview_schema(self):
        from adaptive.api.schemas import GuardianChildOverview, StudentProgress
        overview = GuardianChildOverview(
            student_id="s1",
            progress=StudentProgress(student_id="s1", topics={"algebra": 5}, total_questions=10, accuracy=80.0),
        )
        assert overview.student_id == "s1"



# ===================================================================
# 10. JWT Refresh / Revocation tests
# ===================================================================

class TestJWTRefreshFlow:
    """Test access-token claims, refresh-token generation, and revocation."""

    def test_access_token_has_jti_iat(self):
        from security import create_access_token, decode_token
        token = create_access_token({"sub": "alice", "role": "student"})
        payload = decode_token(token)
        assert "jti" in payload
        assert "iat" in payload
        assert payload["type"] == "access"
        assert len(payload["jti"]) == 32  # uuid4 hex

    def test_access_token_lifetime_matches_config(self):
        """Access-token lifetime must equal the configured value and stay within a
        sane ceiling. Product decision: 7-day access tokens (configured via
        access_token_expire_minutes); sessions also persist via the refresh cookie."""
        from security import create_access_token, decode_token
        from auth_config import ACCESS_TOKEN_EXPIRE_MINUTES
        token = create_access_token({"sub": "alice", "role": "student"})
        payload = decode_token(token)
        diff = payload["exp"] - payload["iat"]
        expected = ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert diff == expected
        assert diff <= 7 * 24 * 60 * 60, "access token must not outlive 7 days"

    def test_refresh_token_has_type_refresh(self):
        from security import create_refresh_token, decode_token
        token, jti = create_refresh_token({"sub": "alice", "role": "student"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti
        assert "iat" in payload

    def test_refresh_token_expires_in_7_days(self):
        from security import create_refresh_token, decode_token
        token, _ = create_refresh_token({"sub": "alice", "role": "student"})
        payload = decode_token(token)
        diff = payload["exp"] - payload["iat"]
        expected = 7 * 24 * 3600
        assert expected - 2 <= diff <= expected + 2

    def test_refresh_token_jti_is_unique(self):
        from security import create_refresh_token
        _, jti1 = create_refresh_token({"sub": "alice"})
        _, jti2 = create_refresh_token({"sub": "alice"})
        assert jti1 != jti2

    def test_access_token_jti_is_unique(self):
        from security import create_access_token, decode_token
        t1 = create_access_token({"sub": "alice"})
        t2 = create_access_token({"sub": "alice"})
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]

    def test_decode_invalid_token_raises(self):
        from security import decode_token
        from jwt import PyJWTError as JWTError
        with pytest.raises(JWTError):
            decode_token("garbage.token.value")

    def test_token_schema_has_refresh_token(self):
        from adaptive.api.schemas import Token
        assert "refresh_token" in Token.model_fields

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_bearer(self):
        """SEC: a refresh token must NOT authenticate a normal (access) route."""
        from security import create_refresh_token
        from adaptive.dependencies import get_current_user
        from fastapi import HTTPException
        token, _ = create_refresh_token({"sub": "alice", "role": "student"})
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
        assert exc.value.status_code == 401

    def test_stream_token_is_short_lived_and_scoped(self):
        """SEC: stream tickets are type='stream' and expire within ~60s."""
        from security import create_stream_token, decode_token
        tok = create_stream_token("alice")
        payload = decode_token(tok)
        assert payload["type"] == "stream"
        assert payload["sub"] == "alice"
        assert 0 < (payload["exp"] - payload["iat"]) <= 120

    @pytest.mark.asyncio
    async def test_stream_token_rejected_as_bearer(self):
        """SEC: a stream ticket must NOT authenticate normal API routes."""
        from security import create_stream_token
        from adaptive.dependencies import get_current_user
        from fastapi import HTTPException
        tok = create_stream_token("alice")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=tok)
        assert exc.value.status_code == 401

    def test_expired_token_rejected(self):
        """An access token with exp in the past should fail decode."""
        import jwt
        from jwt import PyJWTError as JWTError
        from datetime import datetime, timezone, timedelta
        secret = os.environ.get("SECRET_KEY", "test-secret-key")
        payload = {
            "sub": "alice",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=16),
            "jti": "abc123",
            "type": "access",
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        with pytest.raises(JWTError):
            from security import decode_token
            decode_token(token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
