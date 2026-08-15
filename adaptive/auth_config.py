import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = (os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY") or "").strip()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set in environment")

VERIFY_TOKEN_TTL_SECONDS = int(os.getenv("VERIFY_TOKEN_TTL_SECONDS", "86400"))
RESET_TOKEN_TTL_SECONDS = int(os.getenv("RESET_TOKEN_TTL_SECONDS", "3600"))
PURPOSE_VERIFY = "verify_email"
PURPOSE_RESET = "reset_password"


# SEC H-3: minimum secret key length enforcement
MIN_SECRET_KEY_LEN = 32
_PLACEHOLDERS = {"change-me", "your-secret", "secret-key", "dev-secret", "test-secret"}


def validate_secret_key(key: str, *, test_mode: bool = False) -> None:
    """
    Validate JWT secret key strength.

    Args:
        key: The secret key to validate
        test_mode: If True, relaxes length requirement but still requires non-empty

    Raises:
        ValueError: If key is missing, too short, or is a known placeholder
    """
    if not key:
        raise ValueError("JWT_SECRET_KEY must be set in environment")

    if not test_mode:
        if len(key) < MIN_SECRET_KEY_LEN:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_SECRET_KEY_LEN} characters"
            )
        low = key.lower()
        for ph in _PLACEHOLDERS:
            if ph in low:
                raise ValueError("JWT_SECRET_KEY appears to be a placeholder value")