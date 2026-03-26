"""Allowed organization enforcement.

Loads a list of permitted DS Identity organization IDs from a JSON config
file (S3 in production, local filesystem in dev). Cached in memory with
a TTL so updates take effect without restarting the service.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300  # 5 minutes
_cached_org_ids: set[str] = set()
_cache_expires_at: float = 0


def _load_from_local(path: str) -> set[str]:
    """Load allowed org IDs from a local JSON file."""
    p = Path(path)
    if not p.exists():
        logger.warning("Allowed orgs file not found: %s", path)
        return set()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read allowed orgs from %s: %s", path, e)
        return set()
    return _parse_org_ids(data, path)


def _parse_org_ids(data: dict, source: str) -> set[str]:
    """Extract org IDs from parsed JSON config."""
    if not isinstance(data, dict) or "organizations" not in data:
        logger.error("Allowed orgs config missing 'organizations' key (source: %s)", source)
        return set()
    org_ids = set()
    for org in data.get("organizations", []):
        if isinstance(org, dict) and org.get("org_id"):
            org_ids.add(org["org_id"])
    if not org_ids:
        logger.error("Allowed orgs config has no valid org IDs (source: %s)", source)
    return org_ids


def _load_from_s3(bucket: str, key: str) -> set[str]:
    """Load allowed org IDs from an S3 JSON file."""
    import boto3
    s3 = boto3.client("s3")
    resp = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(resp["Body"].read())
    return _parse_org_ids(data, f"s3://{bucket}/{key}")


def _load_org_ids() -> set[str]:
    """Load org IDs from the configured source."""
    if settings.dev_mode:
        path = settings.allowed_orgs_local_path
        if not path:
            path = str(Path(__file__).parent.parent / "config" / "allowed-orgs.json")
        try:
            return _load_from_local(path)
        except Exception:
            logger.warning("Failed to load allowed orgs from local file", exc_info=True)
            return set()

    try:
        return _load_from_s3(settings.s3_bucket, settings.allowed_orgs_s3_key)
    except Exception:
        logger.warning("Failed to load allowed orgs from S3", exc_info=True)
        return set()


def get_allowed_org_ids() -> set[str]:
    """Return the current set of allowed org IDs, refreshing if stale."""
    global _cached_org_ids, _cache_expires_at

    now = time.monotonic()
    if _cached_org_ids and now < _cache_expires_at:
        return _cached_org_ids

    org_ids = _load_org_ids()
    if org_ids:
        _cached_org_ids = org_ids
        _cache_expires_at = now + _CACHE_TTL_SECONDS
        logger.info("Loaded %d allowed organizations", len(org_ids))
    elif _cached_org_ids:
        # Keep stale cache rather than locking everyone out
        logger.warning("Failed to refresh allowed orgs, keeping previous %d orgs", len(_cached_org_ids))
    else:
        logger.error("No allowed organizations loaded - all logins will be rejected")

    return _cached_org_ids


def is_org_allowed(org_id: str | None) -> bool:
    """Check whether an org ID is in the allowed set."""
    if not org_id:
        return False
    allowed = get_allowed_org_ids()
    if not allowed:
        # If no orgs configured at all, reject (fail-closed)
        return False
    return org_id in allowed
