"""Shared rate limiter + per-user daily LLM budget (SEC-3).

Used by both user (auth gateway) and adaptive (AI engine) services.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from user.auth_config import SECRET_KEY, ALGORITHM
from user.dependencies import get_current_user

logger = logging.getLogger(__name__)


def user_key(request: Request) -> str:
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


_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
_storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI", "").strip() or None
_IS_MEMORY_URI = bool(_storage_uri and _storage_uri.startswith("memory://"))
if _storage_uri and (
    _storage_uri.startswith("#") or "://" not in _storage_uri
):
    logger.warning(
        "Ignoring invalid RATE_LIMIT_STORAGE_URI=%r (not a URL) — using in-memory store",
        _storage_uri,
    )
    _storage_uri = None


def validate_rate_limit_config(environment: str, storage_uri) -> None:
    env = (environment or "").strip().lower()
    if env == "production" and not storage_uri:
        raise RuntimeError(
            "RATE_LIMIT_STORAGE_URI is required in production so rate limits are "
            "shared across uvicorn workers and replicas (in-memory limits are "
            "per-process and can be bypassed). Set e.g. "
            "RATE_LIMIT_STORAGE_URI=redis://redis:6379"
        )


def ping_rate_limit_store() -> bool:
    if not _storage_uri:
        return True
    if _IS_MEMORY_URI:
        return True
    try:
        import redis

        client = redis.Redis.from_url(_storage_uri, socket_connect_timeout=2)
        client.ping()
        logger.info("Rate-limit store reachable: %s", _storage_uri)
        return True
    except Exception as e:
        logger.error("Rate-limit store unreachable (%s): %s", _storage_uri, e)
        return False


validate_rate_limit_config(_ENVIRONMENT, _storage_uri)

_LIMITS_ENABLED = _ENVIRONMENT == "production" or os.getenv("RATE_LIMIT_DISABLED") != "1"
limiter = Limiter(
    enabled=_LIMITS_ENABLED,
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "120/minute")],
    storage_uri=_storage_uri,
)

LLM_DAILY_REQUEST_CAP = int(os.getenv("LLM_DAILY_REQUEST_CAP", "300"))


async def check_llm_budget(current_user: dict = Depends(get_current_user)):
    from pymongo import ReturnDocument
    from user.database import llm_usage_collection

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