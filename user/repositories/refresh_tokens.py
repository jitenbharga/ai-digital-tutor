from user.database import refresh_tokens_collection
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class RefreshTokenRepository:
    @staticmethod
    async def get(jti: str):
        return await refresh_tokens_collection.find_one({"jti": jti})

    @staticmethod
    async def create(username: str, jti: str, expires_at: datetime):
        await refresh_tokens_collection.insert_one({
            "jti": jti,
            "username": username,
            "revoked": False,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        })

    @staticmethod
    async def revoke(jti: str):
        await refresh_tokens_collection.update_one(
            {"jti": jti}, {"$set": {"revoked": True}}
        )

    @staticmethod
    async def revoke_family(username: str):
        await refresh_tokens_collection.update_many(
            {"username": username}, {"$set": {"revoked": True}}
        )

    @staticmethod
    async def rotate(old_jti: str, username: str, new_jti: str, new_expires_at: datetime):
        await RefreshTokenRepository.revoke(old_jti)
        await RefreshTokenRepository.create(username, new_jti, new_expires_at)