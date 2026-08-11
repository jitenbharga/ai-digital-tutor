"""User persistence. The only module that reads/writes the ``users`` collection.

W5: `get_by_username` (the auth hot path) is read-through cached with a short TTL;
every write invalidates the cache so callers never see stale credentials/roles.
"""
from typing import Optional


def _col():
    # Resolve lazily so tests can patch database.users_collection (wire_db).
    import database
    return database.users_collection


class UserRepository:
    @staticmethod
    async def get_by_username(username: str, use_cache: bool = True) -> Optional[dict]:
        """Read a user by username. Cached by default (the get_current_user hot
        path). Pass ``use_cache=False`` for credential checks (login) so a reset
        password can never be authenticated from a stale per-worker entry."""
        from core import user_cache

        if use_cache:
            cached = user_cache.get(username)
            if cached is not None:
                return cached
        doc = await _col().find_one({"username": username})
        if use_cache:
            user_cache.put(username, doc)
        return doc

    @staticmethod
    async def get_by_username_or_email(identifier: str) -> Optional[dict]:
        ident = (identifier or "").strip().lower()
        return await _col().find_one(
            {"$or": [{"username": ident}, {"email": ident}]}
        )

    @staticmethod
    async def get_by_email(email: str) -> Optional[dict]:
        ident = (email or "").strip().lower()
        if not ident:
            return None
        return await _col().find_one({"email": ident})

    @staticmethod
    async def exists(username: str) -> bool:
        return await _col().find_one({"username": username}) is not None

    @staticmethod
    async def email_exists(email: str) -> bool:
        return await UserRepository.get_by_email(email) is not None

    @staticmethod
    async def create(doc: dict):
        from core import user_cache

        res = await _col().insert_one(doc)
        user_cache.invalidate(doc.get("username"))
        return res

    @staticmethod
    async def set_password(username: str, hashed_password: str):
        from core import user_cache

        res = await _col().update_one(
            {"username": username}, {"$set": {"hashed_password": hashed_password}}
        )
        user_cache.invalidate(username)
        return res

    @staticmethod
    async def set_google_sub(username: str, google_sub: str):
        from core import user_cache

        res = await _col().update_one(
            {"username": username}, {"$set": {"google_sub": google_sub}}
        )
        user_cache.invalidate(username)
        return res

    @staticmethod
    async def set_email_verified(username: str, verified: bool = True):
        from core import user_cache

        res = await _col().update_one(
            {"username": username}, {"$set": {"email_verified": verified}}
        )
        user_cache.invalidate(username)
        return res
