#!/usr/bin/env bash
# Copy a prod user to staging AND remap to the masquerade hash uid.
#
# The base scripts/copy-user-to-staging.py copies under the prod user_id, but
# masquerade derives user_id = sha256(email)[:32]. This wrapper runs that copy
# then remaps profile/intake/sessions/digest to the masq uid so the masquerade
# session actually sees the data.
#
# Usage: scripts/copy-user-for-masquerade.sh <email> <week_override>

set -euo pipefail

EMAIL="${1:?email required}"
WEEK="${2:-0}"

echo "=== Step 1: copy via existing script ==="
AWS_PROFILE=forge uv run python scripts/copy-user-to-staging.py \
  --email "$EMAIL" --week "$WEEK" --include-sessions

echo ""
echo "=== Step 2: remap to masquerade uid (sha256(email)[:32]) ==="
AWS_PROFILE=forge uv run python3 - <<PY
import hashlib, boto3, sys

EMAIL = "$EMAIL"
WEEK = int("$WEEK")
PROD_BUCKET = "forge-production-data"
STAGING_BUCKET = "forge-staging-data"
PROD_PROFILES = "forge-production-profiles"
STAGING_PROFILES = "forge-staging-profiles"
PROD_SESSIONS = "forge-production-sessions"
STAGING_SESSIONS = "forge-staging-sessions"

session = boto3.Session(profile_name="forge", region_name="us-east-1")
ddb = session.client("dynamodb")
s3 = session.client("s3")

masq_uid = hashlib.sha256(EMAIL.lower().encode()).hexdigest()[:32]
print(f"masquerade user_id = {masq_uid}")

# Find prod user_id
resp = ddb.scan(
    TableName=PROD_PROFILES,
    FilterExpression="email = :e",
    ExpressionAttributeValues={":e": {"S": EMAIL}},
)
items = resp.get("Items", [])
if not items:
    print(f"NOT FOUND in prod: {EMAIL}")
    sys.exit(1)
prod_item = items[0]
prod_uid = prod_item["user_id"]["S"]
print(f"prod user_id      = {prod_uid}")

# Copy profile -> masq_uid
prod_item["user_id"] = {"S": masq_uid}
if WEEK > 0:
    prod_item["program_week_override"] = {"N": str(WEEK)}
ddb.put_item(TableName=STAGING_PROFILES, Item=prod_item)
print("  profile remapped -> masq_uid")

# Mirror every per-user S3 artifact under profiles/{prod_uid}/ to
# profiles/{masq_uid}/. Enumerated dynamically (not hardcoded keys) so we
# don't drift as new artifacts land (pulse-responses.json, weekly digests
# beyond week 5, future per-user files, etc.).
prefix = f"profiles/{prod_uid}/"
paginator_s3 = s3.get_paginator("list_objects_v2")
mirrored = 0
for page in paginator_s3.paginate(Bucket=PROD_BUCKET, Prefix=prefix):
    for obj in page.get("Contents", []):
        rel = obj["Key"][len(prefix):]
        if not rel:
            continue
        try:
            body = s3.get_object(Bucket=PROD_BUCKET, Key=obj["Key"])["Body"].read()
            s3.put_object(Bucket=STAGING_BUCKET, Key=f"profiles/{masq_uid}/{rel}", Body=body)
            mirrored += 1
        except Exception as e:
            print(f"  skip {rel}: {e}")
print(f"  profile artifacts mirrored: {mirrored}")

# Copy sessions to masq_uid
paginator = ddb.get_paginator("query")
copied = 0
for page in paginator.paginate(
    TableName=PROD_SESSIONS,
    KeyConditionExpression="user_id = :uid",
    ExpressionAttributeValues={":uid": {"S": prod_uid}},
):
    for item in page.get("Items", []):
        sid = item["session_id"]["S"]
        item["user_id"] = {"S": masq_uid}
        ddb.put_item(TableName=STAGING_SESSIONS, Item=item)
        # session transcript
        src = f"sessions/{prod_uid}/{sid}.json"
        dst = f"sessions/{masq_uid}/{sid}.json"
        try:
            body = s3.get_object(Bucket=PROD_BUCKET, Key=src)["Body"].read()
            s3.put_object(Bucket=STAGING_BUCKET, Key=dst, Body=body)
        except s3.exceptions.NoSuchKey:
            pass
        copied += 1
print(f"  sessions remapped: {copied}")

print()
print(f"=== Done. Masquerade with: localStorage.setItem('forge-masquerade', '{EMAIL}') ===")
PY
