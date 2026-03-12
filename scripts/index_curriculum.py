#!/usr/bin/env python3
"""Curriculum indexer CLI for Forge.

Indexes curriculum content (Markdown, text, PDF) into LanceDB.

Usage:
  python scripts/index_curriculum.py --local ./test-curriculum/
  python scripts/index_curriculum.py --bucket forge-data --prefix curriculum/
  python scripts/index_curriculum.py --local ./test-curriculum/ --force
  python scripts/index_curriculum.py --local ./test-curriculum/ --dry-run
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}

MIME_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Index curriculum content into LanceDB"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--local", metavar="PATH", help="Local directory to scan")
    source.add_argument("--bucket", metavar="NAME", help="S3 bucket name")

    parser.add_argument(
        "--prefix",
        default="curriculum/",
        help="S3 key prefix (default: curriculum/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reindex everything (default: only new/changed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without actually indexing",
    )
    parser.add_argument(
        "--lance-path",
        default="/tmp/lance",
        help="Local LanceDB path (default: /tmp/lance)",
    )
    return parser.parse_args()


def extract_frontmatter_difficulty(content: str) -> str:
    """Extract difficulty from YAML frontmatter if present, else return 'general'."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return "general"

    for line in lines[1:20]:  # only scan first ~20 lines
        if line.strip() == "---":
            break
        if line.lower().startswith("difficulty:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'").lower()
            return value if value else "general"

    return "general"


def get_category(file_path: str, base_path: str) -> str:
    """Derive category from the directory structure.

    For a file at base_path/marketing/foo.md, returns 'marketing'.
    Files directly under base_path get category 'general'.
    """
    rel = os.path.relpath(file_path, base_path)
    parts = Path(rel).parts
    if len(parts) > 1:
        return parts[0]
    return "general"


def get_category_from_s3_key(key: str, prefix: str) -> str:
    """Derive category from S3 key relative to prefix.

    For curriculum/marketing/foo.md with prefix 'curriculum/', returns 'marketing'.
    """
    # Strip leading prefix
    rel = key[len(prefix):] if key.startswith(prefix) else key
    parts = Path(rel).parts
    if len(parts) > 1:
        return parts[0]
    return "general"


def scan_local(directory: str):
    """Yield (file_path, document_id) tuples for supported files under directory."""
    base = os.path.abspath(directory)
    for root, _dirs, files in os.walk(base):
        for fname in sorted(files):
            ext = Path(fname).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                full_path = os.path.join(root, fname)
                # document_id is the relative path from the base directory
                document_id = os.path.relpath(full_path, base)
                yield full_path, document_id


def scan_s3(bucket: str, prefix: str):
    """Yield (s3_key, document_id) tuples for supported S3 objects."""
    import boto3

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            ext = Path(key).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                yield key, key  # document_id is the full S3 key


def read_local_file(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()


def read_s3_file(bucket: str, key: str) -> bytes:
    import boto3

    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


async def run(args):
    from backend.indexer.text_extraction import extract_text
    from backend.lance.indexing import index_document

    # Override lance_local_path via env so get_lance_connection picks it up
    os.environ["LANCE_LOCAL_PATH"] = args.lance_path
    os.environ["LANCE_BACKEND"] = "local"

    # Reload settings after env override
    import importlib
    import backend.config as config_module
    importlib.reload(config_module)
    # Also reload connection so it picks up the fresh settings
    import backend.lance.connection as conn_module
    importlib.reload(conn_module)

    total_files = 0
    total_chunks = 0
    total_errors = 0
    start_all = time.monotonic()

    if args.local:
        base_path = os.path.abspath(args.local)
        if not os.path.isdir(base_path):
            logger.error(f"Directory not found: {base_path}")
            sys.exit(1)

        items = list(scan_local(base_path))
        logger.info(f"Found {len(items)} file(s) under {base_path}")

        for file_path, document_id in items:
            ext = Path(file_path).suffix.lower()
            mime_type = MIME_TYPES[ext]
            filename = os.path.basename(file_path)
            category = get_category(file_path, base_path)

            content_bytes = read_local_file(file_path)
            text = extract_text(content_bytes, mime_type)
            if text is None:
                logger.warning(f"  SKIP {document_id} - text extraction failed")
                total_errors += 1
                continue

            difficulty = extract_frontmatter_difficulty(text)

            if args.dry_run:
                print(
                    f"  [dry-run] would index: {document_id}"
                    f"  (category={category}, difficulty={difficulty},"
                    f" {len(text)} chars)"
                )
                total_files += 1
                continue

            t0 = time.monotonic()
            result = await index_document(
                collection="curriculum",
                content=text,
                scope_path="curriculum",
                document_id=document_id,
                extra_fields={
                    "filename": filename,
                    "category": category,
                    "difficulty": difficulty,
                },
            )
            elapsed = time.monotonic() - t0

            if result["error"]:
                logger.error(f"  ERROR {document_id}: {result['error']}")
                total_errors += 1
            else:
                chunks = result["chunk_count"]
                logger.info(
                    f"  OK {document_id} - {chunks} chunk(s) in {elapsed:.2f}s"
                    f" (category={category}, difficulty={difficulty})"
                )
                total_files += 1
                total_chunks += chunks

    else:
        # S3 mode
        items = list(scan_s3(args.bucket, args.prefix))
        logger.info(f"Found {len(items)} file(s) in s3://{args.bucket}/{args.prefix}")

        for s3_key, document_id in items:
            ext = Path(s3_key).suffix.lower()
            mime_type = MIME_TYPES[ext]
            filename = os.path.basename(s3_key)
            category = get_category_from_s3_key(s3_key, args.prefix)

            content_bytes = read_s3_file(args.bucket, s3_key)
            text = extract_text(content_bytes, mime_type)
            if text is None:
                logger.warning(f"  SKIP {document_id} - text extraction failed")
                total_errors += 1
                continue

            difficulty = extract_frontmatter_difficulty(text)

            if args.dry_run:
                print(
                    f"  [dry-run] would index: {document_id}"
                    f"  (category={category}, difficulty={difficulty},"
                    f" {len(text)} chars)"
                )
                total_files += 1
                continue

            t0 = time.monotonic()
            result = await index_document(
                collection="curriculum",
                content=text,
                scope_path="curriculum",
                document_id=document_id,
                extra_fields={
                    "filename": filename,
                    "category": category,
                    "difficulty": difficulty,
                },
            )
            elapsed = time.monotonic() - t0

            if result["error"]:
                logger.error(f"  ERROR {document_id}: {result['error']}")
                total_errors += 1
            else:
                chunks = result["chunk_count"]
                logger.info(
                    f"  OK {document_id} - {chunks} chunk(s) in {elapsed:.2f}s"
                    f" (category={category}, difficulty={difficulty})"
                )
                total_files += 1
                total_chunks += chunks

    total_elapsed = time.monotonic() - start_all

    print()
    print("Summary")
    print(f"  Files indexed : {total_files}")
    if not args.dry_run:
        print(f"  Total chunks  : {total_chunks}")
        print(f"  Errors        : {total_errors}")
    print(f"  Time          : {total_elapsed:.2f}s")


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
