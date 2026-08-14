from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGODB_URI")
db_name = os.getenv("DB_NAME")

if not uri or not db_name:
    raise ValueError("MONGODB_URI and DB_NAME must be set in environment")

client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
db = client[db_name]

users_collection = db["users"]
students_col = db["students"]
student_states_collection = db["student_states"]
questions_collection = db["questions"]
rl_transitions_collection = db["rl_transitions"]
llm_calls_collection = db["llm_calls"]
interactions_collection = db["interactions"]
guardian_invites_collection = db["guardian_invites"]
buddy_invites_collection = db["buddy_invites"]
retention_collection = db["retention"]
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
notes_collection = db["notes"]
content_stats_collection = db["content_stats"]
content_reports_collection = db["content_reports"]
flashcards_collection = db["flashcards"]
exam_plans_collection = db["exam_plans"]
notifications_collection = db["notifications"]
cheatsheets_collection = db["cheatsheets"]
user_materials_collection = db["user_materials"]
feynman_attempts_collection = db["feynman_attempts"]
login_attempts_collection = db["login_attempts"]
auth_tokens_collection = db["auth_tokens"]

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


async def _drop_indexes_for_keys(coll, keys) -> None:
    pattern = {keys: 1} if isinstance(keys, str) else dict(keys)
    names = [
        idx["name"]
        async for idx in coll.list_indexes()
        if idx.get("key") == pattern
    ]
    for name in names:
        await coll.drop_index(name)


async def ensure_indexes(raise_on_error: bool = False) -> dict:
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
            err_msg = str(e)
            if "IndexKeySpecsConflict" in err_msg or "IndexOptionsConflict" in err_msg or "same name" in err_msg or "already exists with different options" in err_msg:
                try:
                    coll = getattr(mod, var)
                    await _drop_indexes_for_keys(coll, keys)
                    await coll.create_index(keys, **opts)
                    created += 1
                    continue
                except Exception as drop_err:
                    log.error("Failed to drop and recreate conflicting index on %s: %s", var, drop_err)
            failed += 1
            log.error("Index creation FAILED on %s keys=%s: %s", var, keys, e)
            if raise_on_error:
                raise
    (log.info if failed == 0 else log.error)(
        "MongoDB indexes: %d ensured, %d failed", created, failed
    )
    return {"created": created, "failed": failed}