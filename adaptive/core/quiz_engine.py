"""
Quiz Engine: generates LLM-powered MCQ quizzes with 4 options per question.
Supports single-correct and multiple-correct questions.
"""
import logging
from adaptive.core.llm_utils import call_llm
from adaptive.core.llm_registry import build_models_cheap
from adaptive.core.prompts import quiz_generator
from adaptive.core.llm_utils import parse_json_robust as safe_parse_json

logger = logging.getLogger(__name__)

# Fallback quiz when LLM fails
FALLBACK_QUIZ = {
    "quiz_title": "Quick Review Quiz",
    "questions": [
        {
            "id": i + 1,
            "question": q,
            "options": opts,
            "correct": correct,
            "multiple": mult,
            "concept": concept,
            "explanation": expl,
            "difficulty": diff,
        }
        for i, (q, opts, correct, mult, concept, expl, diff) in enumerate([
            (
                "What is the primary purpose of a variable in programming?",
                {"A": "To store data", "B": "To create loops", "C": "To define functions", "D": "To import libraries"},
                ["A"], False, "variables", "Variables store data values that can be referenced and manipulated.", "easy"
            ),
            (
                "Which of the following are valid data types? (Select all that apply)",
                {"A": "Integer", "B": "Looper", "C": "String", "D": "Boolean"},
                ["A", "C", "D"], True, "data types", "Integer, String, and Boolean are fundamental data types.", "easy"
            ),
            (
                "What does a function return if no return statement is specified?",
                {"A": "0", "B": "None/null", "C": "An error", "D": "Empty string"},
                ["B"], False, "functions", "Functions return None (Python) or undefined (JS) by default.", "medium"
            ),
            (
                "Which sorting algorithm has the best average-case time complexity?",
                {"A": "Bubble Sort - O(n^2)", "B": "Merge Sort - O(n log n)", "C": "Selection Sort - O(n^2)", "D": "Insertion Sort - O(n^2)"},
                ["B"], False, "algorithms", "Merge Sort has O(n log n) average-case complexity.", "hard"
            ),
            (
                "What is encapsulation in OOP?",
                {"A": "Inheriting from a parent class", "B": "Bundling data and methods that operate on that data", "C": "Creating multiple instances", "D": "Overriding methods"},
                ["B"], False, "OOP concepts", "Encapsulation bundles data with the methods that operate on it.", "medium"
            ),
        ])
    ],
}


class QuizGenerator:
    """Generate topic-specific MCQ quizzes via LLM."""

    def __init__(self):
        self.models = build_models_cheap()  # P3.1: quiz gen uses cheap tier

    async def generate_quiz(
        self,
        topic: str,
        num_questions: int = 10,
        tone_directive: str = "",
        language_directive: str = "",
    ) -> dict:
        """Generate a quiz with num_questions MCQs on the given topic."""
        prompt = quiz_generator.build(
            topic=topic,
            num_questions=num_questions,
            tone_directive=tone_directive,
            language_directive=language_directive,
        )

        result = await call_llm(
            self.models,
            prompt=prompt,
            required_key="questions",
            engine_name="quiz_generator",
            prompt_version=quiz_generator.VERSION,
        )

        if result is None:
            logger.warning("LLM returned None for quiz, using fallback")
            fallback = FALLBACK_QUIZ.copy()
            fallback["quiz_title"] = f"Quiz: {topic}"
            return fallback

        parsed = result  # call_llm already returns parsed dict
        if "questions" not in parsed:
            logger.warning("Quiz response missing 'questions' key, using fallback")
            fallback = FALLBACK_QUIZ.copy()
            fallback["quiz_title"] = f"Quiz: {topic}"
            return fallback

        # Validate and normalize questions
        questions = []
        for i, q in enumerate(parsed["questions"][:num_questions]):
            questions.append({
                "id": i + 1,
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                "correct": q.get("correct", []),
                "multiple": q.get("multiple", len(q.get("correct", [])) > 1),
                "concept": q.get("concept", ""),
                "explanation": q.get("explanation", ""),
                "difficulty": q.get("difficulty", "medium"),
            })

        return {
            "quiz_title": parsed.get("quiz_title", f"Quiz: {topic}"),
            "questions": questions,
        }

    def score_quiz(self, questions: list[dict], answers: dict[int, list[str]]) -> dict:
        """
        Score submitted MCQ answers. Open-ended questions (type == "open") are
        skipped here — they are graded separately via the answer evaluator.
        answers: {question_id: [selected_options]}
        Returns per-question results and overall score for the MCQ portion.
        """
        results = []
        correct_count = 0

        mcq = [q for q in questions if q.get("type", "mcq") != "open"]

        for q in mcq:
            qid = q["id"]
            submitted = sorted(answers.get(qid, []))
            expected = sorted(q["correct"])
            is_correct = submitted == expected

            if is_correct:
                correct_count += 1

            results.append({
                "id": qid,
                "type": "mcq",
                "question": q["question"],
                "submitted": submitted,
                "correct": expected,
                "correct_answer": ", ".join(expected),
                "is_correct": is_correct,
                "multiple": q.get("multiple", False),
                "explanation": q.get("explanation", ""),
                "concept": q.get("concept", ""),
                "hints_used": q.get("hints_used", 0),
            })

        total = len(mcq)
        score_pct = round((correct_count / total * 100) if total > 0 else 0, 1)

        return {
            "total_questions": total,
            "correct_count": correct_count,
            "score_percentage": score_pct,
            "passed": score_pct >= 70,
            "results": results,
        }
