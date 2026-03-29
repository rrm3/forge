#!/usr/bin/env python3
"""Migrate intake objectives from per-department to company-wide.

This script:
1. Reads all department configs from S3, builds UUID mapping (old dept IDs -> new company IDs)
2. Remaps keys in each user's intake-responses.json on S3
3. Uploads new config/company.json with 8 base objectives (6 retained + 2 Day 2)
4. Rewrites department configs to only contain department-specific extras
5. Backfills intake_weeks in DynamoDB for users who completed Week 1

Run with: AWS_PROFILE=forge python scripts/migrate-objectives-to-company.py [--dry-run]

Prerequisites:
- Valid AWS session for the forge profile
- boto3 installed (uv run)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# The S3 bucket used by Forge (production)
BUCKET = "forge-production-data"

# New company objectives with stable IDs (from config/company.json)
COMPANY_OBJECTIVES_FILE = Path(__file__).parent.parent / "config" / "company.json"

# The 7 original shared objectives matched by extraction_key.
# objective #7 "Starting points" (extraction_key: starting_points) is being DROPPED.
SHARED_EXTRACTION_KEYS = {
    "work_summary": "c0-work-summary",
    "daily_tasks": "c0-daily-tasks",
    "ai_tools_used": "c0-ai-tools",
    "core_skills": "c0-core-skills",
    "learning_goals": "c0-learning-goals",
    "goals": "c0-goals",
}

# extraction_key for the dropped objective - responses are preserved but not remapped
DROPPED_KEY = "starting_points"


def load_s3_json(s3, key: str) -> dict | list | None:
    """Load a JSON file from S3, returning None if not found."""
    try:
        resp = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(resp["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        logger.warning("Failed to read s3://%s/%s: %s", BUCKET, key, e)
        return None


def write_s3_json(s3, key: str, data: dict | list, dry_run: bool = False):
    """Write a JSON file to S3."""
    if dry_run:
        logger.info("  [DRY RUN] Would write s3://%s/%s", BUCKET, key)
        return
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2).encode(),
        ContentType="application/json",
    )
    logger.info("  Wrote s3://%s/%s", BUCKET, key)


def list_s3_keys(s3, prefix: str) -> list[str]:
    """List all keys under a prefix."""
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def build_uuid_mapping(s3) -> dict[str, str]:
    """Build mapping from old department UUIDs to new company UUIDs.

    Scans all department configs, matches objectives by extraction_key
    to the shared set, and maps old UUID -> new company UUID.
    """
    mapping: dict[str, str] = {}

    dept_keys = list_s3_keys(s3, "config/departments/")
    for key in dept_keys:
        if not key.endswith(".json"):
            continue
        dept_name = key.split("/")[-1].replace(".json", "")
        config = load_s3_json(s3, key)
        if not config:
            continue

        objectives = config.get("objectives", [])
        for obj in objectives:
            ext_key = obj.get("extraction_key", "")
            obj_id = obj.get("id", "")
            if ext_key in SHARED_EXTRACTION_KEYS and obj_id:
                new_id = SHARED_EXTRACTION_KEYS[ext_key]
                mapping[obj_id] = new_id
                logger.debug("  %s/%s: %s -> %s", dept_name, ext_key, obj_id, new_id)

    return mapping


def migrate_intake_responses(s3, mapping: dict[str, str], dry_run: bool = False) -> int:
    """Remap objective UUIDs in all user intake-responses.json files.

    Returns the number of files modified.
    """
    response_keys = list_s3_keys(s3, "profiles/")
    response_keys = [k for k in response_keys if k.endswith("/intake-responses.json")]

    modified = 0
    for key in response_keys:
        user_id = key.split("/")[1]
        data = load_s3_json(s3, key)
        if not data or not isinstance(data, dict):
            continue

        # Remap keys
        new_data = {}
        changed = False
        for obj_id, value in data.items():
            if obj_id in mapping:
                new_data[mapping[obj_id]] = value
                changed = True
            else:
                # Keep as-is (department-specific objectives or already migrated)
                new_data[obj_id] = value

        if changed:
            write_s3_json(s3, key, new_data, dry_run)
            modified += 1
            logger.info("  Migrated responses for user %s (%d keys remapped)", user_id, sum(1 for k in data if k in mapping))

    return modified


def rewrite_department_configs(s3, dry_run: bool = False) -> int:
    """Remove shared objectives from department configs, keeping only extras.

    Returns the number of departments modified.
    """
    dept_keys = list_s3_keys(s3, "config/departments/")
    modified = 0

    for key in dept_keys:
        if not key.endswith(".json"):
            continue
        dept_name = key.split("/")[-1].replace(".json", "")
        config = load_s3_json(s3, key)
        if not config:
            continue

        objectives = config.get("objectives", [])
        # Keep only objectives whose extraction_key is NOT in the shared set
        # and NOT the dropped "starting_points" key
        extras = [
            o for o in objectives
            if o.get("extraction_key", "") not in SHARED_EXTRACTION_KEYS
            and o.get("extraction_key", "") != DROPPED_KEY
        ]

        if len(extras) != len(objectives):
            config["objectives"] = extras
            write_s3_json(s3, key, config, dry_run)
            modified += 1
            removed = len(objectives) - len(extras)
            logger.info("  %s: removed %d shared objectives, kept %d extras", dept_name, removed, len(extras))

    return modified


def upload_company_config(s3, dry_run: bool = False):
    """Upload the new company.json to S3."""
    company_config = json.loads(COMPANY_OBJECTIVES_FILE.read_text())
    write_s3_json(s3, "config/company.json", company_config, dry_run)


DYNAMO_TABLE = "forge-profiles"


def backfill_intake_weeks(dynamo, dry_run: bool = False) -> int:
    """Backfill intake_weeks for users who completed Week 1.

    Scans DynamoDB profiles. For every user with intake_completed_at set
    but no intake_weeks entry for week 1, writes {"1": "<intake_completed_at>"}.
    This prevents them from being re-gated on Week 2.

    Returns the number of profiles updated.
    """
    paginator = dynamo.get_paginator("scan")
    updated = 0

    for page in paginator.paginate(
        TableName=DYNAMO_TABLE,
        ProjectionExpression="user_id, intake_completed_at, intake_weeks",
    ):
        for item in page.get("Items", []):
            user_id = item.get("user_id", {}).get("S")
            completed_at = item.get("intake_completed_at", {}).get("S")
            if not user_id or not completed_at:
                continue

            # Check if intake_weeks already has week 1
            existing_weeks = item.get("intake_weeks", {}).get("M", {})
            if "1" in existing_weeks:
                continue

            # Build the new intake_weeks map
            new_weeks = {k: v for k, v in existing_weeks.items()}
            new_weeks["1"] = {"S": completed_at}

            if dry_run:
                logger.info("  [DRY RUN] Would set intake_weeks={\"1\": \"%s\"} for user %s", completed_at, user_id)
                updated += 1
                continue

            dynamo.update_item(
                TableName=DYNAMO_TABLE,
                Key={"user_id": {"S": user_id}},
                UpdateExpression="SET intake_weeks = :w",
                ExpressionAttributeValues={":w": {"M": new_weeks}},
            )
            logger.info("  Set intake_weeks={\"1\": \"%s\"} for user %s", completed_at, user_id)
            updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Migrate objectives to company-wide config")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without writing")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN MODE ===\n")

    session = boto3.Session(profile_name="forge")
    s3 = session.client("s3")
    dynamo = session.client("dynamodb")

    # Step 1: Build UUID mapping
    logger.info("Step 1: Building UUID mapping from department configs...")
    mapping = build_uuid_mapping(s3)
    logger.info("  Found %d UUID mappings across departments\n", len(mapping))

    if not mapping:
        logger.error("No UUID mappings found. Are department configs on S3?")
        sys.exit(1)

    # Step 2: Migrate user intake responses
    logger.info("Step 2: Migrating user intake responses...")
    users_modified = migrate_intake_responses(s3, mapping, args.dry_run)
    logger.info("  Modified %d user response files\n", users_modified)

    # Step 3: Upload company config
    logger.info("Step 3: Uploading company.json...")
    upload_company_config(s3, args.dry_run)
    logger.info("")

    # Step 4: Rewrite department configs
    logger.info("Step 4: Rewriting department configs (removing shared objectives)...")
    depts_modified = rewrite_department_configs(s3, args.dry_run)
    logger.info("  Modified %d department configs\n", depts_modified)

    # Step 5: Backfill intake_weeks for existing users
    logger.info("Step 5: Backfilling intake_weeks for Week 1 completions...")
    weeks_backfilled = backfill_intake_weeks(dynamo, args.dry_run)
    logger.info("  Backfilled %d profiles\n", weeks_backfilled)

    logger.info("=== Migration complete ===")
    logger.info("  Users migrated: %d", users_modified)
    logger.info("  Departments rewritten: %d", depts_modified)
    logger.info("  intake_weeks backfilled: %d", weeks_backfilled)
    if args.dry_run:
        logger.info("\n  This was a dry run. Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
