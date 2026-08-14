import os
import logging
from datetime import datetime, timedelta, timezone

from user.database import login_attempts_collection

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))


async def assert_login_allowed(identifier: str):
    doc = await login_attempts_collection.find_one({"username": identifier})
    if doc and doc.get("failures", 0) >= MAX_ATTEMPTS:
        expire_at = doc.get("expire_at")
        if expire_at and expire_at > datetime.now(timezone.utc):
            raise HTTPException(
                429,
                f"Too many failed attempts. Try again after {expire_at.strftime('%H:%M UTC')}."
            )
        else:
            await login_attempts_collection.delete_one({"username": identifier})


async def record_login_failure(identifier: str):
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    await login_attempts_collection.update_one(
        {"username": identifier},
        {"$inc": {"failures": 1}, "$set": {"expire_at": expire_at}},
        upsert=True,
    )


async def clear_login_failures(identifier: str):
    await login_attempts_collection.delete_one({"username": identifier})


from fastapi import HTTPException