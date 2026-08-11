import time
from typing import Dict, List

from core.llm_registry import build_models
from core.llm_utils import call_llm
from core.review_engine import ReviewEngine
from core.prompts import study_planner as prompt_tmpl


class StudyPlanner:

    def __init__(self):
        self.models = build_models()
        self.review_engine = ReviewEngine()

    @staticmethod
    def build_study_profile(student, available_minutes: int = 30) -> Dict:
        weak = []
        strong = []

        for topic, concept in student.concepts.items():
            mastery = concept.concept_mastery
            if mastery < 0.5:
                weak.append({"topic": topic, "mastery": round(mastery, 2)})
            elif mastery > 0.8:
                strong.append({"topic": topic, "mastery": round(mastery, 2)})

        if len(student.history) >= 2:
            timestamps = [h.get("created_at", 0) for h in student.history]
            session_gaps = []
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i - 1]
                if gap < 3600:
                    session_gaps.append(gap)
            avg_session_sec = sum(session_gaps) / max(1, len(session_gaps))
            avg_session_min = round(avg_session_sec / 60, 1)
        else:
            avg_session_min = 15.0

        history = student.history
        if len(history) >= 10:
            recent = history[-5:]
            older = history[-10:-5]
            recent_correct = sum(1 for h in recent if h.get("correct", False))
            older_correct = sum(1 for h in older if h.get("correct", False))
            if recent_correct > older_correct:
                trend = "improving"
            elif recent_correct < older_correct:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "not enough data"

        import datetime
        day = datetime.datetime.now(datetime.timezone.utc).strftime("%A")

        return {
            "weak_concepts": weak,
            "strong_concepts": strong,
            "avg_session_minutes": avg_session_min,
            "fatigue": round(student.fatigue, 2),
            "frustration": round(student.frustration, 2),
            "streak": student.streak,
            "engagement_trend": trend,
            "available_minutes": available_minutes,
            "day": day,
        }

    async def generate_plan(
        self,
        student,
        available_minutes: int = 30,
        tone_directive: str = "",
        language_directive: str = "",
    ) -> Dict:

        profile = self.build_study_profile(student, available_minutes)

        weak_str = ", ".join(
            f"{c['topic']} (mastery={c['mastery']})" for c in profile["weak_concepts"]
        ) or "none identified"

        strong_str = ", ".join(
            f"{c['topic']} (mastery={c['mastery']})" for c in profile["strong_concepts"]
        ) or "none yet"

        prompt = prompt_tmpl.build(weak_str, strong_str, profile, available_minutes, tone_directive, language_directive=language_directive)

        data = await call_llm(
            self.models, prompt, required_key="plan",
            engine_name="study_planner",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "plan": data.get("plan", []),
                "motivational_note": data.get("motivational_note", ""),
                "estimated_knowledge_gain": data.get("estimated_knowledge_gain", ""),
                "profile_summary": profile,
                "model_used": data.get("model_used", "unknown"),
            }

        plan = []
        remaining = available_minutes
        if profile["strong_concepts"] and remaining >= 5:
            t = profile["strong_concepts"][0]["topic"]
            plan.append({"topic": t, "duration_min": 5, "type": "review", "reason": "Confidence boost"})
            remaining -= 5
        for wc in profile["weak_concepts"]:
            if remaining < 5:
                break
            dur = min(15, remaining)
            plan.append({"topic": wc["topic"], "duration_min": dur, "type": "learn", "reason": f"Weak area (mastery={wc['mastery']})"})
            remaining -= dur

        return {
            "plan": plan,
            "motivational_note": "Keep going! Every session builds on the last.",
            "estimated_knowledge_gain": "Incremental improvement in weak areas.",
            "profile_summary": profile,
            "model_used": "fallback",
        }
