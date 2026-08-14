#!/usr/bin/env python3
"""
Export interactions collection to pyKT-compatible CSV.

pyKT standard column order:
  uid, skill_name, problem_id, correct, timestamp

Extended columns (for richer KT models):
  response_time, hint_level, difficulty, mode, score, grade

Usage:
  python scripts/export_interactions.py                     # stdout
  python scripts/export_interactions.py -o interactions.csv  # file
  python scripts/export_interactions.py --extended           # include extra cols
"""

import argparse
import asyncio
import csv
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import interactions_collection


PYKT_COLUMNS = ["uid", "skill_name", "problem_id", "correct", "timestamp"]
EXTENDED_COLUMNS = PYKT_COLUMNS + [
    "response_time", "hint_level", "difficulty", "mode", "score", "grade",
]


async def export(output_file=None, extended=False):
    columns = EXTENDED_COLUMNS if extended else PYKT_COLUMNS

    cursor = interactions_collection.find({}).sort("timestamp", 1)

    if output_file:
        fh = open(output_file, "w", newline="", encoding="utf-8")
    else:
        fh = sys.stdout

    writer = csv.writer(fh)
    writer.writerow(columns)

    count = 0
    async for doc in cursor:
        row = [
            doc.get("student_id", ""),
            doc.get("skill_id", ""),
            doc.get("item_id", ""),
            int(doc.get("correct", False)),
            int(doc.get("timestamp", 0)),
        ]
        if extended:
            row.extend([
                doc.get("response_time", 0.0),
                doc.get("hint_level", 0),
                doc.get("difficulty", 0.0),
                doc.get("mode", 0),
                doc.get("score", 0.0),
                doc.get("grade", ""),
            ])
        writer.writerow(row)
        count += 1

    if output_file:
        fh.close()
        print(f"Exported {count} interactions to {output_file}", file=sys.stderr)
    else:
        print(f"# {count} interactions exported", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Export interactions to pyKT CSV")
    parser.add_argument("-o", "--output", help="Output CSV file path")
    parser.add_argument("--extended", action="store_true",
                        help="Include extra columns (response_time, hint, difficulty, mode, score, grade)")
    args = parser.parse_args()
    asyncio.run(export(args.output, args.extended))


if __name__ == "__main__":
    main()
