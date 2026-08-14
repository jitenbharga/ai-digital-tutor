"""
SEC L-11: Mongo-backed failed-login backoff.

In-memory counters would be per-worker (bypassable, like the pre-H-4 rate limits),
so lockout state lives in Mongo and is shared across workers/replicas. Failures are
recorded for *any* submitted username (valid or not), so lockout timing leaks no
signal about which usernames exist.

Tunables (env):
  LOGIN_MAX_FAILURES     default 5   — failures before lockout
  LOGIN_LOCKOUT_SECONDS  default 900 — lockout duration (15 min)
  LOGIN_WINDOW_SECONDS   default 900 — inactivity window before counters reset
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument

LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def assert_login_allowed(username: str) -> None:
    """Raise 429 (with Retry-After) if this username is currently locked out."""
    from user.database import login_attempts_collection

    doc = await login_attempts_collection.find_one({"username": username})
    if not doc:
        return
    locked_until = doc.get("locked_until")
    if locked_until:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        now = _now()
        if locked_until > now:
            retry = max(1, int((locked_until - now).total_seconds()))
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Please try again later.",
                headers={"Retry-After": str(retry)},
            )


async def record_login_failure(username: str) -> None:
    """Atomically increment the failure counter; lock the account past the
    threshold. The doc auto-expires after the lockout/window via a TTL index."""
    from user.database import login_attempts_collection

    now = _now()
    expire_at = now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS + LOGIN_WINDOW_SECONDS)
    doc = await login_attempts_collection.find_one_and_update(
        {"username": username},
        {
            "$inc": {"count": 1},
            "$set": {"last_failed": now, "expire_at": expire_at},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if doc.get("count", 0) >= LOGIN_MAX_FAILURES:
        await login_attempts_collection.update_one(
            {"username": username},
            {"$set": {"locked_until": now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)}},
        )


async def clear_login_failures(username: str) -> None:
    """Reset counters after a successful login."""
    from user.database import login_attempts_collection

    await login_attempts_collection.delete_one({"username": username})