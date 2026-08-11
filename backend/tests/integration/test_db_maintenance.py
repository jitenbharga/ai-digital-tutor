"""W5: index-migration fail-loud behavior + telemetry pruning."""
import time

import pytest


@pytest.mark.asyncio
async def test_ensure_indexes_raise_on_error_propagates(wire_db, monkeypatch):
    import database

    class _BadColl:
        async def create_index(self, *a, **k):
            raise RuntimeError("index build failed")

    # First INDEX_SPEC targets users_collection — make it fail.
    monkeypatch.setattr(database, "users_collection", _BadColl(), raising=False)

    # Migration mode: the failure propagates (blocks the deploy).
    with pytest.raises(RuntimeError):
        await database.ensure_indexes(raise_on_error=True)

    # Startup mode: swallowed but surfaced in the summary (no longer hidden).
    result = await database.ensure_indexes(raise_on_error=False)
    assert result["failed"] >= 1


@pytest.mark.asyncio
async def test_telemetry_prune_deletes_old_keeps_recent(wire_db):
    from scripts.telemetry_maintenance import prune

    now = time.time()
    inter = wire_db["interactions_collection"]
    await inter.insert_one({"timestamp": now - 200 * 86400, "x": "old"})
    await inter.insert_one({"timestamp": now - 1 * 86400, "x": "recent"})

    summary = await prune(dry_run=False)
    assert summary["interactions_collection"] == 1
    remaining = [d async for d in inter.find({})]
    assert len(remaining) == 1 and remaining[0]["x"] == "recent"


@pytest.mark.asyncio
async def test_telemetry_prune_dry_run_deletes_nothing(wire_db):
    from scripts.telemetry_maintenance import prune

    now = time.time()
    llm = wire_db["llm_calls_collection"]
    await llm.insert_one({"start_ts": now - 100 * 86400})  # older than 30d default
    await prune(dry_run=True)
    assert await llm.count_documents({}) == 1


@pytest.mark.asyncio
async def test_telemetry_retention_zero_skips(wire_db, monkeypatch):
    from scripts.telemetry_maintenance import prune

    monkeypatch.setenv("RETAIN_INTERACTIONS_DAYS", "0")
    now = time.time()
    inter = wire_db["interactions_collection"]
    await inter.insert_one({"timestamp": now - 999 * 86400})

    summary = await prune(dry_run=False)
    assert "interactions_collection" not in summary
    assert await inter.count_documents({}) == 1
