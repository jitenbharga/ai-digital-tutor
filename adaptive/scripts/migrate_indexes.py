#!/usr/bin/env python3
"""
W5: create MongoDB indexes as an explicit deploy step (fail-loud).

Run before/at deploy:

    python -m scripts.migrate_indexes

Exits non-zero if any index fails, so a broken index blocks the rollout instead
of silently degrading query performance (the old behaviour swallowed the error).
In production set AUTO_ENSURE_INDEXES=0 so the app does NOT lazily create indexes
at startup and this migration is the single source of truth.
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main() -> int:
    from database import ensure_indexes, client

    try:
        await client.admin.command("ping")
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot reach MongoDB: {e}", file=sys.stderr)
        return 2

    result = await ensure_indexes(raise_on_error=False)
    if result["failed"]:
        print(f"FAILED: {result['failed']} index(es) could not be created", file=sys.stderr)
        return 1
    print(f"OK: {result['created']} indexes ensured")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
