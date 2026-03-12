"""LanceDB connection management.

LanceDB connections are lightweight, stateless pointers to a storage location.
A shared Session provides an in-memory LRU cache for index and metadata objects,
avoiding redundant S3 fetches across requests.
"""

import logging
from datetime import timedelta

import lancedb
from lancedb import Session

from backend.config import settings

logger = logging.getLogger(__name__)

# Shared cache across all connections in this process.
# LRU-evicted, bounded by these byte limits.
_session = Session(
    index_cache_size_bytes=48 * 1024 * 1024,  # 48 MB
    metadata_cache_size_bytes=48 * 1024 * 1024,  # 48 MB
)


def get_lance_connection(scope_path: str) -> lancedb.DBConnection:
    """Get a LanceDB connection for the given scope path.

    Storage layout:
        Local:  {lance_local_path}/{scope_path}/
        S3:     s3://{bucket}/lance/{scope_path}/

    Args:
        scope_path: Path segment identifying the scope (e.g. "org/acme",
            "curriculum", "profiles/user123")

    Returns:
        lancedb.DBConnection pointing at the scope's storage location
    """
    if settings.lance_backend == "s3":
        bucket = settings.lance_s3_bucket or settings.s3_bucket
        uri = f"s3://{bucket}/lance/{scope_path}"
    else:
        uri = f"{settings.lance_local_path}/{scope_path}"

    return lancedb.connect(
        uri,
        session=_session,
        # Reuse cached manifest if checked within the last 5 seconds.
        read_consistency_interval=timedelta(seconds=5),
    )
