#!/usr/bin/env python3
"""Copy a user's data from production to staging for QA testing.

Copies profile (DynamoDB), intake responses (S3), and optionally session
transcripts (S3) from production to staging. The user's production user_id
is mapped to a staging user_id so you can masquerade as them.

Usage:
  # Copy by email (looks up production user_id automatically)
  AWS_PROFILE=forge python scripts/copy-user-to-staging.py --email jane@digital-science.com

  # Copy by production user_id directly
  AWS_PROFILE=forge python scripts/copy-user-to-staging.py --user-id 7418f468-...

  # Also copy session transcripts (larger, slower)
  AWS_PROFILE=forge python scripts/copy-user-to-staging.py --email jane@digital-science.com --include-sessions

  # Set a week override for testing
  AWS_PROFILE=forge python scripts/copy-user-to-staging.py --email jane@digital-science.com --week 2

After copying, masquerade as the user in staging:
  1. Open staging app
  2. Open browser console
  3. Run: localStorage.setItem('forge-masquerade', 'jane@digital-science.com')
  4. Refresh the page
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROD_BUCKET = "forge-production-data"
STAGING_BUCKET = "forge-staging-data"
PROD_PROFILES = "forge-production-profiles"
STAGING_PROFILES = "forge-staging-profiles"
PROD_SESSIONS = "forge-production-sessions"
STAGING_SESSIONS = "forge-staging-sessions"


def find_user_by_email(dynamo, table: str, email: str) -> dict | None:
    """Find a user profile by email in DynamoDB."""
    resp = dynamo.scan(
        TableName=table,
        FilterExpression="email = :e",
        ExpressionAttributeValues={":e": {"S": email}},
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_user(dynamo, table: str, user_id: str) -> dict | None:
    """Get a user profile by user_id."""
    resp = dynamo.get_item(TableName=table, Key={"user_id": {"S": user_id}})
    return resp.get("Item")


def copy_profile(dynamo, prod_item: dict, staging_user_id: str, week_override: int = 0):
    """Copy a production profile to staging, remapping the user_id."""
    item = dict(prod_item)
    item["user_id"] = {"S": staging_user_id}
    if week_override > 0:
        item["program_week_override"] = {"N": str(week_override)}

    dynamo.put_item(TableName=STAGING_PROFILES, Item=item)
    name = item.get("name", {}).get("S", "?")
    email = item.get("email", {}).get("S", "?")
    logger.info("  Profile copied: %s (%s) -> staging user_id=%s", name, email, staging_user_id)


def copy_s3_file(s3, prod_key: str, staging_key: str):
    """Copy a file from production to staging S3."""
    try:
        resp = s3.get_object(Bucket=PROD_BUCKET, Key=prod_key)
        body = resp["Body"].read()
        s3.put_object(Bucket=STAGING_BUCKET, Key=staging_key, Body=body, ContentType="application/json")
        logger.info("  S3: %s -> %s", prod_key, staging_key)
        return True
    except s3.exceptions.NoSuchKey:
        logger.info("  S3: %s (not found, skipping)", prod_key)
        return False


def copy_sessions(dynamo, s3, prod_user_id: str, staging_user_id: str):
    """Copy session records and transcripts from production to staging."""
    paginator = dynamo.get_paginator("query")
    copied = 0
    for page in paginator.paginate(
        TableName=PROD_SESSIONS,
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": {"S": prod_user_id}},
    ):
        for item in page.get("Items", []):
            session_id = item["session_id"]["S"]
            # Remap user_id for staging
            item["user_id"] = {"S": staging_user_id}
            dynamo.put_item(TableName=STAGING_SESSIONS, Item=item)

            # Copy transcript from S3
            prod_key = f"sessions/{prod_user_id}/{session_id}.json"
            staging_key = f"sessions/{staging_user_id}/{session_id}.json"
            copy_s3_file(s3, prod_key, staging_key)
            copied += 1

    logger.info("  Copied %d sessions", copied)


def main():
    parser = argparse.ArgumentParser(description="Copy a user from production to staging")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="User's email address")
    group.add_argument("--user-id", help="Production user_id")
    parser.add_argument("--include-sessions", action="store_true", help="Also copy session transcripts")
    parser.add_argument("--week", type=int, default=0, help="Set program_week_override on staging (e.g. --week 2)")
    args = parser.parse_args()

    session = boto3.Session(profile_name="forge")
    dynamo = session.client("dynamodb")
    s3 = session.client("s3")

    # Find the production user
    if args.email:
        logger.info("Looking up %s in production...", args.email)
        prod_item = find_user_by_email(dynamo, PROD_PROFILES, args.email)
        if not prod_item:
            logger.error("User not found in production: %s", args.email)
            sys.exit(1)
    else:
        prod_item = get_user(dynamo, PROD_PROFILES, args.user_id)
        if not prod_item:
            logger.error("User not found in production: %s", args.user_id)
            sys.exit(1)

    prod_user_id = prod_item["user_id"]["S"]
    email = prod_item.get("email", {}).get("S", "?")
    name = prod_item.get("name", {}).get("S", "?")
    logger.info("Found: %s (%s) [%s]\n", name, email, prod_user_id)

    # Check if user already exists on staging (by email)
    staging_item = find_user_by_email(dynamo, STAGING_PROFILES, email)
    if staging_item:
        staging_user_id = staging_item["user_id"]["S"]
        logger.info("User already exists on staging: %s", staging_user_id)
    else:
        # Use the same user_id on staging (they'll get created on first login)
        staging_user_id = prod_user_id
        logger.info("User not on staging yet, will use prod user_id: %s", staging_user_id)

    # Copy profile
    logger.info("\nStep 1: Copying profile...")
    copy_profile(dynamo, prod_item, staging_user_id, args.week)

    # Copy intake responses
    logger.info("\nStep 2: Copying intake responses...")
    prod_key = f"profiles/{prod_user_id}/intake-responses.json"
    staging_key = f"profiles/{staging_user_id}/intake-responses.json"
    copy_s3_file(s3, prod_key, staging_key)

    # Copy weekly briefing if it exists
    prod_key = f"profiles/{prod_user_id}/weekly-briefing.json"
    staging_key = f"profiles/{staging_user_id}/weekly-briefing.json"
    copy_s3_file(s3, prod_key, staging_key)

    # Copy sessions if requested
    if args.include_sessions:
        logger.info("\nStep 3: Copying sessions and transcripts...")
        copy_sessions(dynamo, s3, prod_user_id, staging_user_id)
    else:
        logger.info("\nStep 3: Skipping sessions (use --include-sessions to copy)")

    logger.info("\n=== Done ===")
    logger.info("  Staging user_id: %s", staging_user_id)
    logger.info("  Email: %s", email)
    if args.week:
        logger.info("  Week override: %d", args.week)
    logger.info("\n  To masquerade, open staging and run in browser console:")
    logger.info("    localStorage.setItem('forge-masquerade', '%s')", email)
    logger.info("  Then refresh the page.")


if __name__ == "__main__":
    main()
