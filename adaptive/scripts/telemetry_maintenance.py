#!/usr/bin/env python3
"""
W5: prune append-heavy telemetry so it can't grow without bound.

interactions / llm_calls / rl_transitions store float-epoch timestamps (not BSON
dates), so a Mongo TTL index is a no-op on them. This script deletes rows older
than a per-collection retention window and is meant to run on a schedule (cron or
a scheduled task), e.g. nightly.

    python -m scripts.telemetry_maintenance             # prune with defaults
    python -m scripts.telemetry_maintenance --dry-run   # report only, delete nothing

Retention (days) is per-collection and env-overridable; set a value to 0 to skip.
For long-term analytics, export to a warehouse before pruning (see docs).
"""
import argparse
import asyncio
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("telemetry_maintenance")

# (collection_attr, epoch_field, default_retention_days, env_override)
RETENTION = [
    ("interactions_collection", "timestamp", 90, "RETAIN_INTERACTIONS_DAYS"),
    ("llm_calls_collection", "start_ts", 30, "RETAIN_LLM_CALLS_DAYS"),
    ("rl_transitions_collection", "ts", 180, "RETAIN_RL_TRANSITIONS_DAYS"),
]


async def prune(dry_run: bool = False) -> dict:
    """Delete telemetry older than its retention window. Returns {collection: n}."""
    import database

    now = time.time()
    summary: dict = {}
    for var, field, default_days, env in RETENTION:
        days = int(os.getenv(env, str(default_days)))
        if days <= 0:
            log.info("%s: retention disabled (0) — skipping", var)
            continue
        cutoff = now - days * 86400
        coll = getattr(database, var)
        query = {field: {"$lt": cutoff}}
        if dry_run:
            n = await coll.count_documents(query)
            log.info("[dry-run] %s: %d docs older than %dd would be deleted", var, n, days)
        else:
            res = await coll.delete_many(query)
            n = res.deleted_count
            log.info("%s: deleted %d docs older than %dd", var, n, days)
        summary[var] = n
    return summary


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report only")
    args = ap.parse_args()

    from database import client
    try:
        await client.admin.command("ping")
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: cannot reach MongoDB: {e}", file=sys.stderr)
        return 2

    await prune(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
