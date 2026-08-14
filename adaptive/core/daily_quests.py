"""
Daily quests engine: generates 1-3 personally-relevant quests each day
based on the student's weak areas (KT mastery). Quests rotate daily
and award bonus XP on completion.
"""
import hashlib
import random
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# XP rewards
# ---------------------------------------------------------------------------
QUEST_XP_EASY = 15
QUEST_XP_MEDIUM = 25
QUEST_XP_HARD = 40

# ---------------------------------------------------------------------------
# Quest templates — each is a callable that takes student state and returns
# a quest dict or None (if precondition not met).
# ---------------------------------------------------------------------------

QUEST_TEMPLATES = [
    {
        "id": "weak_topic_hard",
        "title_fn": lambda t: f"Conquer {t}: beat a hard problem",
        "description_fn": lambda t: f"Answer a hard question in {t} — your weakest area right now.",
        "type": "challenge",
        "difficulty": "hard",
        "xp": QUEST_XP_HARD,
        "target": 1,
        "metric": "correct_hard",
        "needs_weak_topic": True,
    },
    {
        "id": "streak_3",
        "title_fn": lambda t: f"3-in-a-row in {t}",
        "description_fn": lambda t: f"Get 3 correct answers in a row in {t}.",
        "type": "streak",
        "difficulty": "medium",
        "xp": QUEST_XP_MEDIUM,
        "target": 3,
        "metric": "consecutive_correct",
        "needs_weak_topic": True,
    },
    {
        "id": "review_5",
        "title_fn": lambda _: "Review champion",
        "description_fn": lambda _: "Complete 5 review cards today.",
        "type": "review",
        "difficulty": "easy",
        "xp": QUEST_XP_EASY,
        "target": 5,
        "metric": "reviews_done",
        "needs_weak_topic": False,
    },
    {
        "id": "answer_10",
        "title_fn": lambda _: "Knowledge sprint",
        "description_fn": lambda _: "Answer 10 questions across any topics.",
        "type": "practice",
        "difficulty": "medium",
        "xp": QUEST_XP_MEDIUM,
        "target": 10,
        "metric": "answers_done",
        "needs_weak_topic": False,
    },
    {
        "id": "explore_new",
        "title_fn": lambda t: f"Explore {t}",
        "description_fn": lambda t: f"Try a new topic you haven't studied much: {t}.",
        "type": "explore",
        "difficulty": "easy",
        "xp": QUEST_XP_EASY,
        "target": 3,
        "metric": "answers_in_topic",
        "needs_weak_topic": True,
    },
    {
        "id": "perfect_5",
        "title_fn": lambda _: "Perfect five",
        "description_fn": lambda _: "Answer 5 questions correctly without a single mistake.",
        "type": "accuracy",
        "difficulty": "hard",
        "xp": QUEST_XP_HARD,
        "target": 5,
        "metric": "perfect_run",
        "needs_weak_topic": False,
    },
]


def _day_seed(student_id: str, date_str: str) -> int:
    """Deterministic seed so the same student gets the same quests for a given day."""
    raw = f"{student_id}:{date_str}:quests"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


def _find_weak_topics(state: dict, count: int = 3) -> list[str]:
    """Return up to `count` weakest topics from topic_proficiency."""
    prof = state.get("topic_proficiency", {})
    if not prof:
        return []
    sorted_topics = sorted(prof.items(), key=lambda kv: kv[1])
    return [t for t, _ in sorted_topics[:count]]


def generate_daily_quests(
    student_id: str,
    state: dict,
    now: datetime | None = None,
    max_quests: int = 3,
) -> list[dict]:
    """
    Generate 1-3 daily quests for the student based on their weak areas.
    Deterministic per day (same student + same day = same quests).
    """
    now = now or datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    seed = _day_seed(student_id, date_str)
    rng = random.Random(seed)

    weak_topics = _find_weak_topics(state)
    total_questions = state.get("total_questions", 0)

    # Filter templates by preconditions
    eligible = []
    for tmpl in QUEST_TEMPLATES:
        if tmpl["needs_weak_topic"] and not weak_topics:
            continue
        # Don't offer "answer 10" if student has answered < 5 total (too early)
        if tmpl["id"] == "answer_10" and total_questions < 5:
            continue
        # Don't offer "perfect 5" if student has < 10 questions (too early)
        if tmpl["id"] == "perfect_5" and total_questions < 10:
            continue
        eligible.append(tmpl)

    if not eligible:
        return []

    # Pick 1-3 quests without replacement
    num = min(max_quests, len(eligible))
    # Ensure at least 1, adjust by student level
    if total_questions < 20:
        num = min(num, 2)  # newer students get fewer quests

    chosen = rng.sample(eligible, num)

    quests = []
    topic_idx = 0
    for tmpl in chosen:
        # Pick a weak topic for this quest
        if tmpl["needs_weak_topic"] and weak_topics:
            topic = weak_topics[topic_idx % len(weak_topics)]
            topic_idx += 1
        else:
            topic = ""

        quest_id = f"{date_str}_{tmpl['id']}"
        quests.append({
            "quest_id": quest_id,
            "template_id": tmpl["id"],
            "title": tmpl["title_fn"](topic),
            "description": tmpl["description_fn"](topic),
            "type": tmpl["type"],
            "difficulty": tmpl["difficulty"],
            "topic": topic,
            "xp_reward": tmpl["xp"],
            "target": tmpl["target"],
            "metric": tmpl["metric"],
            "progress": 0,
            "completed": False,
            "date": date_str,
        })

    return quests


def check_quest_progress(quest: dict, state: dict, today_stats: dict) -> dict:
    """
    Check and update progress for a single quest based on today's activity.
    Returns updated quest dict.
    """
    metric = quest.get("metric", "")
    target = quest.get("target", 1)
    topic = quest.get("topic", "")

    progress = 0

    if metric == "correct_hard":
        # Count hard correct answers today in this topic
        progress = today_stats.get("hard_correct", {}).get(topic, 0)
    elif metric == "consecutive_correct":
        progress = today_stats.get("consecutive_correct", {}).get(topic, 0)
    elif metric == "reviews_done":
        progress = today_stats.get("reviews_done", 0)
    elif metric == "answers_done":
        progress = today_stats.get("answers_done", 0)
    elif metric == "answers_in_topic":
        progress = today_stats.get("answers_in_topic", {}).get(topic, 0)
    elif metric == "perfect_run":
        progress = today_stats.get("perfect_run", 0)

    quest["progress"] = min(progress, target)
    quest["completed"] = progress >= target

    return quest


def get_today_stats(state: dict) -> dict:
    """
    Extract today's activity stats from student state for quest tracking.
    """
    daily = state.get("daily_progress", {})
    quest_stats = state.get("quest_stats", {})

    return {
        "answers_done": daily.get("answers_done", 0),
        "reviews_done": daily.get("reviews_done", 0),
        "hard_correct": quest_stats.get("hard_correct", {}),
        "consecutive_correct": quest_stats.get("consecutive_correct", {}),
        "answers_in_topic": quest_stats.get("answers_in_topic", {}),
        "perfect_run": quest_stats.get("perfect_run", 0),
    }


def record_quest_activity(
    state: dict,
    event: str,
    topic: str = "",
    difficulty: str = "medium",
    correct: bool = False,
) -> dict:
    """
    Track quest-relevant metrics from an answer/review event.
    Returns updates to merge into state.
    event: "answer" or "review"
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    quest_stats = state.get("quest_stats", {})
    stats_date = quest_stats.get("date", "")

    # Reset on new day
    if stats_date != today:
        quest_stats = {
            "date": today,
            "hard_correct": {},
            "consecutive_correct": {},
            "answers_in_topic": {},
            "perfect_run": 0,
            "current_run": 0,
        }

    if event == "answer" and topic:
        # Track answers in topic
        ait = quest_stats.get("answers_in_topic", {})
        ait[topic] = ait.get(topic, 0) + 1
        quest_stats["answers_in_topic"] = ait

        if correct:
            # Track hard correct
            if difficulty == "hard":
                hc = quest_stats.get("hard_correct", {})
                hc[topic] = hc.get(topic, 0) + 1
                quest_stats["hard_correct"] = hc

            # Track consecutive correct
            cc = quest_stats.get("consecutive_correct", {})
            cc[topic] = cc.get(topic, 0) + 1
            quest_stats["consecutive_correct"] = cc

            # Track perfect run
            quest_stats["current_run"] = quest_stats.get("current_run", 0) + 1
            quest_stats["perfect_run"] = max(
                quest_stats.get("perfect_run", 0),
                quest_stats["current_run"],
            )
        else:
            # Break consecutive streak for this topic
            cc = quest_stats.get("consecutive_correct", {})
            cc[topic] = 0
            quest_stats["consecutive_correct"] = cc

            # Break perfect run
            quest_stats["current_run"] = 0

    return {"quest_stats": quest_stats}
