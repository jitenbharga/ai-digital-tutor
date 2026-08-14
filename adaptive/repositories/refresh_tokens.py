"""Refresh-token persistence (rotation + revocation). Wraps ``refresh_tokens``."""
from datetime import datetime, timedelta, timezone
from typing import Optional


def _col():
    import database
    return database.refresh_tokens_collection


class RefreshTokenRepository:
    @staticmethod
    async def store(jti: str, username: str, ttl_days: int) -> None:
        now = datetime.now(timezone.utc)
        await _col().insert_one(
            {
                "jti": jti,
                "username": username,
                "created_at": now,
                "expires_at": now + timedelta(days=ttl_days),
                "revoked": False,
            }
        )

    @staticmethod
    async def get(jti: str) -> Optional[dict]:
        return await _col().find_one({"jti": jti})

    @staticmethod
    async def revoke(jti: str) -> None:
        await _col().update_one(
            {"jti": jti, "revoked": False}, {"$set": {"revoked": True}}
        )

    @staticmethod
    async def revoke_family(username: str) -> None:
        """Revoke every active refresh token for a user (reuse-detection response)."""
        await _col().update_many(
            {"username": username, "revoked": False}, {"$set": {"revoked": True}}
        )
