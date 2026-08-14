from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017/digital_tutor"
db_name = os.getenv("DB_NAME") or "digital_tutor"

client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
db = client[db_name]

users_collection = db["users"]
refresh_tokens_collection = db["refresh_tokens"]
login_attempts_collection = db["login_attempts"]
auth_tokens_collection = db["auth_tokens"]
llm_usage_collection = db["llm_usage_daily"]

INDEX_SPECS = [
    ("users_collection", "username", {"unique": True}),
    ("users_collection", "email", {"unique": True}),
    ("refresh_tokens_collection", "jti", {"unique": True}),
    ("refresh_tokens_collection", "expires_at", {"expireAfterSeconds": 0}),
    ("login_attempts_collection", "username", {"unique": True}),
    ("login_attempts_collection", "expire_at", {"expireAfterSeconds": 0}),
    ("auth_tokens_collection", "token", {"unique": True}),
    ("auth_tokens_collection", "expires_at", {"expireAfterSeconds": 0}),
    ("llm_usage_collection", [("username", 1), ("day", 1)], {"unique": True}),
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