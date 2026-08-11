"""W5: the auth user-lookup cache (read-through + write-invalidation)."""
import pytest


@pytest.mark.asyncio
async def test_cache_serves_hit_without_hitting_db(wire_db, monkeypatch):
    from core import user_cache
    from repositories.users import UserRepository

    monkeypatch.setattr(user_cache, "TTL_SECONDS", 30)
    await UserRepository.create({"username": "alice", "role": "student"})
    assert (await UserRepository.get_by_username("alice"))["role"] == "student"  # caches

    # Delete straight from the DB (bypassing repository invalidation).
    await wire_db["users_collection"].delete_one({"username": "alice"})
    # A cached read still returns the doc — proving the cache is in effect.
    cached = await UserRepository.get_by_username("alice")
    assert cached is not None and cached["role"] == "student"


@pytest.mark.asyncio
async def test_write_invalidates_cache(wire_db, monkeypatch):
    from core import user_cache
    from repositories.users import UserRepository

    monkeypatch.setattr(user_cache, "TTL_SECONDS", 30)
    await UserRepository.create({"username": "bob", "email_verified": False})
    await UserRepository.get_by_username("bob")  # cache it
    await UserRepository.set_email_verified("bob", True)  # must invalidate
    assert (await UserRepository.get_by_username("bob"))["email_verified"] is True


@pytest.mark.asyncio
async def test_ttl_zero_disables_cache(wire_db, monkeypatch):
    from core import user_cache
    from repositories.users import UserRepository

    monkeypatch.setattr(user_cache, "TTL_SECONDS", 0)
    await UserRepository.create({"username": "carol"})
    await UserRepository.get_by_username("carol")
    await wire_db["users_collection"].delete_one({"username": "carol"})
    assert await UserRepository.get_by_username("carol") is None  # always hits DB


@pytest.mark.asyncio
async def test_miss_is_not_cached(wire_db, monkeypatch):
    from core import user_cache
    from repositories.users import UserRepository

    monkeypatch.setattr(user_cache, "TTL_SECONDS", 30)
    assert await UserRepository.get_by_username("ghost") is None  # miss, must not cache
    await UserRepository.create({"username": "ghost", "role": "student"})
    assert (await UserRepository.get_by_username("ghost"))["role"] == "student"


@pytest.mark.asyncio
async def test_use_cache_false_reads_fresh(wire_db, monkeypatch):
    """SEC: login uses use_cache=False, so a password changed on another worker
    (DB write with no local invalidation) is seen immediately — a reset password
    can't authenticate from a stale per-worker entry."""
    from core import user_cache
    from repositories.users import UserRepository

    monkeypatch.setattr(user_cache, "TTL_SECONDS", 30)
    await UserRepository.create({"username": "dave", "hashed_password": "OLD"})
    await UserRepository.get_by_username("dave")  # prime cache with OLD
    await wire_db["users_collection"].update_one(
        {"username": "dave"}, {"$set": {"hashed_password": "NEW"}}
    )
    # Cached path returns OLD; the login path (use_cache=False) returns NEW.
    assert (await UserRepository.get_by_username("dave"))["hashed_password"] == "OLD"
    assert (await UserRepository.get_by_username("dave", use_cache=False))["hashed_password"] == "NEW"
