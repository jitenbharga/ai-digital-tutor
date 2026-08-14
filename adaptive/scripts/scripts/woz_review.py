"""
P0.2 — Wizard-of-Oz Review Queue

Concierge test: AI generates content, a human reviews/corrects before
it reaches the student. Measures the true defect rate of the LLM
teaching layer.

Usage:
  python scripts/woz_review.py [--limit 20]

Reads recent AI-generated content from MongoDB (questions, explanations,
feedback) and presents each item for human review.

Tracks:
  - Total items reviewed
  - Items flagged as defective (bad question, wrong answer, weak feedback)
  - Defect categories
  - Overall defect rate

Results saved to `woz_review_results` collection + JSON file.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("woz_review")

DEFECT_CATEGORIES = [
    "bad_question",       # Question is unclear, ambiguous, or nonsensical
    "wrong_answer",       # Correct answer is actually wrong
    "weak_feedback",      # Feedback is generic, unhelpful, or misleading
    "wrong_difficulty",   # Difficulty label doesn't match actual difficulty
    "offtopic",           # Content doesn't match the stated topic
    "factual_error",      # Contains a factual mistake
    "formatting",         # Poor formatting, broken math, etc.
    "other",              # Catch-all
]


async def load_review_items(limit: int):
    """Load recent AI-generated items from MongoDB for review."""
    from database import interactions_collection, questions_collection

    items = []

    # Load recent interactions (questions + evaluations)
    cursor = interactions_collection.find(
        {},
        {"_id": 0, "student_id": 1, "skill_id": 1, "correct": 1,
         "timestamp": 1, "question": 1, "student_answer": 1,
         "correct_answer": 1, "feedback": 1, "difficulty": 1}
    ).sort("timestamp", -1).limit(limit)

    async for doc in cursor:
        items.append({
            "source": "interaction",
            "student_id": doc.get("student_id", "?"),
            "topic": doc.get("skill_id", "?"),
            "question": doc.get("question", "(no question recorded)"),
            "correct_answer": doc.get("correct_answer", "(no answer recorded)"),
            "student_answer": doc.get("student_answer", ""),
            "feedback": doc.get("feedback", ""),
            "difficulty": doc.get("difficulty", "?"),
            "was_correct": doc.get("correct", None),
            "timestamp": str(doc.get("timestamp", "")),
        })

    if not items:
        logger.info("No interactions found. Trying questions collection...")
        cursor = questions_collection.find({}).sort("_id", -1).limit(limit)
        async for doc in cursor:
            items.append({
                "source": "question_bank",
                "topic": doc.get("topic", "?"),
                "question": doc.get("question", ""),
                "correct_answer": doc.get("correct_answer", ""),
                "difficulty": doc.get("difficulty", "?"),
                "timestamp": "",
            })

    return items


def review_item(item: dict, index: int, total: int) -> dict:
    """Present one item for human review."""
    print(f"\n{'='*60}")
    print(f"  Item {index+1}/{total} — {item.get('source', '?')}")
    print(f"{'='*60}")
    print(f"  Topic:      {item.get('topic', '?')}")
    print(f"  Difficulty:  {item.get('difficulty', '?')}")
    print(f"  Question:    {item.get('question', '(none)')}")
    print(f"  Answer Key:  {item.get('correct_answer', '(none)')}")
    if item.get("student_answer"):
        print(f"  Student:     {item['student_answer']}")
        print(f"  Was correct: {item.get('was_correct', '?')}")
    if item.get("feedback"):
        print(f"  Feedback:    {item['feedback']}")
    print()

    verdict = input("  OK? [y/n/s(kip)] ").strip().lower()

    if verdict == "s":
        return {"skipped": True}

    if verdict in ("n", "no"):
        print(f"  Defect categories: {', '.join(DEFECT_CATEGORIES)}")
        cats = input("  Which categories (comma-separated)? ").strip()
        categories = [c.strip() for c in cats.split(",") if c.strip() in DEFECT_CATEGORIES]
        if not categories:
            categories = ["other"]
        notes = input("  Notes (optional): ").strip()
        return {
            "verdict": "defective",
            "categories": categories,
            "notes": notes,
        }

    return {"verdict": "ok"}


async def main():
    parser = argparse.ArgumentParser(description="Wizard-of-Oz Review Queue (P0.2)")
    parser.add_argument("--limit", type=int, default=20, help="Max items to review")
    args = parser.parse_args()

    items = await load_review_items(args.limit)
    if not items:
        print("No items to review. Generate some interactions first.")
        return

    print(f"\nLoaded {len(items)} items for review.\n")

    reviews = []
    defect_counts = Counter()
    total_reviewed = 0
    total_defective = 0

    for i, item in enumerate(items):
        result = review_item(item, i, len(items))
        if result.get("skipped"):
            continue

        total_reviewed += 1
        review_record = {
            "item_index": i,
            "topic": item.get("topic"),
            "source": item.get("source"),
            **result,
        }
        reviews.append(review_record)

        if result.get("verdict") == "defective":
            total_defective += 1
            for cat in result.get("categories", []):
                defect_counts[cat] += 1

        # Allow early exit
        if i < len(items) - 1:
            cont = input("\n  Continue? [y/n] ").strip().lower()
            if cont in ("n", "no"):
                break

    # Summary
    defect_rate = total_defective / max(total_reviewed, 1)
    print(f"\n{'='*60}")
    print(f"  WOZ REVIEW SUMMARY")
    print(f"{'='*60}")
    print(f"  Items reviewed:  {total_reviewed}")
    print(f"  Defective:       {total_defective}")
    print(f"  Defect rate:     {defect_rate:.0%}")
    if defect_counts:
        print(f"  By category:")
        for cat, count in defect_counts.most_common():
            print(f"    {cat}: {count}")
    print(f"{'='*60}\n")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_reviewed": total_reviewed,
        "total_defective": total_defective,
        "defect_rate": round(defect_rate, 4),
        "defect_categories": dict(defect_counts),
        "reviews": reviews,
    }

    # Save
    try:
        from database import db
        await db["woz_review_results"].insert_one(summary)
        logger.info("Results saved to woz_review_results collection")
    except Exception as e:
        logger.warning("Could not save to MongoDB: %s", e)

    filename = f"woz_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info("Results saved to %s", filename)


if __name__ == "__main__":
    asyncio.run(main())
