#!/usr/bin/env python3
"""Inspect / diff / restore version history of the S3-managed config.

The company prompt, company objectives, and department configs/prompts are the
live source of truth in S3 (`s3://forge-{env}-data/config/`), edited via the
admin UI and the occasional manual S3 edit. They are NOT git-tracked (the repo
is public and the config carries admin emails + internal prompts). Instead,
**S3 bucket versioning is enabled**, so every change is automatically versioned.

This read-only-by-default helper makes that history usable like git:

  # list every version of a config object (newest first)
  AWS_PROFILE=forge python3 scripts/config-history.py list company-objectives.json
  AWS_PROFILE=forge python3 scripts/config-history.py list departments/technology.json --env staging

  # diff the latest two versions (what changed most recently)
  AWS_PROFILE=forge python3 scripts/config-history.py diff company-objectives.json

  # diff two specific versions (VersionIds from `list`, or 'current')
  AWS_PROFILE=forge python3 scripts/config-history.py diff company-objectives.json --from <vid> --to current

  # restore a prior version (dry-run shows the diff; --apply re-uploads it)
  AWS_PROFILE=forge python3 scripts/config-history.py restore company-objectives.json <vid>
  AWS_PROFILE=forge python3 scripts/config-history.py restore company-objectives.json <vid> --apply

`key` is relative to the `config/` prefix (e.g. `company-objectives.json`,
`departments/technology.json`, `departments/prompt/sales.json`).
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys

import boto3
from botocore.exceptions import ClientError

BUCKETS = {"prod": "forge-production-data", "staging": "forge-staging-data"}


def _s3():
    return boto3.Session(profile_name="forge").client("s3")


def _full_key(key: str) -> str:
    return key if key.startswith("config/") else f"config/{key}"


def _versions(s3, bucket: str, key: str) -> list[dict]:
    """All versions of exactly `key`, newest first."""
    out = []
    paginator = s3.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket, Prefix=key):
        for v in page.get("Versions", []):
            if v["Key"] == key:
                out.append(v)
    out.sort(key=lambda v: v["LastModified"], reverse=True)
    return out


def _get_body(s3, bucket: str, key: str, version_id: str | None) -> bytes:
    kw = {"Bucket": bucket, "Key": key}
    if version_id and version_id not in ("current", "latest"):
        kw["VersionId"] = version_id
    return s3.get_object(**kw)["Body"].read()


def _pretty(body: bytes) -> str:
    try:
        return json.dumps(json.loads(body.decode()), indent=2, sort_keys=True)
    except Exception:
        return body.decode(errors="replace")


def cmd_list(s3, bucket, key, args):
    versions = _versions(s3, bucket, key)
    if not versions:
        print(f"No versions found for {key} in {bucket}")
        return 1
    print(f"{len(versions)} version(s) of {key} ({bucket}):")
    for i, v in enumerate(versions):
        latest = " (current)" if v.get("IsLatest") else ""
        print(f"  [{i}] {v['LastModified'].isoformat()}  {v['VersionId']}  {v['Size']}b{latest}")
    return 0


def _resolve(versions, ref):
    """Resolve a --from/--to ref: a VersionId, 'current'/'latest', or int index."""
    if ref in (None, "current", "latest"):
        return None  # current
    if ref.isdigit():
        return versions[int(ref)]["VersionId"]
    return ref  # assume a VersionId


def cmd_diff(s3, bucket, key, args):
    versions = _versions(s3, bucket, key)
    if len(versions) < 1:
        print(f"No versions for {key}")
        return 1
    if args.to is None and args.from_ is None:
        # default: latest two
        to_vid = None
        from_vid = versions[1]["VersionId"] if len(versions) > 1 else None
        if from_vid is None:
            print("Only one version exists; nothing to diff.")
            return 0
    else:
        to_vid = _resolve(versions, args.to)
        from_vid = _resolve(versions, args.from_)
    a = _pretty(_get_body(s3, bucket, key, from_vid)).splitlines(keepends=True)
    b = _pretty(_get_body(s3, bucket, key, to_vid)).splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        a, b,
        fromfile=f"{key}@{from_vid or 'current'}",
        tofile=f"{key}@{to_vid or 'current'}",
    ))
    if not diff:
        print("(no differences)")
    else:
        sys.stdout.writelines(diff)
    return 0


def cmd_restore(s3, bucket, key, args):
    body = _get_body(s3, bucket, key, args.version_id)
    cur = _pretty(_get_body(s3, bucket, key, None)).splitlines(keepends=True)
    tgt = _pretty(body).splitlines(keepends=True)
    diff = list(difflib.unified_diff(cur, tgt, fromfile=f"{key}@current", tofile=f"{key}@{args.version_id}"))
    if not diff:
        print("Target version is identical to current; nothing to restore.")
        return 0
    print(f"Restoring {key} ({bucket}) to version {args.version_id} would change:\n")
    sys.stdout.writelines(diff)
    if not args.apply:
        print("\n\n(dry-run) Re-run with --apply to write this version as current.")
        return 0
    ctype = "application/json" if key.endswith(".json") else "text/plain"
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=ctype)
    print(f"\n\nRestored {key} to version {args.version_id} (new current version written).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="S3 config version history (list/diff/restore)")
    ap.add_argument("--env", choices=["prod", "staging"], default="prod")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list versions of a config key")
    p_list.add_argument("key")

    p_diff = sub.add_parser("diff", help="diff two versions (default: latest two)")
    p_diff.add_argument("key")
    p_diff.add_argument("--from", dest="from_", help="VersionId, index, or 'current'")
    p_diff.add_argument("--to", help="VersionId, index, or 'current' (default current)")

    p_rest = sub.add_parser("restore", help="restore a prior version (dry-run unless --apply)")
    p_rest.add_argument("key")
    p_rest.add_argument("version_id")
    p_rest.add_argument("--apply", action="store_true", help="actually write it (default dry-run)")

    args = ap.parse_args()
    bucket = BUCKETS[args.env]
    key = _full_key(args.key)
    s3 = _s3()
    try:
        return {"list": cmd_list, "diff": cmd_diff, "restore": cmd_restore}[args.cmd](s3, bucket, key, args)
    except ClientError as e:
        print(f"AWS error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
