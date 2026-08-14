from datetime import datetime, timedelta, timezone
from user.repositories.refresh_tokens import RefreshTokenRepository
from user.security import create_access_token, create_refresh_token
from user.auth_config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
import logging

logger = logging.getLogger(__name__)


class TokenService:
    @staticmethod
    async def issue_token_pair(username: str, role: str):
        access_token = create_access_token(
            {"sub": username, "role": role},
            ACCESS_TOKEN_EXPIRE_MINUTES
        )
        refresh_token = create_refresh_token(
            {"sub": username, "role": role},
            REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        expires_at = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
        await RefreshTokenRepository.create(username, jti, expires_at)
        return access_token, refresh_token

    @staticmethod
    async def rotate_refresh(old_jti: str, username: str, role: str):
        await RefreshTokenRepository.revoke(old_jti)
        return await TokenService.issue_token_pair(username, role)


def decode_token(token: str) -> dict:
    import jwt
    from user.auth_config import SECRET_KEY, ALGORITHM
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])