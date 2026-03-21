#!/usr/bin/env python3
"""Index department resource markdown files into LanceDB.

Reads all .md files from department-resources/ directory, chunks them,
and indexes into the 'department_resources' LanceDB table.

Usage:
    # Index locally (dev)
    python scripts/index_department_resources.py

    # Index to S3 (production)
    AWS_PROFILE=acumentum python scripts/index_department_resources.py --target s3

    # Custom source directory
    python scripts/index_department_resources.py --source /path/to/markdown/files
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def chunk_markdown(content: str, max_chunk_size: int = 1500) -> list[dict]:
    """Split markdown into chunks by heading sections."""
    chunks = []
    current_section = ""
    current_content: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_content:
                text = "\n".join(current_content).strip()
                if text:
                    chunks.append({"content": text, "section": current_section})
            current_section = line.lstrip("# ").strip()
            current_content = [line]
        elif line.startswith("# ") and not current_content:
            current_section = line.lstrip("# ").strip()
            current_content = [line]
        else:
            current_content.append(line)

    if current_content:
        text = "\n".join(current_content).strip()
        if text:
            chunks.append({"content": text, "section": current_section})

    # Split chunks that are too large
    split_chunks = []
    for chunk in chunks:
        if len(chunk["content"]) <= max_chunk_size:
            split_chunks.append(chunk)
        else:
            parts = re.split(r"\n(?=### |\n\n)", chunk["content"])
            current = ""
            for part in parts:
                if len(current) + len(part) > max_chunk_size and current:
                    split_chunks.append({"content": current.strip(), "section": chunk["section"]})
                    current = part
                else:
                    current = current + "\n" + part if current else part
            if current.strip():
                split_chunks.append({"content": current.strip(), "section": chunk["section"]})

    return split_chunks


async def index_file(filepath: Path) -> int:
    """Index a single department resource file. Returns number of chunks indexed."""
    from backend.lance.indexing import index_document

    content = filepath.read_text(encoding="utf-8")
    department = filepath.stem

    chunks = chunk_markdown(content)
    count = 0
    errors = 0

    for i, chunk in enumerate(chunks):
        doc_id = f"dept-{department}-{i}"
        try:
            result = await index_document(
                collection="department_resources",
                content=chunk["content"],
                scope_path="department_resources",
                document_id=doc_id,
                extra_fields={
                    "department": department,
                    "section": chunk["section"],
                    "source_file": filepath.name,
                },
            )
            if result.get("error"):
                logger.error("  Chunk %s: %s", doc_id, result["error"])
                errors += 1
            else:
                count += 1
        except Exception as e:
            logger.error("  Failed to index chunk %s: %s", doc_id, e)
            errors += 1

    if errors:
        logger.warning("  %s: %d chunks OK, %d errors", filepath.name, count, errors)
    return count


async def main(source_dir: str, target: str):
    from backend.config import settings

    # Override lance backend based on target
    if target == "s3":
        settings.lance_backend = "s3"
        bucket = settings.lance_s3_bucket or settings.s3_bucket
        logger.info("Target: S3 (bucket: %s)", bucket)
    else:
        settings.lance_backend = "local"
        logger.info("Target: local (%s)", settings.lance_local_path)

    source = Path(source_dir)
    if not source.is_dir():
        logger.error("Source directory not found: %s", source)
        sys.exit(1)

    md_files = sorted(source.glob("*.md"))
    if not md_files:
        logger.warning("No .md files found in %s", source)
        return

    logger.info("Found %d markdown files in %s", len(md_files), source)

    total = 0
    for filepath in md_files:
        count = await index_file(filepath)
        logger.info("Indexed %s: %d chunks", filepath.name, count)
        total += count

    logger.info("Done. Total chunks indexed: %d from %d files", total, len(md_files))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Index department resources into LanceDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local dev (writes to /tmp/lance/)
  python scripts/index_department_resources.py

  # Production S3 (needs AWS credentials)
  AWS_PROFILE=acumentum python scripts/index_department_resources.py --target s3
        """,
    )
    parser.add_argument(
        "--source",
        default=str(Path(__file__).resolve().parent.parent / "department-resources"),
        help="Path to department resource markdown files (default: ./department-resources/)",
    )
    parser.add_argument(
        "--target",
        choices=["local", "s3"],
        default="local",
        help="Where to write the index: 'local' for /tmp/lance, 's3' for production (default: local)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.source, args.target))
