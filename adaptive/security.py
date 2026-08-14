import jwt
from jwt import PyJWTError as JWTError
from datetime import datetime, timedelta, timezone
import uuid

from pwdlib import PasswordHash

ph = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return ph.verify(plain, hashed)
    except Exception:
        try:
            return ph.verify(hashed, plain)
        except Exception:
            return False


def create_access_token(data: dict, expires_delta_minutes: int = 15) -> str:
    """Short-lived access token with jti and iat claims."""
    from auth_config import SECRET_KEY, ALGORITHM
    now = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode.update({
        "exp": now + timedelta(minutes=expires_delta_minutes),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "type": "access",
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta_days: int = 7) -> tuple[str, str]:
    """Longer-lived refresh token. Returns (encoded_token, jti)."""
    from auth_config import SECRET_KEY, ALGORITHM
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    to_encode = data.copy()
    to_encode.update({
        "exp": now + timedelta(days=expires_delta_days),
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
    from auth_config import SECRET_KEY, ALGORITHM
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
    from auth_config import SECRET_KEY, ALGORITHM
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
