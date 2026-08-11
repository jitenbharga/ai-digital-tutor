from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGODB_URI")
db_name = os.getenv("DB_NAME")

if not uri or not db_name:
    raise ValueError("MONGODB_URI and DB_NAME must be set in environment")

client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

# Connection test moved to FastAPI startup event (serve.py)
# Motor is async — cannot call server_info() synchronously at module level
db = client[db_name]

users_collection = db["users"]
students_col = db["students"]
student_states_collection = db["student_states"]
questions_collection = db["questions"]
rl_transitions_collection = db["rl_transitions"]
llm_calls_collection = db["llm_calls"]
interactions_collection = db["interactions"]
guardian_invites_collection = db["guardian_invites"]
buddy_invites_collection = db["buddy_invites"]      # study-buddy pairing codes
retention_collection = db["retention"]              # per-student active_days (shared streak)
refresh_tokens_collection = db["refresh_tokens"]
mentor_memory_collection = db["mentor_memory"]
onboarding_sessions_collection = db["onboarding_sessions"]
learning_paths_collection = db["learning_paths"]
certificates_collection = db["certificates"]
daily_goals_collection = db["daily_goals"]
daily_quests_collection = db["daily_quests"]
ask_sessions_collection = db["ask_sessions"]
curricula_collection = db["curricula"]
curriculum_progress_collection = db["curriculum_progress"]
quiz_history_collection = db["quiz_history"]
mistakes_collection = db["mistakes"]
projects_collection = db["projects"]
chat_sessions_collection = db["chat_sessions"]
active_quizzes_collection = db["active_quizzes"]
llm_usage_collection = db["llm_usage_daily"]
notes_collection = db["notes"]  # N12 personal notebook (used by serve.py)
content_stats_collection = db["content_stats"]      # B2: per concept/difficulty outcome aggregates
content_reports_collection = db["content_reports"]  # B2: student-flagged bad questions
flashcards_collection = db["flashcards"]            # B3: FSRS-scheduled cards from mistakes + notes
exam_plans_collection = db["exam_plans"]            # B4: exam-date back-planned schedules
digest_log_collection = db["digest_log"]            # B6: guardian weekly digest dedup log
notifications_collection = db["notifications"]       # C3: student re-engagement nudges
cheatsheets_collection = db["cheatsheets"]           # D2/S3: cached smart cheat sheets
user_materials_collection = db["user_materials"]    # S1: uploaded textbook chapters (chunks stored inline)
feynman_attempts_collection = db["feynman_attempts"]  # S2: explain-back grading history
login_attempts_collection = db["login_attempts"]     # L-11: failed-login backoff (Mongo-backed)
auth_tokens_collection = db["auth_tokens"]           # W3: password-reset + email-verify tokens


# ── W5: declarative index registry ──────────────────────────────────────────
# (collection_attr, keys, options). Keys is a field name or a list of (field,dir)
# tuples. This is the single source of truth for indexes, applied by both startup
# and scripts/migrate_indexes.py. TTL indexes require a BSON *date* field (the
# refresh/login/auth token collections use datetimes); the append-heavy telemetry
# collections store float epochs, so they're pruned by scripts/telemetry_maintenance.py
# instead of via a (no-op-on-floats) TTL index.
INDEX_SPECS = [
    ("users_collection", "username", {"unique": True}),
    ("curriculum_progress_collection", [("user_id", 1), ("subject_id", 1)], {}),
    ("mistakes_collection", [("student_id", 1), ("timestamp", -1)], {}),
    ("quiz_history_collection", [("student_id", 1), ("taken_at", -1)], {}),
    ("notes_collection", [("student_id", 1), ("created_at", -1)], {}),
    ("mentor_memory_collection", "student_id", {}),
    ("refresh_tokens_collection", "jti", {"unique": True}),
    ("refresh_tokens_collection", "expires_at", {"expireAfterSeconds": 0}),
    ("chat_sessions_collection", [("student_id", 1), ("topic", 1)], {}),
    ("chat_sessions_collection", "chat_id", {}),
    ("chat_sessions_collection", [("student_id", 1), ("updated_at", -1)], {}),
    ("buddy_invites_collection", "code", {"unique": True}),
    ("student_states_collection", "student_id", {}),
    ("ask_sessions_collection", "student_id", {}),
    ("active_quizzes_collection", "quiz_id", {"unique": True}),
    ("active_quizzes_collection", "created_at", {"expireAfterSeconds": 86400}),
    ("llm_usage_collection", [("username", 1), ("day", 1)], {"unique": True}),
    ("content_stats_collection", [("topic", 1), ("concept", 1), ("difficulty", 1)], {"unique": True}),
    ("content_reports_collection", [("topic", 1), ("created_at", -1)], {}),
    ("flashcards_collection", [("student_id", 1), ("due_ts", 1)], {}),
    ("flashcards_collection", [("student_id", 1), ("source_id", 1)], {"unique": True}),
    ("exam_plans_collection", [("student_id", 1), ("subject_id", 1)], {"unique": True}),
    ("digest_log_collection", [("guardian", 1), ("week", 1)], {"unique": True}),
    ("notifications_collection", [("student_id", 1), ("created_at", -1)], {}),
    ("notifications_collection", [("student_id", 1), ("dedup_key", 1)], {"unique": True}),
    ("cheatsheets_collection", [("student_id", 1), ("topic_key", 1)], {"unique": True}),
    ("user_materials_collection", [("student_id", 1), ("created_at", -1)], {}),
    ("feynman_attempts_collection", [("student_id", 1), ("created_at", -1)], {}),
    ("login_attempts_collection", "username", {"unique": True}),
    ("login_attempts_collection", "expire_at", {"expireAfterSeconds": 0}),
    ("auth_tokens_collection", "token", {"unique": True}),
    ("auth_tokens_collection", "expires_at", {"expireAfterSeconds": 0}),
]


async def ensure_indexes(raise_on_error: bool = False) -> dict:
    """Apply INDEX_SPECS idempotently.

    W5: replaces the old single try/except that swallowed *all* index errors as
    one warning (a failed index silently degraded queries at scale). Each index
    now succeeds or fails independently and logs at ERROR. The migration script
    passes ``raise_on_error=True`` so a broken index fails the deploy loudly;
    startup keeps the default so the app still boots in degraded mode.
    """
    import sys
    import logging
    log = logging.getLogger(__name__)
    mod = sys.modules[__name__]
    created = failed = 0
    for var, keys, opts in INDEX_SPECS:
        try:
            coll = getattr(mod, var)
            await coll.create_index(keys, **opts)
            created += 1
        except Exception as e:
            failed += 1
            log.error("Index creation FAILED on %s keys=%s: %s", var, keys, e)
            if raise_on_error:
                raise
    (log.info if failed == 0 else log.error)(
        "MongoDB indexes: %d ensured, %d failed", created, failed
    )
    return {"created": created, "failed": failed}
