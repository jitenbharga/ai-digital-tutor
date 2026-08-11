"""
P0.1 — Pre/Post Learning Test Harness

Minimal experiment script to measure whether the tutor actually teaches.

Usage:
  python scripts/prepost_test.py --student <username> --topic <topic> [--num-questions 5]

Flow:
  1. Pre-test: generate N questions at mixed difficulty, record baseline score.
  2. (Manual) Student uses the tutor for learning sessions.
  3. Post-test: generate N matched questions, record post score.
  4. Compute normalized learning gain.

Results are logged to MongoDB collection `experiment_results`.
"""

import argparse
import asyncio
import json
import logging
import sys
import os
from datetime import datetime, timezone

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("prepost_test")


async def generate_test_questions(generator, topic: str, num: int, difficulty: str = "mixed"):
    """Generate a set of test questions via the question generator."""
    questions = []
    difficulties = ["easy", "medium", "hard"] if difficulty == "mixed" else [difficulty]
    for i in range(num):
        diff = difficulties[i % len(difficulties)]
        try:
            q = await generator.generate_question(
                explanation=f"Test question on {topic}",
                topic=topic,
                difficulty=diff,
            )
            if q and isinstance(q, dict):
                q["test_difficulty"] = diff
                q["test_index"] = i
                questions.append(q)
            else:
                logger.warning("Failed to generate question %d", i)
        except Exception as e:
            logger.warning("Error generating question %d: %s", i, e)
    return questions


async def administer_test(evaluator, questions: list, topic: str):
    """Interactively administer test questions and score answers."""
    results = []
    total_correct = 0

    print(f"\n{'='*60}")
    print(f"  TEST: {topic} ({len(questions)} questions)")
    print(f"{'='*60}\n")

    for i, q in enumerate(questions):
        question_text = q.get("question", "No question generated")
        print(f"Q{i+1}. [{q.get('test_difficulty', '?')}] {question_text}")
        if q.get("options"):
            for j, opt in enumerate(q["options"]):
                print(f"   {chr(65+j)}) {opt}")
        print()

        answer = input("Your answer: ").strip()
        if not answer:
            answer = "(no answer)"

        # Evaluate
        try:
            eval_result = await evaluator.evaluate(
                question=question_text,
                student_answer=answer,
                topic=topic,
                correct_answer=q.get("correct_answer", ""),
            )
            correct = eval_result.get("is_correct", False)
        except Exception as e:
            logger.warning("Evaluation error: %s", e)
            correct = False
            eval_result = {"error": str(e)}

        if correct:
            total_correct += 1
            print("  -> Correct!\n")
        else:
            print(f"  -> Incorrect. Expected: {q.get('correct_answer', 'N/A')}\n")

        results.append({
            "question_index": i,
            "question": question_text,
            "difficulty": q.get("test_difficulty"),
            "student_answer": answer,
            "correct_answer": q.get("correct_answer", ""),
            "is_correct": correct,
        })

    score = total_correct / max(len(questions), 1)
    print(f"\nScore: {total_correct}/{len(questions)} = {score:.0%}\n")
    return results, score


def compute_learning_gain(pre_score: float, post_score: float) -> dict:
    """Compute normalized learning gain (Hake)."""
    if pre_score >= 1.0:
        normalized = 0.0  # ceiling effect
    else:
        normalized = (post_score - pre_score) / (1.0 - pre_score)

    return {
        "pre_score": round(pre_score, 4),
        "post_score": round(post_score, 4),
        "raw_gain": round(post_score - pre_score, 4),
        "normalized_gain": round(normalized, 4),
        "interpretation": (
            "high" if normalized >= 0.7 else
            "medium" if normalized >= 0.3 else
            "low" if normalized > 0 else
            "negative/zero"
        ),
    }


async def run_pretest(student_id: str, topic: str, num_questions: int):
    """Run the pre-test phase."""
    from core.question_generator import QuestionGenerator
    from core.answer_evaluator import LLMAnswerEvaluator

    generator = QuestionGenerator()
    evaluator = LLMAnswerEvaluator()

    logger.info("Generating %d pre-test questions for %s on %s", num_questions, student_id, topic)
    questions = await generate_test_questions(generator, topic, num_questions)

    if not questions:
        logger.error("No questions generated. Check LLM configuration.")
        return None

    results, score = await administer_test(evaluator, questions, topic)

    record = {
        "student_id": student_id,
        "topic": topic,
        "phase": "pre",
        "score": score,
        "num_questions": len(questions),
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Save to MongoDB
    try:
        from database import db
        await db["experiment_results"].insert_one(record)
        logger.info("Pre-test saved to experiment_results collection")
    except Exception as e:
        logger.warning("Could not save to MongoDB: %s", e)

    # Also save to file
    filename = f"prepost_{student_id}_{topic}_pre.json"
    with open(filename, "w") as f:
        json.dump(record, f, indent=2, default=str)
    logger.info("Pre-test results saved to %s", filename)

    return record


async def run_posttest(student_id: str, topic: str, num_questions: int):
    """Run the post-test phase and compute learning gain."""
    from core.question_generator import QuestionGenerator
    from core.answer_evaluator import LLMAnswerEvaluator

    generator = QuestionGenerator()
    evaluator = LLMAnswerEvaluator()

    # Load pre-test results
    pre_record = None
    try:
        from database import db
        pre_record = await db["experiment_results"].find_one(
            {"student_id": student_id, "topic": topic, "phase": "pre"},
            sort=[("timestamp", -1)],
        )
    except Exception:
        pass

    if not pre_record:
        filename = f"prepost_{student_id}_{topic}_pre.json"
        if os.path.exists(filename):
            with open(filename) as f:
                pre_record = json.load(f)

    if not pre_record:
        logger.error("No pre-test found for %s on %s. Run pre-test first.", student_id, topic)
        return None

    pre_score = pre_record["score"]
    logger.info("Pre-test score: %.0f%%. Now running post-test...", pre_score * 100)

    questions = await generate_test_questions(generator, topic, num_questions)
    if not questions:
        logger.error("No questions generated.")
        return None

    results, post_score = await administer_test(evaluator, questions, topic)
    gain = compute_learning_gain(pre_score, post_score)

    record = {
        "student_id": student_id,
        "topic": topic,
        "phase": "post",
        "score": post_score,
        "num_questions": len(questions),
        "results": results,
        "learning_gain": gain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Print summary
    print(f"\n{'='*60}")
    print(f"  LEARNING GAIN REPORT: {student_id} / {topic}")
    print(f"{'='*60}")
    print(f"  Pre-test score:      {gain['pre_score']:.0%}")
    print(f"  Post-test score:     {gain['post_score']:.0%}")
    print(f"  Raw gain:            {gain['raw_gain']:+.0%}")
    print(f"  Normalized gain:     {gain['normalized_gain']:.2f} ({gain['interpretation']})")
    print(f"{'='*60}\n")

    # Save
    try:
        from database import db
        await db["experiment_results"].insert_one(record)
        logger.info("Post-test saved to experiment_results collection")
    except Exception as e:
        logger.warning("Could not save to MongoDB: %s", e)

    filename = f"prepost_{student_id}_{topic}_post.json"
    with open(filename, "w") as f:
        json.dump(record, f, indent=2, default=str)
    logger.info("Post-test results saved to %s", filename)

    return record


async def main():
    parser = argparse.ArgumentParser(description="Pre/Post Learning Test Harness (P0.1)")
    parser.add_argument("--student", required=True, help="Student username")
    parser.add_argument("--topic", required=True, help="Topic to test")
    parser.add_argument("--num-questions", type=int, default=5, help="Questions per test")
    parser.add_argument("--phase", choices=["pre", "post", "both"], default="pre",
                        help="Which phase to run")
    args = parser.parse_args()

    if args.phase in ("pre", "both"):
        await run_pretest(args.student, args.topic, args.num_questions)

    if args.phase == "both":
        print("\n[Now use the tutor for learning sessions, then run with --phase post]\n")

    if args.phase == "post":
        await run_posttest(args.student, args.topic, args.num_questions)


if __name__ == "__main__":
    asyncio.run(main())
