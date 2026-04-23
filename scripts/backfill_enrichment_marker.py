#!/usr/bin/env python3
"""One-time backfill: stamp `intake_enrichment_completed_at` on legacy-enriched profiles.

WHY
===
Phase 1 of the Week 5 release introduced `intake_enrichment_completed_at` on
`UserProfile`, written only by `_enrich_profile_async` on success, and used
as the gate predicate that decides whether to run enrichment on a user's
next intake.

The new field is absent on every profile that was enriched before deploy —
367 production users and 260 staging users at the time of writing. When any
of those users completes their Week 5 intake (or later), the gate sees
`intake_enrichment_completed_at is None`, assumes the user has never been
enriched, and runs `_enrich_profile_async` over their existing rich fields.
Since weekly check-in transcripts are narrow, Opus produces sparse
extractions that CLOBBER the legacy-enriched values.

That is the exact Fabio bug Phase 1 was supposed to fix — deferred by one
intake cycle and expanded from 1 user to ~400.

This script backfills the marker by examining each profile and setting
`intake_enrichment_completed_at` to the profile's `updated_at` (or current
time if updated_at is missing) whenever ANY rich identity field is
populated — `work_summary`, `intake_summary`, or `ai_proficiency`.

SAFETY
======
* Read-only by default. Pass `--apply` to actually write.
* Prints a preview of every profile that would be updated.
* Never modifies profiles that already have the marker set.
* Never modifies profiles that have no rich identity fields (they're
  genuine first-timers or legitimately never-enriched; enrichment should
  run on their next intake).

USAGE
=====

    # Dry run (default)
    AWS_PROFILE=forge python scripts/backfill_enrichment_marker.py --env staging

    # Apply to staging
    AWS_PROFILE=forge python scripts/backfill_enrichment_marker.py --env staging --apply

    # Apply to production (requires --yes-production confirmation)
    AWS_PROFILE=forge python scripts/backfill_enrichment_marker.py --env production --apply --yes-production
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

import boto3


TABLES = {
    "staging": "forge-staging-profiles",
    "production": "forge-production-profiles",
}


def has_rich_identity(item: dict) -> bool:
    """True if the profile has evidence of prior enrichment — any identity field populated."""
    ws = item.get("work_summary") or ""
    isum = item.get("intake_summary") or ""
    ai_prof = item.get("ai_proficiency")
    # ai_proficiency in DDB is a dict like {"level": 3, "rationale": "..."}
    ai_prof_real = bool(ai_prof and isinstance(ai_prof, dict) and ai_prof.get("level"))
    return bool(ws.strip() or isum.strip() or ai_prof_real)


def pick_marker_timestamp(item: dict) -> str:
    """Choose the best-available timestamp for the enrichment marker.

    Preference order:
    1. `updated_at` — when the profile was last modified; most likely to
       coincide with the real enrichment time for legacy users.
    2. `intake_completed_at` — second-best signal.
    3. `created_at` — weakest, falls back if nothing else.
    4. Current time — last resort.
    """
    for key in ("updated_at", "intake_completed_at", "created_at"):
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
    return datetime.now(UTC).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["staging", "production"], required=True)
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default: dry run)")
    parser.add_argument("--yes-production", action="store_true", help="Required confirmation for --env production")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on profiles updated (for testing)")
    args = parser.parse_args()

    if args.env == "production" and args.apply and not args.yes_production:
        print("ERROR: --env production + --apply requires --yes-production confirmation.")
        sys.exit(1)

    table_name = TABLES[args.env]
    dynamo = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamo.Table(table_name)

    print(f"Scanning {table_name}...")
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    print(f"  {len(items)} profiles scanned")

    candidates = []
    already_marked = 0
    no_identity = 0
    for item in items:
        if item.get("intake_enrichment_completed_at"):
            already_marked += 1
            continue
        if not has_rich_identity(item):
            no_identity += 1
            continue
        candidates.append(item)

    print(f"\nClassification:")
    print(f"  Already have marker (skip): {already_marked}")
    print(f"  No rich identity fields — correctly unmarked (skip): {no_identity}")
    print(f"  LEGACY-ENRICHED needing backfill: {len(candidates)}")

    if args.limit and len(candidates) > args.limit:
        print(f"\n  (limiting to first {args.limit} per --limit)")
        candidates = candidates[: args.limit]

    print("\nSample of candidates (first 10):")
    for c in candidates[:10]:
        ts = pick_marker_timestamp(c)
        print(f"  {c.get('user_id'):40}  email={c.get('email', '?'):40}  marker→{ts}")

    if not args.apply:
        print(f"\nDRY RUN complete. Would update {len(candidates)} profiles. Re-run with --apply to execute.")
        return

    print(f"\nAPPLYING marker to {len(candidates)} profiles in {args.env}...")
    ok = 0
    errors = []
    for c in candidates:
        ts = pick_marker_timestamp(c)
        try:
            table.update_item(
                Key={"user_id": c["user_id"]},
                UpdateExpression="SET intake_enrichment_completed_at = :ts, updated_at = :now",
                ConditionExpression="attribute_not_exists(intake_enrichment_completed_at)",
                ExpressionAttributeValues={
                    ":ts": ts,
                    ":now": datetime.now(UTC).isoformat(),
                },
            )
            ok += 1
        except Exception as e:
            errors.append((c.get("user_id", "?"), str(e)[:100]))

    print(f"\nBackfill complete: {ok}/{len(candidates)} updated")
    if errors:
        print(f"Errors ({len(errors)}):")
        for uid, msg in errors[:10]:
            print(f"  {uid}: {msg}")


if __name__ == "__main__":
    main()
