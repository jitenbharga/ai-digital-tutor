from fastapi import HTTPException
import os
import time
import uuid
import logging

logger = logging.getLogger("rl.inference")

from adaptive.core.adaptive_explainer import AdaptiveExplainer
from adaptive.core.socratic_engine import SocraticEngine
from adaptive.models.dqn import DQNAgent
from adaptive.api.session_manager import SessionManager

from adaptive.core.question_generator import QuestionGenerator
from adaptive.core.answer_evaluator import LLMAnswerEvaluator
from adaptive.core.prerequisite_engine import PrerequisiteEngine
from adaptive.core.review_engine import ReviewEngine
from adaptive.core.reward import update_student_traits, compute_reward
from adaptive.core.knowledge_tracing.manager import KnowledgeTracingManager
from adaptive.core.leakage_guard import classify_message, get_redirect_response, get_anti_disclosure_instruction
from adaptive.core.mentor import load_memory, save_memory_item, build_mentor_directive, extract_memory_facts
from adaptive.utils.tone import get_tone_directive
from adaptive.utils.language import get_language_directive
from adaptive.config.features import RL_ENABLED
from adaptive.core.ab_experiment import (
    get_experiment_manager, RL_VS_RULE_EXPERIMENT,
    ARM_CONTROL, ARM_TREATMENT,
)
from adaptive.database import (
    questions_collection, rl_transitions_collection, interactions_collection,
    mentor_memory_collection, users_collection,
)


# ----------------------------------
# TEACHING MODES (RL controls this)
# ----------------------------------
MODE_DIRECT_QUESTION = 0    # classic: explain -> question
MODE_SOCRATIC_PROBE  = 1    # ask leading question, no answer
MODE_REVEAL_STEP     = 2    # show one step, ask student to continue
MODE_CHALLENGE       = 3    # push harder, edge cases

MODE_NAMES = {
    0: "direct_question",
    1: "socratic_probe",
    2: "reveal_step",
    3: "challenge"
}


class ProductionTutor:

    def __init__(self):

        # RL actions: (mode, hint_level, difficulty)
        # 4 modes x 3 hints x 3 difficulties = 36 actions
        self.action_space = []
        for mode in range(4):              # 0,1,2,3
            for hint in range(3):          # 0,1,2
                for diff in [0.2, 0.4, 0.6]:
                    self.action_space.append((mode, hint, diff))

        # min_buffer: configurable via env (default 500, lowered from 2000)
        min_buffer = int(os.getenv("RL_MIN_BUFFER", "500"))

        self.agent = DQNAgent(
            action_space=self.action_space,
            db_collection=rl_transitions_collection,
            min_buffer=min_buffer,
        )

        self.sessions = SessionManager()

        # AI modules (LLM driven -- all async now)
        self.generator = QuestionGenerator()
        self.evaluator = LLMAnswerEvaluator()
        self.prereq = PrerequisiteEngine()
        self.explainer = AdaptiveExplainer()
        self.socratic = SocraticEngine()

        # Knowledge Tracing (calibrated mastery)
        self.kt = KnowledgeTracingManager()

        # Load full training state (model + target + optimizer + epsilon + step_counter)
        self.agent.load_checkpoint("checkpoints/dqn_model.pt")

        # R9: Gate DQN serving -- only use learned policy if it beats baselines
        self.dqn_validated = self._check_dqn_gate()

        # Production serving: greedy or near-greedy (0.0 = pure greedy)
        self.serve_epsilon = float(os.getenv("RL_SERVE_EPSILON", "0.0"))

        # NOTE: Replay buffer is loaded from DB via load_replay_buffer()
        self._buffer_loaded = False

        # P2.1: Mastery gating config
        try:
            import yaml
            _cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "default.yaml")
            with open(_cfg_path) as _f:
                _cfg = yaml.safe_load(_f) or {}
            _mastery_cfg = _cfg.get("mastery", {})
        except Exception:
            _mastery_cfg = {}
        self._mastery_threshold = _mastery_cfg.get("prerequisite_threshold", 0.7)
        self._enforce_mastery_gating = _mastery_cfg.get("enforce_gating", True)

    def _check_dqn_gate(self) -> bool:
        """
        R9: Check if DQN policy has been validated against baselines.
        Looks for eval_results.json produced by training/eval_policies.py.
        If missing or DQN doesn't beat baselines, fall back to MasteryThreshold.
        """
        eval_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "eval_results.json",
        )
        try:
            from training.eval_policies import check_dqn_beats_baselines
            validated = check_dqn_beats_baselines(eval_path)
            if validated:
                logger.info("DQN policy VALIDATED -- beats all pedagogical baselines")
            else:
                logger.warning(
                    "DQN policy NOT validated (eval_results.json missing or DQN underperforms). "
                    "Falling back to MasteryThreshold policy for action selection."
                )
            return validated
        except Exception as e:
            logger.warning("Could not check DQN gate: %s -- assuming not validated", e)
            return False

    async def load_replay_buffer(self):
        """Load persisted transitions from MongoDB into the in-memory replay buffer."""
        if not self._buffer_loaded:
            count = await self.agent.replay_buffer.load_from_db()
            self._buffer_loaded = True
            print("Replay buffer ready: %d transitions loaded." % count)

    # ------------------------------------------------
    # START SESSION
    # ------------------------------------------------

    async def start_session(self, student_state):
        student = await self.sessions.create_session(student_state)
        if not hasattr(student, "current_topic"):
            student.current_topic = None
        return student.student_id

    # ------------------------------------------------
    # HELPER: difficulty float -> label
    # ------------------------------------------------

    @staticmethod
    def _difficulty_label(difficulty):
        if difficulty < 0.3:
            return "easy"
        elif difficulty < 0.5:
            return "medium"
        return "hard"

    # ------------------------------------------------
    # HELPER: build student profile dict
    # ------------------------------------------------

    @staticmethod
    def _build_profile(student, concept):
        return {
            "knowledge": concept.knowledge,
            "mastery": concept.concept_mastery,
            "learning_velocity": student.learning_velocity,
            "confidence": student.confidence,
            "engagement": student.engagement,
            "focus": student.focus,
            "curiosity": student.curiosity,
            "frustration": student.frustration,
            "fatigue": student.fatigue,
            "retention": student.retention,
            "cognitive_load": student.cognitive_load,
            "speed": student.speed,
            "hint_dependency": student.hint_dependency,
            "streak": student.streak
        }

    # ------------------------------------------------
    # HELPER: build mentor directive for a student
    # ------------------------------------------------

    async def _get_mentor_directive(self, student_id: str, student, is_socratic: bool = False) -> str:
        """Load mentor memory + user display name, build the persona directive."""
        user = await users_collection.find_one({"username": student_id})
        display_name = (user or {}).get("display_name") or student_id
        tone = get_tone_directive(student)
        memory_items = await load_memory(mentor_memory_collection, student_id)
        return build_mentor_directive(
            display_name=display_name,
            tone_directive=tone,
            memory_items=memory_items,
            is_socratic=is_socratic,
        )

    # ------------------------------------------------
    # DECIDE NEXT ACTION (MODE-ROUTED)
    # ------------------------------------------------

    async def decide(self, student_input):

        # LOAD STUDENT
        student = await self.sessions.get_student(student_input.student_id)

        if student is None:
            student = await self.sessions.create_session({
                "student_id": student_input.student_id
            })

        # UPDATE TOPIC (reset conversation on topic switch)
        if student_input.current_topic:
            if student.current_topic != student_input.current_topic:
                student.conversation = []
                student.conversation_turns = 0
            student.current_topic = student_input.current_topic

        concept = student.get_current_concept()

        # KT-calibrated mastery (falls back to heuristic if insufficient data)
        kt_result = await self.kt.predict_mastery(
            student_input.student_id, student.current_topic,
            heuristic_fallback=concept.knowledge,
        )
        kt_mastery = kt_result["p_correct"]

        # RL ACTION: (mode, hint, difficulty)
        # P4: experiment-aware policy selection.
        # If RL A/B experiment is active, arm decides policy per user.
        # Otherwise fall back to global RL_ENABLED flag.
        exp_mgr = get_experiment_manager()
        ab_arm = await exp_mgr.get_arm(student_input.student_id, RL_VS_RULE_EXPERIMENT)
        use_dqn = False
        if ab_arm == ARM_TREATMENT and self.dqn_validated:
            use_dqn = True
        elif ab_arm is None:
            # No active experiment → use global flag
            use_dqn = RL_ENABLED and self.dqn_validated

        if use_dqn:
            action_idx, action = self.agent.get_action(
                student, explore=False, serve_epsilon=self.serve_epsilon,
                kt_mastery=kt_mastery,
            )
            mode, hint, difficulty = action
        else:
            # Simple mastery rule policy (transparent, no RL needed)
            from training.baselines import MasteryThresholdPolicy
            _fallback = MasteryThresholdPolicy()
            concept_dict = {"knowledge": concept.knowledge}
            traits_dict = {
                "frustration": student.frustration, "fatigue": student.fatigue,
                "confidence": student.confidence,
            }
            mode, hint, difficulty = _fallback.select_action(traits_dict, concept_dict)
            action_idx = None  # no DQN action index
        level = self._difficulty_label(difficulty)

        # RL observability: log decision + record metrics
        self.agent.metrics.record_decision(mode, hint, difficulty, self.agent.epsilon)
        policy_tag = "dqn" if use_dqn else "mastery_rule"
        logger.info(
            "rl_decision student=%s mode=%d hint=%d difficulty=%.2f epsilon=%.4f step=%d topic=%s policy=%s",
            student_input.student_id, mode, hint, difficulty,
            self.agent.epsilon, self.agent.step_counter,
            student_input.current_topic, policy_tag,
        )

        profile = self._build_profile(student, concept)
        tone = get_tone_directive(student)

        # --- E9: Language + reading-level directive ---
        user_doc = await users_collection.find_one({"username": student_input.student_id})
        lang_dir = get_language_directive((user_doc or {}).get("preferences"))

        # --- E3: Mentor persona directive ---
        is_socratic = mode in (MODE_SOCRATIC_PROBE, MODE_REVEAL_STEP, MODE_CHALLENGE)
        mentor_directive = await self._get_mentor_directive(
            student_input.student_id, student, is_socratic=is_socratic,
        )

        # --- G7: Answer-leakage guard ---
        # Check last student message in conversation for extraction attempts
        if mode in (MODE_SOCRATIC_PROBE, MODE_REVEAL_STEP, MODE_CHALLENGE):
            last_student_msg = ""
            for msg in reversed(student.conversation):
                if msg.get("role") == "student":
                    last_student_msg = msg.get("content", "")
                    break

            if last_student_msg:
                flagged, category, matched = classify_message(last_student_msg)
                if flagged:
                    redirect = get_redirect_response(
                        category, topic=student.current_topic, mode=mode,
                    )
                    logger.warning(
                        "leakage_guard flagged student=%s category=%s matched='%s'",
                        student_input.student_id, category, matched,
                    )
                    # Return redirect as the question instead of generating normally
                    student.history.append({
                        "question": redirect["redirect_response"],
                        "answer": "",
                        "mode": MODE_NAMES.get(mode, "socratic_probe"),
                        "difficulty": level,
                        "model_used": "leakage_guard",
                        "verified": None,
                        "verification_method": "none",
                        "created_at": time.time(),
                        "leakage_flagged": True,
                        "leakage_category": category,
                    })
                    student.conversation.append({
                        "role": "tutor",
                        "content": redirect["redirect_response"],
                        "mode": "redirect",
                        "timestamp": time.time(),
                    })
                    await self.sessions.save(student)
                    return {
                        "mode": "redirect",
                        "question": redirect["redirect_response"],
                        "hint_level": hint,
                        "difficulty": difficulty,
                        "explanation": {"leakage_guard": {
                            "flagged": True,
                            "category": category,
                        }},
                    }

        # Anti-disclosure instruction for Socratic modes
        anti_disclosure = get_anti_disclosure_instruction(mode)
        if anti_disclosure:
            tone = f"{tone}\n\n{anti_disclosure}" if tone else anti_disclosure

        # Get core concept from explainer (used by all modes)
        explanation = await self.explainer.generate_explanation(
            topic=student.current_topic,
            student_profile=profile,
            tone_directive=tone,
            language_directive=lang_dir,
            mentor_directive=mentor_directive,
        )

        core_concept = explanation.get("core_concept", student.current_topic)

        # -----------------------------
        # ROUTE BY MODE
        # -----------------------------

        # P2.3: Carry last misconception to shape next question
        _last_misc = getattr(student, "last_misconception", "") or ""

        if mode == MODE_DIRECT_QUESTION:
            result = await self.generator.generate_question(
                explanation=explanation,
                topic=student.current_topic,
                difficulty=level,
                frustration=student.frustration,
                knowledge=concept.knowledge,
                tone_directive=tone,
                language_directive=lang_dir,
                mentor_directive=mentor_directive,
                last_misconception=_last_misc,
            )
            question_text = result["question"]
            answer_text = result.get("answer", "")

        elif mode == MODE_SOCRATIC_PROBE:
            result = await self.socratic.generate_socratic_probe(
                topic=student.current_topic,
                core_concept=core_concept,
                knowledge_level=concept.knowledge,
                frustration=student.frustration,
                curiosity=student.curiosity,
                conversation_context=student.conversation,
                tone_directive=tone,
                language_directive=lang_dir,
                mentor_directive=mentor_directive,
            )
            question_text = result["question"]
            answer_text = result.get("answer", "")
            explanation["socratic"] = {
                "expected_insight": result.get("expected_insight", ""),
                "follow_up_if_stuck": result.get("follow_up_if_stuck", ""),
                "thinking_direction": result.get("thinking_direction", ""),
            }

        elif mode == MODE_REVEAL_STEP:
            result = await self.socratic.generate_reveal_step(
                topic=student.current_topic,
                core_concept=core_concept,
                knowledge_level=concept.knowledge,
                difficulty=level,
                conversation_context=student.conversation,
                tone_directive=tone,
                language_directive=lang_dir,
                mentor_directive=mentor_directive,
            )
            question_text = result["question"]
            answer_text = result.get("answer", "")
            explanation["revealed_step"] = result.get("revealed_step", "")
            explanation["problem_context"] = result.get("problem_context", "")
            explanation["checkpoint_hint"] = result.get("checkpoint_hint", "")

        elif mode == MODE_CHALLENGE:
            result = await self.socratic.generate_challenge(
                topic=student.current_topic,
                core_concept=core_concept,
                knowledge_level=concept.knowledge,
                mastery=concept.concept_mastery,
                difficulty=level,
                conversation_context=student.conversation,
                tone_directive=tone,
                language_directive=lang_dir,
                mentor_directive=mentor_directive,
            )
            question_text = result["question"]
            answer_text = result.get("answer", "")
            explanation["challenge"] = {
                "why_its_tricky": result.get("why_its_tricky", ""),
                "common_trap": result.get("common_trap", ""),
                "deep_insight": result.get("deep_insight", ""),
            }

        else:
            # Safety fallback
            result = await self.generator.generate_question(
                explanation=explanation,
                topic=student.current_topic,
                difficulty=level,
                frustration=student.frustration,
                knowledge=concept.knowledge,
                tone_directive=tone,
                language_directive=lang_dir,
                mentor_directive=mentor_directive,
                last_misconception=_last_misc,
            )
            question_text = result["question"]
            answer_text = result.get("answer", "")
            mode = MODE_DIRECT_QUESTION

        # UPDATE CONVERSATION CONTEXT
        student.conversation.append({
            "role": "tutor",
            "content": question_text,
            "mode": MODE_NAMES.get(mode, "direct_question"),
            "timestamp": time.time()
        })
        student.conversation = student.conversation[-20:]
        student.conversation_turns += 1
        student.last_mode = mode

        # STORE HISTORY
        state = self.agent.get_state(student, kt_mastery=kt_mastery).tolist()
        MAX_HISTORY = 100

        student.history.append({
            "state": state,
            "action_index": action_idx,
            "mode": mode,
            "hint": hint,
            "difficulty": difficulty,
            "topic": student.current_topic,
            "question": question_text,
            "answer": answer_text,
            "model_used": result.get("model_used", "unknown"),
            "verified": result.get("verified"),
            "verification_method": result.get("verification_method", "none"),
            "created_at": time.time()
        })

        student.history = student.history[-MAX_HISTORY:]

        await self.sessions.save(student)

        return {
            "mode": MODE_NAMES.get(mode, "direct_question"),
            "question": question_text,
            "hint_level": hint,
            "difficulty": difficulty,
            "explanation": explanation
        }

    # ------------------------------------------------
    # SELECT TOPIC (LLM / USER CONTROL)
    # ------------------------------------------------

    async def select_topic(self, student_id, topic):
        student = await self.sessions.get_student(student_id)

        # P2.1: Mastery-gated prerequisite check
        prereq = await self.prereq.get_prerequisites(topic)
        unmastered = []
        mastery_status = {}

        for p in prereq:
            kt_r = await self.kt.predict_mastery(student_id, p, heuristic_fallback=0.3)
            p_correct = kt_r["p_correct"]
            mastery_status[p] = {
                "mastery": round(p_correct, 3),
                "method": kt_r["method"],
                "unlocked": p_correct >= self._mastery_threshold,
            }
            if p_correct < self._mastery_threshold:
                unmastered.append(p)

        if unmastered and self._enforce_mastery_gating:
            return {
                "prerequisites": prereq,
                "mastery_status": mastery_status,
                "blocked": True,
                "unmastered": unmastered,
                "message": f"Master these first: {', '.join(unmastered)}",
                "threshold": self._mastery_threshold,
            }

        student.current_topic = topic
        await self.sessions.save(student)
        return {
            "prerequisites": prereq,
            "mastery_status": mastery_status,
            "blocked": False,
            "unmastered": [],
            "message": f"Topic '{topic}' unlocked!",
            "threshold": self._mastery_threshold,
        }

    # ------------------------------------------------
    # SUBMIT ANSWER
    # ------------------------------------------------

    async def submit_answer(self, student_id, student_answer):

        student = await self.sessions.get_student(student_id)

        if student is None or not student.history:
            return {"error": "No active question"}

        q = student.history[-1]

        end_time = time.time()
        start_time = q["created_at"]

        # EVALUATE (LLM - DIAGNOSTIC -- now async)
        concept = student.get_current_concept()

        result = await self.evaluator.evaluate(
            question=q["question"],
            student_answer=student_answer,
            correct_answer=q["answer"],
            start_time=start_time,
            end_time=end_time,
            topic=student.current_topic,
            knowledge=concept.knowledge,
            generator_model=q.get("model_used", ""),
        )

        last = student.history[-1]

        evaluation = {
            "student_id": student_id,
            "correct": result["correct"],
            "response_time": result["response_time"],
            "hint_used": last["hint"],
            "difficulty": last["difficulty"]
        }

        reward = await self.learn(student_id, evaluation)

        student.conversation.append({
            "role": "student",
            "content": student_answer,
            "correct": result["correct"],
            "timestamp": time.time()
        })
        student.conversation = student.conversation[-20:]

        # P2.3: Store last misconception for next question targeting
        student.last_misconception = result.get("misconception", "") if not result["correct"] else ""

        student.current_question = None

        await self.sessions.update_student_state(student_id, result["correct"], student.current_topic)
        await self.sessions.save(student)

        # -- G8: Append-only interaction log (leakage-safe) --
        # Only fields known at answer time -- no post-hoc aggregates.
        interaction = {
            "student_id": student_id,
            "skill_id": student.current_topic,
            "item_id": q.get("question", "")[:200],  # truncated question as item ID
            "correct": bool(result["correct"]),
            "response_time": round(result["response_time"], 3),
            "hint_level": int(last.get("hint", 0)),
            "difficulty": float(last.get("difficulty", 0.4)),
            "mode": int(last.get("mode", 0)),
            "score": float(result.get("score", 0.0)),
            "grade": result.get("grade", ""),
            "timestamp": end_time,
        }
        try:
            await interactions_collection.insert_one(interaction)
            self.kt.invalidate_cache(student_id)  # refresh KT predictions
        except Exception as e:
            logger.warning("Failed to log interaction: %s", e)

        # P2.2: On wrong answer with misconception, auto-generate Socratic probe
        misconception_probe = None
        if not result["correct"] and result.get("misconception"):
            try:
                tone_dir = get_tone_directive(student)
                user_doc = await users_collection.find_one({"username": student_id})
                lang_dir = get_language_directive((user_doc or {}).get("preferences"))
                mentor_dir = ""
                try:
                    mentor_dir = await self._get_mentor_directive(
                        student_id, student, is_socratic=True,
                    )
                except Exception:
                    pass

                misconception_probe = await self.socratic.generate_misconception_probe(
                    topic=student.current_topic or "",
                    question=q["question"],
                    student_answer=student_answer,
                    correct_answer=q["answer"],
                    misconception=result.get("misconception", ""),
                    root_concept=result.get("root_concept", ""),
                    error_type=result.get("error_type", "conceptual"),
                    tone_directive=tone_dir,
                    language_directive=lang_dir,
                    mentor_directive=mentor_dir,
                )
            except Exception as e:
                logger.warning("Misconception probe generation failed: %s", e)

        response = {
            "correct": result["correct"],
            # Alias so serve.py post-answer hooks (analytics, quests, mistakes,
            # certificates) read a consistent key. Keep "correct" for the frontend.
            "is_correct": result["correct"],
            "score": result["score"],
            "reasoning": result["reasoning"],
            "response_time": result["response_time"],
            "reward": reward,
            "error_type": result.get("error_type", "none"),
            "misconception": result.get("misconception"),
            "root_concept": result.get("root_concept"),
            "targeted_feedback": result.get("targeted_feedback", ""),
            "remediation": result.get("remediation", ""),
            # Context needed by downstream hooks in serve.py /submit_answer
            "topic": student.current_topic,
            "difficulty": last.get("difficulty", 0.4),
            "concept_tested": result.get("root_concept", "") or student.current_topic,
            "original_question": q.get("question", ""),
            "correct_answer": q.get("answer", ""),
        }

        if misconception_probe:
            response["misconception_probe"] = misconception_probe

        return response

    # ------------------------------------------------
    # RL LEARNING (USES SHARED MATH)
    # ------------------------------------------------

    async def learn(self, student_id, evaluation):

        student = await self.sessions.get_student(student_id)

        if student is None:
            return 0

        if not student.history:
            raise HTTPException(400, "No question history found for this student")

        last = student.history[-1]

        state = last["state"]
        action = last["action_index"]
        difficulty = last["difficulty"]
        hint = last["hint"]
        mode = last.get("mode", MODE_DIRECT_QUESTION)

        correct = evaluation["correct"]
        time_taken = evaluation["response_time"]
        hint_used = evaluation["hint_used"]

        # BUILD TRAIT / CONCEPT DICTS
        concept_obj = student.get_current_concept()
        concept_dict = {
            "knowledge": concept_obj.knowledge,
            "concept_mastery": concept_obj.concept_mastery,
        }
        traits = {
            "learning_velocity": student.learning_velocity,
            "confidence": student.confidence,
            "engagement": student.engagement,
            "frustration": student.frustration,
            "streak": student.streak,
            "fatigue": student.fatigue,
            "cognitive_load": student.cognitive_load,
            "hint_dependency": student.hint_dependency,
            "focus": student.focus,
            "curiosity": student.curiosity,
            "retention": student.retention,
            "speed": student.speed,
        }

        def _mark_reviewed(c_dict):
            ReviewEngine.mark_reviewed(
                concept_obj,
                correct=correct,
                response_time=time_taken,
                hint_level=hint_used,
            )


        # SHARED UPDATE + REWARD
        old_knowledge, old_engagement = update_student_traits(
            traits, concept_dict, correct, time_taken, hint_used, difficulty,
            mark_reviewed_fn=_mark_reviewed,
        )

        reward = compute_reward(
            traits, concept_dict, correct, time_taken, hint, difficulty, mode,
            old_knowledge, old_engagement,
        )

        # WRITE BACK
        concept_obj.knowledge = concept_dict["knowledge"]
        concept_obj.concept_mastery = concept_dict["concept_mastery"]

        for key, val in traits.items():
            setattr(student, key, val)


        # STORE TRANSITION + TRAIN
        # -- SINGLE REWARD SOURCE: the DQN agent ONLY learns from
        # core.reward.compute_reward (the `reward` var above).
        # The evaluator's ux_score is a display metric and must NOT
        # be passed here. See R2 in the project spec. --
        next_state = (self.agent.get_state(student)).tolist()

        # P4: experiment-aware DQN training
        exp_mgr = get_experiment_manager()
        ab_arm = await exp_mgr.get_arm(student_id, RL_VS_RULE_EXPERIMENT)
        use_dqn_learn = False
        if ab_arm == ARM_TREATMENT and self.dqn_validated:
            use_dqn_learn = True
        elif ab_arm is None:
            use_dqn_learn = RL_ENABLED

        if use_dqn_learn:
            self.agent.store_transition(state, action, reward, next_state, done=False)
            self.agent.train_step()

        # RL observability
        policy_tag = "dqn" if use_dqn_learn else "mastery_rule"
        self.agent.metrics.record_reward(reward)
        logger.info(
            "rl_learn student=%s reward=%.4f correct=%s mode=%d difficulty=%.2f hint=%d mean_reward=%.4f policy=%s",
            student_id, reward, correct, mode, difficulty, hint,
            self.agent.metrics.mean_reward(), policy_tag,
        )

        # P4: Track per-answer metrics for A/B experiment
        if ab_arm is not None:
            try:
                await exp_mgr.track_answer_metrics(
                    student_id=student_id,
                    experiment_id=RL_VS_RULE_EXPERIMENT,
                    correct=correct,
                    frustration=student.frustration,
                    mastery=concept_obj.knowledge,
                    response_time=time_taken,
                    policy_tag=policy_tag,
                )
            except Exception as e:
                logger.warning("Failed to track AB metric: %s", e)

        # --- E3: Extract & persist mentor memory ---
        memory_facts = extract_memory_facts(
            student_id=student_id,
            topic=student.current_topic,
            correct=correct,
            streak=student.streak,
            concept_mastery=concept_obj.concept_mastery,
            evaluation=evaluation,
        )
        for mf in memory_facts:
            await save_memory_item(
                mentor_memory_collection, student_id,
                fact=mf["fact"], category=mf["category"],
            )

        return reward

    # ------------------------------------------------
    # GENERATE QUESTION (ASYNC)
    # ------------------------------------------------

    async def generate_question(self, student_id):

        student = await self.sessions.get_student(student_id)
        concept = student.get_current_concept()
        profile = self._build_profile(student, concept)

        # P4: experiment-aware policy selection (same logic as decide)
        exp_mgr = get_experiment_manager()
        ab_arm = await exp_mgr.get_arm(student_id, RL_VS_RULE_EXPERIMENT)
        use_dqn = False
        if ab_arm == ARM_TREATMENT and self.dqn_validated:
            use_dqn = True
        elif ab_arm is None:
            use_dqn = RL_ENABLED and self.dqn_validated

        if use_dqn:
            action_idx, action = self.agent.get_action(
                student, explore=False, serve_epsilon=self.serve_epsilon
            )
            mode, hint_level, difficulty = action
        else:
            from training.baselines import MasteryThresholdPolicy
            _fb = MasteryThresholdPolicy()
            _c = {"knowledge": concept.knowledge}
            _t = {"frustration": student.frustration, "fatigue": student.fatigue, "confidence": student.confidence}
            mode, hint_level, difficulty = _fb.select_action(_t, _c)
            action_idx = None
        difficulty_level = self._difficulty_label(difficulty)

        # RL observability
        self.agent.metrics.record_decision(mode, hint_level, difficulty, self.agent.epsilon)
        logger.info(
            "rl_decision student=%s mode=%d hint=%d difficulty=%.2f epsilon=%.4f step=%d topic=%s",
            student_id, mode, hint_level, difficulty,
            self.agent.epsilon, self.agent.step_counter,
            student.current_topic,
        )

        tone = get_tone_directive(student)

        # --- E9: Language + reading-level directive ---
        user_doc = await users_collection.find_one({"username": student_id})
        lang_dir = get_language_directive((user_doc or {}).get("preferences"))

        explanation = await self.explainer.generate_explanation(
            topic=student.current_topic,
            student_profile=profile,
            tone_directive=tone,
            language_directive=lang_dir,
        )

        question = await self.generator.generate_question(
            explanation=explanation,
            topic=student.current_topic,
            difficulty=difficulty_level,
            frustration=student.frustration,
            knowledge=concept.knowledge,
            tone_directive=tone,
            language_directive=lang_dir,
        )

        student.current_question = question

        student.history.append({
            "state": self.agent.get_state(student).tolist(),
            "action_index": action_idx,
            "mode": mode,
            "difficulty": difficulty,
            "hint": hint_level,
            "question": question["question"],
            "answer": question.get("answer", ""),
            "created_at": time.time()
        })

        await self.sessions.save(student)

        return {
            "mode": MODE_NAMES.get(mode, "direct_question"),
            "question": question["question"],
            "hint_level": hint_level,
            "difficulty": difficulty
        }
