"""
Centralized auth configuration — single source of truth.

Reads from configs/default.yaml (static defaults) and environment
variables (SECRET_KEY override). Every module that needs auth
constants imports from here instead of defining its own.
"""

import os
import sys
import yaml

# ── Load YAML defaults ──────────────────────────────────────────
_config_path = os.path.join(os.path.dirname(__file__), "configs", "default.yaml")
with open(_config_path) as _f:
    _cfg = yaml.safe_load(_f).get("auth", {})

ALGORITHM: str = _cfg.get("algorithm", "HS256")
# SEC L-2: the access token is SHORT-LIVED (15 min); sessions persist via the
# httpOnly refresh cookie + silent refresh. The fallback matches
# configs/default.yaml so a missing key can never silently widen the TTL to days.
ACCESS_TOKEN_EXPIRE_MINUTES: int = _cfg.get("access_token_expire_minutes", 15)
REFRESH_TOKEN_EXPIRE_DAYS: int = _cfg.get("refresh_token_expire_days", 7)

# ── SECRET_KEY validation (SEC H-3) ──────────────────────────────
# A guessable HS256 key lets anyone forge tokens for any user/role, so we refuse
# to boot on a missing / weak / placeholder key in EVERY environment except an
# explicit test run (where short deterministic keys are required and harmless).
MIN_SECRET_KEY_LEN = 32
_WEAK_SECRETS = {
    "change-me-to-a-random-64-char-string",
    "ci-test-secret-key-not-for-production",
    "secret", "changeme", "please-change-me",
}


def validate_secret_key(secret_key: str, *, test_mode: bool,
                        min_len: int = MIN_SECRET_KEY_LEN) -> None:
    """Fail closed on an unusable signing key. Pure + unit-testable.

    * Missing key  -> always rejected (even under test).
    * Non-test env -> reject keys shorter than ``min_len`` or matching a known
      placeholder.
    """
    if not secret_key:
        raise ValueError(
            "SECRET_KEY environment variable is required. "
            "Set it before starting the server."
        )
    if test_mode:
        return
    if len(secret_key) < min_len or secret_key in _WEAK_SECRETS:
        raise ValueError(
            f"SECRET_KEY is too weak: it must be at least {min_len} random "
            "characters and not a known placeholder. Generate one with "
            '`python -c "import secrets; print(secrets.token_urlsafe(48))"` and '
            "set it via the SECRET_KEY environment variable. "
            "(Enforced in every environment except an explicit test run.)"
        )


SECRET_KEY: str = os.getenv("SECRET_KEY", "").strip()
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
# Test mode: an explicit test/ci ENVIRONMENT, or we are running under pytest
# (conftest imports this module during collection, before ENVIRONMENT is set).
TEST_MODE: bool = ENVIRONMENT in {"test", "ci"} or "pytest" in sys.modules
validate_secret_key(SECRET_KEY, test_mode=TEST_MODE)
