import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from database import auth_tokens_collection

logger = logging.getLogger(__name__)

PURPOSE_VERIFY = "verify_email"
PURPOSE_RESET = "reset_password"

VERIFY_TOKEN_TTL_SECONDS = int(os.getenv("VERIFY_TOKEN_TTL_SECONDS", "86400"))
RESET_TOKEN_TTL_SECONDS = int(os.getenv("RESET_TOKEN_TTL_SECONDS", "3600"))


async def create_token(username: str, purpose: str, ttl_seconds: int) -> str:
    import secrets
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    await auth_tokens_collection.insert_one({
        "token": token,
        "username": username,
        "purpose": purpose,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
    })
    return token


async def consume_token(token: str, purpose: str) -> Optional[str]:
    doc = await auth_tokens_collection.find_one_and_delete({
        "token": token,
        "purpose": purpose,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    return doc["username"] if doc else None