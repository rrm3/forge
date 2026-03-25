"""Allowed email domain enforcement.

Loads a list of permitted email domains from a JSON config file
(S3 in production, local filesystem in dev). Cached in memory with
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
_cached_domains: set[str] = set()
_cache_expires_at: float = 0


def _load_from_local(path: str) -> set[str]:
    """Load allowed domains from a local JSON file."""
    p = Path(path)
    if not p.exists():
        logger.warning("Allowed domains file not found: %s", path)
        return set()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read allowed domains from %s: %s", path, e)
        return set()
    return _parse_domains(data, path)


def _parse_domains(data: dict, source: str) -> set[str]:
    """Extract and validate domains from parsed JSON config."""
    if not isinstance(data, dict) or "domains" not in data:
        logger.error("Allowed domains config missing 'domains' key (source: %s)", source)
        return set()
    domains = {d.strip().lower() for d in data.get("domains", []) if isinstance(d, str) and d.strip()}
    if not domains:
        logger.error("Allowed domains config has empty domain list (source: %s)", source)
    return domains


def _load_from_s3(bucket: str, key: str) -> set[str]:
    """Load allowed domains from an S3 JSON file."""
    import boto3
    s3 = boto3.client("s3")
    resp = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(resp["Body"].read())
    return _parse_domains(data, f"s3://{bucket}/{key}")


def _load_domains() -> set[str]:
    """Load domains from the configured source."""
    if settings.dev_mode:
        path = settings.allowed_domains_local_path
        if not path:
            # Default to config/allowed-domains.json relative to project root
            path = str(Path(__file__).parent.parent / "config" / "allowed-domains.json")
        try:
            return _load_from_local(path)
        except Exception:
            logger.warning("Failed to load allowed domains from local file", exc_info=True)
            return set()

    try:
        return _load_from_s3(settings.s3_bucket, settings.allowed_domains_s3_key)
    except Exception:
        logger.warning("Failed to load allowed domains from S3", exc_info=True)
        return set()


def get_allowed_domains() -> set[str]:
    """Return the current set of allowed email domains, refreshing if stale."""
    global _cached_domains, _cache_expires_at

    now = time.monotonic()
    if _cached_domains and now < _cache_expires_at:
        return _cached_domains

    domains = _load_domains()
    if domains:
        _cached_domains = domains
        _cache_expires_at = now + _CACHE_TTL_SECONDS
        logger.info("Loaded %d allowed email domains", len(domains))
    elif _cached_domains:
        # Keep stale cache rather than locking everyone out
        logger.warning("Failed to refresh allowed domains, keeping previous %d domains", len(_cached_domains))
    else:
        logger.error("No allowed domains loaded - all logins will be rejected")

    return _cached_domains


def is_domain_allowed(email: str) -> bool:
    """Check whether an email address belongs to an allowed domain."""
    allowed = get_allowed_domains()
    if not allowed:
        # If no domains configured at all, reject (fail-closed)
        return False
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return domain in allowed
