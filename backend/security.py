import jwt
from jwt import PyJWTError as JWTError
from datetime import datetime, timedelta, timezone
import uuid

from auth_config import (
    SECRET_KEY, ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
)

try:
    from pwdlib import PasswordHash
    pwd_context = PasswordHash.recommended()

    def hash_password(password: str):
        return pwd_context.hash(password)

    def verify_password(password: str, hashed: str):
        return pwd_context.verify(password, hashed)
except ImportError:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(password: str):
        return pwd_context.hash(password)

    def verify_password(password: str, hashed: str):
        return pwd_context.verify(password, hashed)


def create_access_token(data: dict) -> str:
    """Short-lived access token (15 min) with jti and iat claims."""
    now = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode.update({
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": "access",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> tuple[str, str]:
    """Longer-lived refresh token (7 days). Returns (encoded_token, jti)."""
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    to_encode = data.copy()
    to_encode.update({
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": now,
        "jti": jti,
        "type": "refresh",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), jti


def create_stream_token(username: str, ttl_seconds: int = 60) -> str:
    """SEC: very short-lived (60s), single-purpose token for EventSource/download
    URLs.

    EventSource and <a> downloads can't send an Authorization header, so a token
    must ride in the query string — which lands in access logs and history. To
    minimise blast radius we never put the *access* token there; instead the
    client mints this scoped ``type="stream"`` token (valid for ~60s, usable
    only on the streaming/download routes) right before opening the connection.
    """
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": username,
        "exp": now + timedelta(seconds=ttl_seconds),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": "stream",
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
