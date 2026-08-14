"""
Token issuance / rotation business logic.

Composes the pure JWT helpers (security.py) with the RefreshTokenRepository so
the access+refresh lifecycle lives in one place instead of being duplicated
across the login and refresh route handlers.
"""
from typing import Tuple

from security import (
    create_access_token, create_refresh_token, REFRESH_TOKEN_EXPIRE_DAYS,
)
from repositories.refresh_tokens import RefreshTokenRepository


class TokenService:
    @staticmethod
    async def issue_token_pair(username: str, role: str) -> Tuple[str, str]:
        """Mint an access token + a persisted (revocable) refresh token.
        Returns ``(access_token, refresh_token)``."""
        access = create_access_token({"sub": username, "role": role})
        refresh, jti = create_refresh_token({"sub": username, "role": role})
        await RefreshTokenRepository.store(jti, username, REFRESH_TOKEN_EXPIRE_DAYS)
        return access, refresh

    @staticmethod
    async def rotate_refresh(old_jti: str, username: str, role: str) -> Tuple[str, str]:
        """Issue a fresh access+refresh pair and revoke the old refresh jti.
        A stolen old token becomes useless after the next legitimate refresh."""
        access = create_access_token({"sub": username, "role": role})
        new_refresh, new_jti = create_refresh_token({"sub": username, "role": role})
        await RefreshTokenRepository.store(new_jti, username, REFRESH_TOKEN_EXPIRE_DAYS)
        await RefreshTokenRepository.revoke(old_jti)
        return access, new_refresh
