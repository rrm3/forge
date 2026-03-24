#!/usr/bin/env python3
"""Migrate intake and wrapup session titles to the new naming convention.

Renames:
  intake:  "Getting Started" or "Day 1" → "Day 1 Getting Started"
  wrapup:  "End of Day Wrap Up"         → "Day 1 Wrap-up"

Usage:
    AWS_PROFILE=forge python scripts/migrate_day_one_title.py --table forge-staging-sessions
    AWS_PROFILE=forge python scripts/migrate_day_one_title.py --table forge-production-sessions --execute
"""

import argparse
import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = "forge-sessions"
REGION = "us-east-1"

MIGRATIONS = [
    {
        "description": "intake sessions",
        "filter": Attr("type").eq("intake") & (
            Attr("title").eq("Getting Started") | Attr("title").eq("Day 1")
        ),
        "new_title": "Day 1 Getting Started",
    },
    {
        "description": "wrapup sessions",
        "filter": Attr("type").eq("wrapup") & Attr("title").eq("End of Day Wrap Up"),
        "new_title": "Day 1 Wrap-up",
    },
]


def scan_all(table, filter_expression):
    scan_kwargs = {
        "FilterExpression": filter_expression,
        "ProjectionExpression": "user_id, session_id, title, #t",
        "ExpressionAttributeNames": {"#t": "type"},
    }
    items = []
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return items


def main():
    parser = argparse.ArgumentParser(description="Migrate session titles to Day N naming")
    parser.add_argument("--execute", action="store_true", help="Actually write changes (default is dry-run)")
    parser.add_argument("--table", default=TABLE_NAME, help=f"DynamoDB table name (default: {TABLE_NAME})")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(args.table)

    total_updated = 0

    for migration in MIGRATIONS:
        items = scan_all(table, migration["filter"])
        print(f"\n{migration['description']}: found {len(items)} → \"{migration['new_title']}\"")

        for item in items:
            print(f"  {item['user_id']} / {item['session_id']} (was: \"{item.get('title', '')}\")")

        if not items:
            continue

        if not args.execute:
            continue

        for item in items:
            table.update_item(
                Key={"user_id": item["user_id"], "session_id": item["session_id"]},
                UpdateExpression="SET title = :new_title",
                ExpressionAttributeValues={":new_title": migration["new_title"]},
            )
            total_updated += 1

    if not args.execute:
        print("\nDry-run mode. Run with --execute to apply changes.")
    else:
        print(f"\nUpdated {total_updated} sessions.")


if __name__ == "__main__":
    main()
