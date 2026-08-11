"""
W3 integration tests — failed-login backoff + account-recovery tokens.
Run against a real async Mongo engine (mongomock locally / mongo:7 in CI).
"""
import pytest
from fastapi import HTTPException


# ── L-11: failed-login backoff ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_backoff_locks_after_max_failures(wire_db, monkeypatch):
    import core.login_guard as lg

    monkeypatch.setattr(lg, "LOGIN_MAX_FAILURES", 3)
    for _ in range(3):
        await lg.record_login_failure("bob")

    with pytest.raises(HTTPException) as exc:
        await lg.assert_login_allowed("bob")
    assert exc.value.status_code == 429
    assert "Retry-After" in (exc.value.headers or {})


@pytest.mark.asyncio
async def test_backoff_below_threshold_allowed(wire_db, monkeypatch):
    import core.login_guard as lg

    monkeypatch.setattr(lg, "LOGIN_MAX_FAILURES", 5)
    await lg.record_login_failure("carol")
    await lg.record_login_failure("carol")
    await lg.assert_login_allowed("carol")  # 2 < 5 → no raise


@pytest.mark.asyncio
async def test_backoff_cleared_on_success(wire_db, monkeypatch):
    import core.login_guard as lg

    monkeypatch.setattr(lg, "LOGIN_MAX_FAILURES", 2)
    await lg.record_login_failure("dave")
    await lg.record_login_failure("dave")
    await lg.clear_login_failures("dave")
    await lg.assert_login_allowed("dave")  # cleared → no raise


# ── W3: recovery tokens (reset + verify) ────────────────────────────────────
@pytest.mark.asyncio
async def test_reset_token_is_single_use(wire_db):
    from core.account_recovery import (
        create_token, consume_token, PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS,
    )

    t = await create_token("erin", PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS)
    assert await consume_token(t, PURPOSE_RESET) == "erin"
    assert await consume_token(t, PURPOSE_RESET) is None  # replay rejected


@pytest.mark.asyncio
async def test_token_wrong_purpose_rejected(wire_db):
    from core.account_recovery import (
        create_token, consume_token, PURPOSE_RESET, PURPOSE_VERIFY,
        RESET_TOKEN_TTL_SECONDS,
    )

    t = await create_token("frank", PURPOSE_RESET, RESET_TOKEN_TTL_SECONDS)
    assert await consume_token(t, PURPOSE_VERIFY) is None  # purpose mismatch


@pytest.mark.asyncio
async def test_expired_token_rejected(wire_db):
    from core.account_recovery import create_token, consume_token, PURPOSE_RESET

    t = await create_token("grace", PURPOSE_RESET, -1)  # already expired
    assert await consume_token(t, PURPOSE_RESET) is None


@pytest.mark.asyncio
async def test_verify_token_roundtrip(wire_db):
    from core.account_recovery import (
        create_token, consume_token, PURPOSE_VERIFY, VERIFY_TOKEN_TTL_SECONDS,
    )

    t = await create_token("heidi", PURPOSE_VERIFY, VERIFY_TOKEN_TTL_SECONDS)
    assert await consume_token(t, PURPOSE_VERIFY) == "heidi"


# ── emailer dev fallback (no SMTP → logs, returns False, never raises) ───────
def test_emailer_dev_fallback(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from core.emailer import send_email

    assert send_email("someone@example.com", "Subject", "Body") is False
