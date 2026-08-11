"""
Integration-test fixtures (W2).

These tests exercise REAL persistence code against a real async MongoDB engine:
  * CI  -> a live `mongo:7` service container (INTEGRATION_REAL_MONGO=1)
  * dev -> mongomock_motor (in-memory, real Mongo query/index semantics)

The SAME tests run against both, closing the audit's #1 testing gap
("not one test exercises a real Mongo query, index, or aggregation").

Run locally with:
    INTEGRATION_TESTS=1 pytest tests/integration -v
"""
import os
import uuid

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def mongo_db():
    """Yield a clean async database (real Mongo in CI, mongomock locally)."""
    if os.getenv("INTEGRATION_REAL_MONGO") == "1":
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(
            os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            serverSelectionTimeoutMS=4000,
        )
        name = f"test_integration_{uuid.uuid4().hex[:8]}"
        await client.drop_database(name)
        try:
            yield client[name]
        finally:
            await client.drop_database(name)
            client.close()
    else:
        from mongomock_motor import AsyncMongoMockClient

        yield AsyncMongoMockClient()[f"test_{uuid.uuid4().hex[:8]}"]


@pytest.fixture
def wire_db(monkeypatch, mongo_db):
    """Point the app's module-level collections at the test database.

    Modules bind collection names at import (``from database import X``), so we
    patch both the ``database`` module and the direct importers. Collections are
    named after their attribute so `ensure_indexes()` and the code under test all
    resolve to the same test collection.
    """
    import database

    # W5: reset the per-worker user cache so entries can't leak across tests.
    from core import user_cache
    user_cache.clear()

    for attr in dir(database):
        if attr.endswith("_collection") or attr == "students_col":
            monkeypatch.setattr(database, attr, mongo_db[attr], raising=False)

    # dependencies.py did `from database import users_collection` at module load.
    import dependencies
    monkeypatch.setattr(
        dependencies, "users_collection", mongo_db["users_collection"], raising=False
    )
    return mongo_db
