"""W5: the declarative index registry applies cleanly and reports failures loudly."""
import pytest


@pytest.mark.asyncio
async def test_ensure_indexes_applies_whole_registry(wire_db):
    import database

    result = await database.ensure_indexes()
    assert result["failed"] == 0
    assert result["created"] == len(database.INDEX_SPECS)


@pytest.mark.asyncio
async def test_ensure_indexes_counts_failures_without_crashing(wire_db, monkeypatch):
    import database

    # A spec referencing a non-existent collection attr must be counted as failed,
    # not crash the whole migration.
    monkeypatch.setattr(database, "INDEX_SPECS", [("nonexistent_collection", "x", {})])
    result = await database.ensure_indexes()
    assert result == {"created": 0, "failed": 1}


@pytest.mark.asyncio
async def test_ensure_indexes_raise_on_error(wire_db, monkeypatch):
    import database

    monkeypatch.setattr(database, "INDEX_SPECS", [("nonexistent_collection", "x", {})])
    with pytest.raises(Exception):
        await database.ensure_indexes(raise_on_error=True)
