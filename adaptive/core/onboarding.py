"""
Core Onboarding Engine — Placement session generation, adaptive questioning, and BKT mastery seeding.
Version: 1.0.1
"""

import uuid
from typing import Any, Dict, List, Optional

PLACEMENT_TOPICS = ["Algebra", "Calculus", "Linear Algebra", "Probability", "Statistics"]

PLACEMENT_QUESTIONS = {
    "Algebra": {
        "question": "Solve for x: 2x + 5 = 13",
        "options": ["x = 3", "x = 4", "x = 5", "x = 6"],
        "answer": "x = 4",
        "difficulty": 0.3,
    },
    "Calculus": {
        "question": "What is the derivative of f(x) = x^2?",
        "options": ["2x", "x", "x^2", "2"],
        "answer": "2x",
        "difficulty": 0.4,
    },
    "Linear Algebra": {
        "question": "What is the determinant of a 2x2 identity matrix?",
        "options": ["0", "1", "2", "-1"],
        "answer": "1",
        "difficulty": 0.3,
    },
    "Probability": {
        "question": "What is the probability of rolling a 6 on a fair 6-sided die?",
        "options": ["1/6", "1/2", "1/3", "1/12"],
        "answer": "1/6",
        "difficulty": 0.2,
    },
    "Statistics": {
        "question": "Which measure of central tendency is the middle value in an ordered dataset?",
        "options": ["Mean", "Median", "Mode", "Variance"],
        "answer": "Median",
        "difficulty": 0.3,
    },
}


def create_session(student_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize a placement test session for a new student."""
    return {
        "session_id": uuid.uuid4().hex,
        "student_id": student_id,
        "profile": profile_data,
        "topics_to_assess": list(PLACEMENT_TOPICS),
        "current_index": 0,
        "current_difficulty": 0.5,
        "results": {},
        "current_question": None,
        "completed": False,
    }


def pick_question(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the next question based on current topic index."""
    idx = session.get("current_index", 0)
    topics = session.get("topics_to_assess", PLACEMENT_TOPICS)

    if idx >= len(topics):
        return None

    topic = topics[idx]
    q_data = PLACEMENT_QUESTIONS.get(topic)

    if not q_data:
        return {
            "question": f"Sample question on {topic}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": "Option A",
            "topic": topic,
            "difficulty": session.get("current_difficulty", 0.5),
        }

    return {
        "question": q_data["question"],
        "options": q_data["options"],
        "answer": q_data["answer"],
        "topic": topic,
        "difficulty": q_data["difficulty"],
    }


def evaluate_and_adapt(
    session: Dict[str, Any],
    user_answer: str,
    current_question: Dict[str, Any]
) -> bool:
    """Evaluate user answer and adapt test difficulty."""
    correct_ans = current_question.get("answer", "").strip().lower()
    given_ans = user_answer.strip().lower()

    is_correct = (given_ans == correct_ans) or (correct_ans in given_ans)

    topic = current_question.get("topic", "General")
    if "results" not in session:
        session["results"] = {}

    session["results"][topic] = {
        "correct": is_correct,
        "user_answer": user_answer,
        "topic": topic,
    }

    session["current_index"] = session.get("current_index", 0) + 1

    curr_diff = session.get("current_difficulty", 0.5)
    if is_correct:
        session["current_difficulty"] = min(1.0, curr_diff + 0.1)
    else:
        session["current_difficulty"] = max(0.1, curr_diff - 0.1)

    return is_correct


def compute_mastery_seeds(session: Dict[str, Any]) -> Dict[str, float]:
    """Calculate initial BKT mastery seeds from placement session results."""
    results = session.get("results", {})
    seeds = {}

    for topic in PLACEMENT_TOPICS:
        if topic in results:
            seeds[topic] = 0.75 if results[topic].get("correct") else 0.35
        else:
            seeds[topic] = 0.50

    return seeds
