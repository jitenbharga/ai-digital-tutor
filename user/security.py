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
    import jwt
    from datetime import datetime, timedelta, timezone
    from auth_config import SECRET_KEY, ALGORITHM

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta_days: int = 7) -> str:
    import jwt
    import uuid
    from datetime import datetime, timedelta, timezone
    from auth_config import SECRET_KEY, ALGORITHM

    to_encode = data.copy()
    jti = uuid.uuid4().hex
    expire = datetime.now(timezone.utc) + timedelta(days=expires_delta_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    import jwt
    from auth_config import SECRET_KEY, ALGORITHM
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])