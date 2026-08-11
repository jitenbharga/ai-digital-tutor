"""
W4 integration tests for the repository + service layers.

auth.py / dependencies.py now delegate all persistence to these, so proving the
repositories + TokenService behave correctly also validates the refactor.
"""
import pytest


@pytest.mark.asyncio
async def test_user_repository_crud(wire_db):
    from repositories.users import UserRepository

    await UserRepository.create({"username": "alice", "role": "student"})
    assert await UserRepository.exists("alice")
    assert not await UserRepository.exists("ghost")

    u = await UserRepository.get_by_username("alice")
    assert u["role"] == "student"

    await UserRepository.set_password("alice", "hashed123")
    assert (await UserRepository.get_by_username("alice"))["hashed_password"] == "hashed123"

    await UserRepository.set_email_verified("alice", True)
    assert (await UserRepository.get_by_username("alice"))["email_verified"] is True


@pytest.mark.asyncio
async def test_user_repository_by_username_or_email(wire_db):
    from repositories.users import UserRepository

    await UserRepository.create({"username": "bob", "email": "bob@x.com"})
    assert (await UserRepository.get_by_username_or_email("bob@x.com"))["username"] == "bob"
    assert (await UserRepository.get_by_username_or_email("BOB@X.COM"))["username"] == "bob"
    assert (await UserRepository.get_by_username_or_email("bob"))["username"] == "bob"
    assert await UserRepository.get_by_username_or_email("nobody") is None


@pytest.mark.asyncio
async def test_refresh_token_repository_store_get_revoke(wire_db):
    from repositories.refresh_tokens import RefreshTokenRepository

    await RefreshTokenRepository.store("j1", "carol", 7)
    doc = await RefreshTokenRepository.get("j1")
    assert doc["username"] == "carol" and doc["revoked"] is False

    await RefreshTokenRepository.revoke("j1")
    assert (await RefreshTokenRepository.get("j1"))["revoked"] is True


@pytest.mark.asyncio
async def test_refresh_token_family_revoke(wire_db):
    from repositories.refresh_tokens import RefreshTokenRepository

    await RefreshTokenRepository.store("a1", "dave", 7)
    await RefreshTokenRepository.store("a2", "dave", 7)
    await RefreshTokenRepository.revoke_family("dave")

    from database import refresh_tokens_collection
    left = await refresh_tokens_collection.count_documents({"username": "dave", "revoked": False})
    assert left == 0


@pytest.mark.asyncio
async def test_token_service_issue_and_rotate(wire_db):
    from services.token_service import TokenService
    from repositories.refresh_tokens import RefreshTokenRepository
    from security import decode_token

    access, refresh = await TokenService.issue_token_pair("erin", "student")
    ap, rp = decode_token(access), decode_token(refresh)
    assert ap["type"] == "access" and ap["sub"] == "erin"
    assert rp["type"] == "refresh"
    assert (await RefreshTokenRepository.get(rp["jti"]))["revoked"] is False

    # Rotation: new pair issued, old jti revoked.
    _, new_refresh = await TokenService.rotate_refresh(rp["jti"], "erin", "student")
    np = decode_token(new_refresh)
    assert np["jti"] != rp["jti"]
    assert (await RefreshTokenRepository.get(rp["jti"]))["revoked"] is True
    assert (await RefreshTokenRepository.get(np["jti"]))["revoked"] is False
