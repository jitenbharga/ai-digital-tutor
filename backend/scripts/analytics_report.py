"""
P0.3 — Analytics Report

Query the analytics_events collection and print funnel metrics.

Usage:
  python scripts/analytics_report.py [--days 7]
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    parser = argparse.ArgumentParser(description="Analytics Report (P0.3)")
    parser.add_argument("--days", type=int, default=7, help="Look back N days")
    args = parser.parse_args()

    from database import db
    coll = db["analytics_events"]

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    # Count events
    event_counts = Counter()
    unique_students = set()
    answers_per_student = Counter()
    day_counts = Counter()  # student_id -> set of active days

    cursor = coll.find({"timestamp": {"$gte": cutoff}})
    student_days = {}  # student_id -> set of date strings

    async for doc in cursor:
        event = doc.get("event", "unknown")
        sid = doc.get("student_id", "?")
        ts = doc.get("timestamp")

        event_counts[event] += 1
        unique_students.add(sid)

        if event == "answer_submitted":
            answers_per_student[sid] += 1

        if ts:
            day_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            if sid not in student_days:
                student_days[sid] = set()
            student_days[sid].add(day_str)

    total_students = len(unique_students)
    signups = event_counts.get("signup", 0)
    onboarding_starts = event_counts.get("onboarding_start", 0)
    onboarding_completes = event_counts.get("onboarding_complete", 0)
    total_answers = event_counts.get("answer_submitted", 0)
    sessions = event_counts.get("session_start", 0)

    # Retention: students active on >1 day
    retained_d1 = sum(1 for days in student_days.values() if len(days) >= 2)
    retained_d7 = sum(1 for days in student_days.values() if len(days) >= 7)

    print(f"\n{'='*50}")
    print(f"  ANALYTICS REPORT (last {args.days} days)")
    print(f"{'='*50}")
    print(f"  Signups:                {signups}")
    print(f"  Onboarding started:     {onboarding_starts}")
    print(f"  Onboarding completed:   {onboarding_completes}")
    print(f"  Completion rate:        {onboarding_completes/max(onboarding_starts,1):.0%}")
    print(f"  Total answers:          {total_answers}")
    print(f"  Sessions:               {sessions}")
    print(f"  Unique active students: {total_students}")
    if total_students:
        print(f"  Avg answers/student:    {total_answers/total_students:.1f}")
    print(f"  Day-1 retention:        {retained_d1}/{total_students} ({retained_d1/max(total_students,1):.0%})")
    print(f"  Day-7 retention:        {retained_d7}/{total_students} ({retained_d7/max(total_students,1):.0%})")
    print()

    if event_counts:
        print("  All events:")
        for ev, count in event_counts.most_common():
            print(f"    {ev}: {count}")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
