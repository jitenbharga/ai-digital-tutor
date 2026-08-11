#!/usr/bin/env python3
"""
One-off migration: student + guardian role cleanup.

What it does
------------
1. Converts any user with role="teacher" or role="admin" to role="student".
2. Drops the legacy ``linked_students`` field from every user document.
3. Creates the ``guardian_links`` collection with indexes on
   (guardian_id) and (student_id) if they don't already exist.

Idempotent — safe to re-run; a second run is a no-op and logs zeros.

Usage
-----
    # Dry-run (read-only, prints what *would* change):
    python scripts/migrate_roles.py --dry-run

    # Execute for real:
    python scripts/migrate_roles.py

Requires MONGODB_URI and DB_NAME in the environment (or .env file).
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME")

if not MONGODB_URI or not DB_NAME:
    sys.exit("ERROR: MONGODB_URI and DB_NAME environment variables are required.")


async def migrate(dry_run: bool = False) -> None:
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    users = db["users"]

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\n{'='*50}")
    print(f"  Role Migration  ({mode})")
    print(f"  Database: {DB_NAME}")
    print(f"{'='*50}\n")

    # ── Step 1: Convert teacher/admin → student ─────────────────
    legacy_count = await users.count_documents({"role": {"$in": ["teacher", "admin"]}})
    print(f"[1/3] Users with role teacher/admin: {legacy_count}")

    if legacy_count > 0:
        if dry_run:
            # Show which users would be affected
            cursor = users.find(
                {"role": {"$in": ["teacher", "admin"]}},
                {"username": 1, "role": 1, "_id": 0},
            )
            async for doc in cursor:
                print(f"      Would convert: {doc['username']} ({doc['role']} → student)")
        else:
            result = await users.update_many(
                {"role": {"$in": ["teacher", "admin"]}},
                {"$set": {"role": "student"}},
            )
            print(f"      Converted {result.modified_count} user(s) to role='student'")

    # ── Step 2: Drop legacy linked_students field ───────────────
    has_linked = await users.count_documents({"linked_students": {"$exists": True}})
    print(f"\n[2/3] Users with linked_students field: {has_linked}")

    if has_linked > 0:
        if dry_run:
            print(f"      Would drop linked_students from {has_linked} document(s)")
        else:
            result = await users.update_many(
                {"linked_students": {"$exists": True}},
                {"$unset": {"linked_students": ""}},
            )
            print(f"      Removed linked_students from {result.modified_count} document(s)")

    # ── Step 3: Create guardian_links collection + indexes ───────
    print(f"\n[3/3] guardian_links collection & indexes")
    gl = db["guardian_links"]

    # Check existing indexes to avoid duplicates
    existing_indexes = await gl.index_information()
    idx_names = set(existing_indexes.keys())

    if dry_run:
        if "guardian_id_1" not in idx_names:
            print("      Would create index on (guardian_id)")
        else:
            print("      Index (guardian_id) already exists — skip")
        if "student_id_1" not in idx_names:
            print("      Would create index on (student_id)")
        else:
            print("      Index (student_id) already exists — skip")
        if "guardian_id_1_student_id_1" not in idx_names:
            print("      Would create unique index on (guardian_id, student_id)")
        else:
            print("      Unique index (guardian_id, student_id) already exists — skip")
    else:
        if "guardian_id_1" not in idx_names:
            await gl.create_index("guardian_id")
            print("      Created index on (guardian_id)")
        else:
            print("      Index (guardian_id) already exists — skip")

        if "student_id_1" not in idx_names:
            await gl.create_index("student_id")
            print("      Created index on (student_id)")
        else:
            print("      Index (student_id) already exists — skip")

        if "guardian_id_1_student_id_1" not in idx_names:
            await gl.create_index(
                [("guardian_id", 1), ("student_id", 1)],
                unique=True,
            )
            print("      Created unique compound index on (guardian_id, student_id)")
        else:
            print("      Unique index (guardian_id, student_id) already exists — skip")

    # ── Summary ─────────────────────────────────────────────────
    remaining = await users.count_documents({"role": {"$in": ["teacher", "admin"]}})
    total_users = await users.count_documents({})
    students = await users.count_documents({"role": "student"})
    guardians = await users.count_documents({"role": "guardian"})

    print(f"\n{'─'*50}")
    print(f"  Summary")
    print(f"  Total users:      {total_users}")
    print(f"  Students:         {students}")
    print(f"  Guardians:        {guardians}")
    print(f"  Legacy roles left:{remaining}")
    print(f"{'─'*50}\n")

    client.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate roles to student+guardian model")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying the database",
    )
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
