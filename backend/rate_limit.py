"""Shared rate limiter + per-user daily LLM budget (SEC-3).

Extracted into its own module so BOTH serve.py and the extras router can share
the *same* Limiter instance — the one registered as ``app.state.limiter`` and
evaluated by ``SlowAPIMiddleware`` — without importing serve.py (which would be
a circular import, since serve.py imports the routers).

Per-route LLM/upload limits are keyed by the authenticated username via
``user_key`` so one user can't exhaust another's (or a shared IP's) budget.
The limiter's *default* key remains the client IP, preserving existing global
behaviour for undecorated routes.
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth_config import SECRET_KEY, ALGORITHM
from dependencies import get_current_user

logger = logging.getLogger(__name__)


def user_key(request: Request) -> str:
    """Rate-limit key = authenticated username if a valid bearer token is
    present, otherwise the client IP. Used per-route for cost-bearing
    endpoints so limits are enforced per user (SEC-3)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return get_remote_address(request)


# SEC H-4: with multiple uvicorn workers/replicas the default in-memory store is
# per-process, so a global limit of "5/min" becomes "5/min * N processes" and is
# effectively bypassable. A shared store (Redis) fixes this.
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip() or None
# Guard against placeholder/comment leaks in .env (e.g. a line like
# `RATE_LIMIT_STORAGE_URI=# e.g. redis://...`) or a value with no URL scheme —
# slowapi/limits would raise ConfigurationError and crash boot. Fall back to the
# in-memory store instead of dying.
if _storage_uri and (_storage_uri.startswith("#") or "://" not in _storage_uri):
    logger.warning(
        "Ignoring invalid RATE_LIMIT_STORAGE_URI=%r (not a URL) — using in-memory store",
        _storage_uri,
    )
    _storage_uri = None


def validate_rate_limit_config(environment: str, storage_uri) -> None:
    """Fail closed when a production deployment would silently fall back to
    per-process in-memory rate limiting. Pure + unit-testable.

    Production runs multi-worker (Dockerfile: ``--workers $(nproc)``) and usually
    multi-replica, so a shared store is mandatory there. Dev/test may use the
    in-memory store (single process) without weakening anything real.
    """
    env = (environment or "").strip().lower()
    if env == "production" and not storage_uri:
        raise RuntimeError(
            "RATE_LIMIT_STORAGE_URI is required in production so rate limits are "
            "shared across uvicorn workers and replicas (in-memory limits are "
            "per-process and can be bypassed). Set e.g. "
            "RATE_LIMIT_STORAGE_URI=redis://redis:6379"
        )


def ping_rate_limit_store() -> bool:
    """Best-effort connectivity check for the shared rate-limit store. Returns
    True if reachable (or if using the in-memory store); False if a configured
    Redis is unreachable. Never raises — callers decide what to do."""
    if not _storage_uri:
        return True
    try:
        import redis

        client = redis.Redis.from_url(_storage_uri, socket_connect_timeout=2)
        client.ping()
        logger.info("Rate-limit store reachable: %s", _storage_uri)
        return True
    except Exception as e:  # noqa: BLE001 — connectivity probe, must not crash boot
        logger.error("Rate-limit store unreachable (%s): %s", _storage_uri, e)
        return False


validate_rate_limit_config(_ENVIRONMENT, _storage_uri)

# Single shared limiter. Default key = IP (unchanged global behaviour);
# cost-bearing routes override key_func=user_key at the decorator.
# E2E/local runs may set RATE_LIMIT_DISABLED=1 so a suite that signs up + logs in
# many times from one IP isn't throttled (login/signup are 5/minute per IP).
# Production ALWAYS keeps limits on — the flag is ignored there.
_LIMITS_ENABLED = _ENVIRONMENT == "production" or os.getenv("RATE_LIMIT_DISABLED") != "1"
limiter = Limiter(
    enabled=_LIMITS_ENABLED,
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120/minute")],
    storage_uri=_storage_uri,
)

# Per-user daily LLM request cap.
LLM_DAILY_REQUEST_CAP = int(os.getenv("LLM_DAILY_REQUEST_CAP", "300"))


async def check_llm_budget(current_user: dict = Depends(get_current_user)):
    """Count LLM-endpoint requests per user per UTC day; 429 over cap.

    SEC: this is a *cost-bearing* gate, so it is both atomic and fail-closed:

    * Atomic — a single ``find_one_and_update`` increments and returns the new
      count, so concurrent requests can't race past the cap (the previous
      inc-then-read pattern could double-count/undercount under load).
    * Fail-closed — if the counter store is unreachable we return 503 rather
      than silently allowing unlimited paid LLM calls. (The app already depends
      on Mongo for auth, so a Mongo outage is not a scenario we keep serving
      expensive LLM traffic through.)
    """
    from pymongo import ReturnDocument
    from database import llm_usage_collection

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    username = (
        current_user.get("username", "anon")
        if isinstance(current_user, dict)
        else str(current_user)
    )
    try:
        doc = await llm_usage_collection.find_one_and_update(
            {"username": username, "day": day},
            {"$inc": {"count": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except Exception as e:
        logger.error("LLM budget store unavailable (failing closed): %s", e)
        raise HTTPException(
            503, "AI service temporarily unavailable. Please try again shortly."
        )

    if (doc or {}).get("count", 0) > LLM_DAILY_REQUEST_CAP:
        raise HTTPException(
            429,
            "Daily AI usage limit reached — great work today! Come back tomorrow.",
        )
    return current_user
