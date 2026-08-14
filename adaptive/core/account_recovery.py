"""
W3: single-use, TTL'd tokens for password reset and email verification.

Tokens are random (secrets.token_urlsafe), stored hashed-by-uniqueness in Mongo
with a TTL index, and consumed atomically (find_one_and_delete) so a token can
never be replayed.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

RESET_TOKEN_TTL_SECONDS = int(os.getenv("RESET_TOKEN_TTL_SECONDS", "3600"))       # 1h
VERIFY_TOKEN_TTL_SECONDS = int(os.getenv("VERIFY_TOKEN_TTL_SECONDS", "86400"))    # 24h

PURPOSE_RESET = "password_reset"
PURPOSE_VERIFY = "email_verify"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_token(username: str, purpose: str, ttl_seconds: int) -> str:
    from database import auth_tokens_collection

    token = secrets.token_urlsafe(32)
    await auth_tokens_collection.insert_one(
        {
            "token": token,
            "username": username,
            "purpose": purpose,
            "created_at": _now(),
            "expires_at": _now() + timedelta(seconds=ttl_seconds),
        }
    )
    return token


async def consume_token(token: str, purpose: str) -> Optional[str]:
    """Atomically validate + consume a token. Returns the username, or None if the
    token is missing, wrong-purpose, or expired (defends against a TTL GC lag)."""
    from database import auth_tokens_collection

    if not token:
        return None
    doc = await auth_tokens_collection.find_one_and_delete(
        {"token": token, "purpose": purpose}
    )
    if not doc:
        return None
    exp = doc.get("expires_at")
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < _now():
            return None
    return doc.get("username")
