"""
Review Engine with FSRS (Free Spaced Repetition Scheduler).

Replaces the heuristic forgetting model with FSRS's Difficulty-Stability-
Retrievability model. Uses py-fsrs (open-spaced-repetition) for scheduling.

Each (student, concept) maintains an FSRS card. On every answer:
  1. Map result to FSRS rating (Again/Hard/Good/Easy)
  2. Update the card
  3. Persist updated state in the concept document

Review scheduling uses predicted recall probability instead of linear decay.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from fsrs import Scheduler, Card, Rating, State
    _scheduler = Scheduler(
        desired_retention=0.9,
        enable_fuzzing=False,
    )
    FSRS_AVAILABLE = True
except ImportError:
    FSRS_AVAILABLE = False
    Scheduler = Card = Rating = State = None
    _scheduler = None

from adaptive.core.llm_registry import build_models_cheap
from adaptive.core.llm_utils import call_llm
from adaptive.core.prompts import review as prompt_tmpl


def _get_or_create_card(concept):
    if not FSRS_AVAILABLE or Card is None:
        return None
    fsrs_state = getattr(concept, "fsrs_state", None)
    if fsrs_state and isinstance(fsrs_state, dict):
        try:
            return Card.from_dict(fsrs_state)
        except Exception:
            pass
    return Card()


def _save_card(concept, card):
    if card and hasattr(card, "to_dict"):
        concept.fsrs_state = card.to_dict()


def map_rating(correct: bool, response_time: float = 0, hint_level: int = 0):
    if not FSRS_AVAILABLE or Rating is None:
        return 1
    if not correct:
        return Rating.Again
    if response_time < 5 and hint_level == 0:
        return Rating.Easy
    if hint_level >= 2 or response_time > 30:
        return Rating.Hard
    return Rating.Good


class ReviewEngine:

    def __init__(self):
        self.models = build_models_cheap()
        self.scheduler = _scheduler

    def get_retrievability(self, concept) -> float:
        card = _get_or_create_card(concept)
        now = datetime.now(timezone.utc)
        if not card or card.last_review is None:
            return concept.concept_mastery
        try:
            return card.get_retrievability(now)
        except Exception:
            return concept.concept_mastery

    def get_due_topics(self, student, threshold: float = 0.9) -> List[Dict]:
        due = []
        now = datetime.now(timezone.utc)

        for topic, concept in student.concepts.items():
            card = _get_or_create_card(concept)

            if not card or card.last_review is None:
                if concept.concept_mastery > 0.1:
                    due.append({
                        "topic": topic,
                        "mastery": round(concept.concept_mastery, 2),
                        "retention_estimate": round(concept.concept_mastery, 2),
                        "days_since_review": 999,
                        "review_count": getattr(concept, "review_count", 0),
                        "fsrs_stability": None,
                        "fsrs_difficulty": None,
                    })
                continue

            try:
                retrievability = card.get_retrievability(now)
            except Exception:
                retrievability = 0.5

            if retrievability < threshold:
                elapsed = (now - card.last_review).total_seconds() / 86400.0
                due.append({
                    "topic": topic,
                    "mastery": round(concept.concept_mastery, 2),
                    "retention_estimate": round(retrievability, 4),
                    "days_since_review": round(elapsed, 1),
                    "review_count": getattr(concept, "review_count", 0),
                    "fsrs_stability": round(card.stability, 2) if card.stability else None,
                    "fsrs_difficulty": round(card.difficulty, 2) if card.difficulty else None,
                })

        due.sort(key=lambda x: x["retention_estimate"])
        return due

    @staticmethod
    def mark_reviewed(concept, correct: bool = True,
                      response_time: float = 10.0, hint_level: int = 0):
        card = _get_or_create_card(concept)
        if not _scheduler or not FSRS_AVAILABLE or not card:
            concept.last_reviewed = time.time()
            concept.review_count = getattr(concept, "review_count", 0) + 1
            return
        now = datetime.now(timezone.utc)
        rating = map_rating(correct, response_time, hint_level)
        updated_card, review_log = _scheduler.review_card(card, rating, now)
        _save_card(concept, updated_card)
        concept.last_reviewed = time.time()
        concept.review_count = getattr(concept, "review_count", 0) + 1
        logger.debug(
            "FSRS review: rating=%s stability=%.2f difficulty=%.2f due=%s",
            rating.name,
            updated_card.stability or 0,
            updated_card.difficulty or 0,
            updated_card.due,
        )

    @staticmethod
    def estimate_retention(concept) -> float:
        engine = ReviewEngine.__new__(ReviewEngine)
        engine.scheduler = _scheduler
        return engine.get_retrievability(concept)

    async def generate_review_question(
        self,
        topic: str,
        days_ago: float,
        mastery: float,
        retention_estimate: float,
        tone_directive: str = "",
        language_directive: str = "",
        mentor_directive: str = "",
    ) -> Dict:
        prompt = prompt_tmpl.build(topic, days_ago, mastery, retention_estimate, tone_directive, mentor_directive=mentor_directive, language_directive=language_directive)

        data = await call_llm(
            self.models, prompt, required_key="question",
            engine_name="review",
            prompt_version=prompt_tmpl.VERSION,
        )

        if data:
            return {
                "topic": topic,
                "refresher": data.get("refresher"),
                "question": data.get("question", ""),
                "answer": data.get("answer", ""),
                "tests_concept": data.get("tests_concept", ""),
                "retention_estimate": retention_estimate,
                "days_since_review": days_ago,
                "model_used": data.get("model_used", "unknown")
            }

        refresher = f"Quick reminder: {topic} is about understanding core principles." if retention_estimate < 0.4 else None
        return {
            "topic": topic,
            "refresher": refresher,
            "question": f"Can you explain the key idea behind {topic} in your own words?",
            "answer": "",
            "tests_concept": f"Core understanding of {topic}",
            "retention_estimate": retention_estimate,
            "days_since_review": days_ago,
            "model_used": "fallback"
        }
