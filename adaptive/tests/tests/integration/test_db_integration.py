"""
W2 backend integration tests — REAL async MongoDB (mongomock locally, mongo:7 in CI).

These drive production code paths (database.ensure_indexes, dependencies.get_current_user,
rate_limit.check_llm_budget, refresh-token revocation invariants) against a live
async Mongo engine, not a MagicMock.
"""
import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError


# ── database.ensure_indexes() ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ensure_indexes_creates_unique_username(wire_db):
    import database

    await database.ensure_indexes()  # must not raise

    users = wire_db["users_collection"]
    await users.insert_one({"username": "alice", "role": "student"})
    # The unique index created by ensure_indexes must reject a duplicate.
    with pytest.raises(DuplicateKeyError):
        await users.insert_one({"username": "alice", "role": "student"})


@pytest.mark.asyncio
async def test_ensure_indexes_declares_username_index(wire_db):
    import database

    await database.ensure_indexes()
    info = await wire_db["users_collection"].index_information()
    assert any(("username", 1) in v.get("key", []) for v in info.values())


# ── dependencies.get_current_user() against a real users collection ─────────
@pytest.mark.asyncio
async def test_get_current_user_returns_real_user(wire_db):
    import dependencies
    from security import create_access_token

    await wire_db["users_collection"].insert_one(
        {"username": "bob", "role": "student"}
    )
    token = create_access_token({"sub": "bob", "role": "student"})
    user = await dependencies.get_current_user(token=token)
    assert user["username"] == "bob"
    assert user["role"] == "student"


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_token_as_bearer(wire_db):
    import dependencies
    from security import create_refresh_token

    await wire_db["users_collection"].insert_one({"username": "bob"})
    refresh, _ = create_refresh_token({"sub": "bob", "role": "student"})
    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(token=refresh)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_unknown_user_401(wire_db):
    import dependencies
    from security import create_access_token

    token = create_access_token({"sub": "ghost", "role": "student"})
    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(token=token)
    assert exc.value.status_code == 401


# ── rate_limit.check_llm_budget() atomic increment + cap + fail-closed ──────
@pytest.mark.asyncio
async def test_llm_budget_atomic_increment_and_cap(wire_db, monkeypatch):
    import rate_limit

    monkeypatch.setattr(rate_limit, "LLM_DAILY_REQUEST_CAP", 3)
    user = {"username": "carol"}

    # 3 requests allowed (count 1..3, cap is exclusive: count > cap -> 429).
    for _ in range(3):
        assert await rate_limit.check_llm_budget(user) == user

    # 4th exceeds the cap.
    with pytest.raises(HTTPException) as exc:
        await rate_limit.check_llm_budget(user)
    assert exc.value.status_code == 429

    doc = await wire_db["llm_usage_collection"].find_one({"username": "carol"})
    assert doc["count"] == 4  # every call incremented exactly once (atomic)


@pytest.mark.asyncio
async def test_llm_budget_fails_closed_when_store_down(wire_db, monkeypatch):
    import database
    import rate_limit

    class _Boom:
        async def find_one_and_update(self, *a, **k):
            raise RuntimeError("mongo unreachable")

    monkeypatch.setattr(database, "llm_usage_collection", _Boom(), raising=False)
    with pytest.raises(HTTPException) as exc:
        await rate_limit.check_llm_budget({"username": "dave"})
    assert exc.value.status_code == 503  # fail closed, never silently allow paid calls


# ── refresh-token persistence invariants (mirror auth.py) ───────────────────
@pytest.mark.asyncio
async def test_refresh_token_unique_jti_and_family_revoke(wire_db):
    import database

    await database.ensure_indexes()
    rtc = wire_db["refresh_tokens_collection"]

    await rtc.insert_one({"jti": "j1", "username": "erin", "revoked": False})
    # jti is a unique index — a replayed/duplicated jti cannot be stored twice.
    with pytest.raises(DuplicateKeyError):
        await rtc.insert_one({"jti": "j1", "username": "erin", "revoked": False})

    # Family revoke (auth.py reuse-detection path): revoke all active for a user.
    await rtc.insert_one({"jti": "j2", "username": "erin", "revoked": False})
    await rtc.update_many(
        {"username": "erin", "revoked": False}, {"$set": {"revoked": True}}
    )
    assert await rtc.count_documents({"username": "erin", "revoked": False}) == 0
