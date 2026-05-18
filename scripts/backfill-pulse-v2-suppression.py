"""One-off: backfill synthetic v2 pulse-responses entries for v1-only users.

Goal: any user who answered v1 in weeks 4-7 but missed the v2 prompt in Week 8
should NOT be re-prompted in Week 9. Wrap-up suppression dedupes on
(question_id, version) — so we synthesize v2 entries for them.

Synthetic entries are tagged with `"synthetic": true` and `level: null` so
they're cleanly filterable in any future analytics consumer.

This script:
1. Iterates every user with a profile on disk.
2. Pulls their pulse-responses.json from S3.
3. If they have a (qid, v1) record but no (qid, v2) record for progress/impact,
   appends a synthetic v2 entry.
4. Uploads back.

Idempotent.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

BUCKET = "forge-production-data"
AWS_PROFILE = "forge"
QIDS = ["progress", "impact"]
TARGET_VERSION = "v2"
SOURCE_VERSION = "v1"
PROFILES_DIR = "data/analytics/dynamodb/profiles"


def s3_get(uid):
    key = f"profiles/{uid}/pulse-responses.json"
    r = subprocess.run(
        ["aws", "s3", "cp", f"s3://{BUCKET}/{key}", "-", "--quiet"],
        env={**os.environ, "AWS_PROFILE": AWS_PROFILE},
        capture_output=True,
    )
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def s3_put(uid, data):
    key = f"profiles/{uid}/pulse-responses.json"
    body = json.dumps(data, indent=2).encode()
    tmp = f"/tmp/pulse-backfill-{os.getpid()}-{uid[:8]}.json"
    with open(tmp, "wb") as f:
        f.write(body)
    try:
        r = subprocess.run(
            ["aws", "s3", "cp", tmp, f"s3://{BUCKET}/{key}",
             "--content-type", "application/json", "--quiet"],
            env={**os.environ, "AWS_PROFILE": AWS_PROFILE},
            capture_output=True,
        )
        return r.returncode == 0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def process_user(uid):
    """Return (uid, status, n_appended). status in {'unchanged', 'updated', 'missing', 'error'}"""
    records = s3_get(uid)
    if records is None:
        return uid, "missing", 0
    if not isinstance(records, list) or not records:
        return uid, "missing", 0

    # Build qid → set of versions answered
    by_qid_version = {}  # (qid, version) -> earliest record for lineage
    for r in records:
        if not isinstance(r, dict):
            continue
        qid = r.get("question_id")
        ver = r.get("version")
        if qid in QIDS and isinstance(ver, str):
            by_qid_version.setdefault((qid, ver), r)

    additions = []
    now = datetime.now(timezone.utc).isoformat()
    for qid in QIDS:
        has_v1 = (qid, SOURCE_VERSION) in by_qid_version
        has_v2 = (qid, TARGET_VERSION) in by_qid_version
        if has_v1 and not has_v2:
            src = by_qid_version[(qid, SOURCE_VERSION)]
            additions.append({
                "user_id": uid,
                "question_id": qid,
                "version": TARGET_VERSION,
                "level": None,
                "synthetic": True,
                "carried_from_version": SOURCE_VERSION,
                "carried_from_week": src.get("week"),
                "carried_from_answered_at": src.get("answered_at"),
                "backfilled_at": now,
                "reason": "v1->v2 bump suppression",
            })

    if not additions:
        return uid, "unchanged", 0

    records.extend(additions)
    if s3_put(uid, records):
        return uid, "updated", len(additions)
    return uid, "error", 0


def main():
    uids = [f.replace(".json", "") for f in os.listdir(PROFILES_DIR)
            if f.endswith(".json")]
    print(f"Scanning {len(uids)} users for v1-only state needing v2 suppression backfill...")

    by_status = {"updated": [], "unchanged": [], "missing": [], "error": []}
    total_appended = 0

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(process_user, uid): uid for uid in uids}
        for fut in as_completed(futures):
            uid, status, n = fut.result()
            by_status[status].append(uid)
            total_appended += n

    print()
    print("=" * 60)
    print(f"Users with synthetic v2 entries appended: {len(by_status['updated'])}")
    print(f"Total synthetic entries written:          {total_appended}")
    print(f"Users unchanged (already had v2 or no v1): {len(by_status['unchanged'])}")
    print(f"Users with no pulse-responses file:        {len(by_status['missing'])}")
    print(f"Errors:                                    {len(by_status['error'])}")
    if by_status['error']:
        print(f"  failed uids: {by_status['error'][:5]}")


if __name__ == "__main__":
    main()
