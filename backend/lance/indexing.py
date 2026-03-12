"""Document ingestion pipeline for LanceDB collections.

Handles chunking, embedding, and storage of documents. Simplified from
Acumentum: no SQS queue, no collection management CRUD, no schema migration.
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from backend.lance.connection import get_lance_connection
from backend.lance.schemas import BUILTIN_SCHEMAS, DOCUMENT_ID_FIELDS

logger = logging.getLogger(__name__)


async def index_document(
    collection: str,
    content: str,
    scope_path: str,
    metadata: dict | None = None,
    document_id: str | None = None,
    extra_fields: dict | None = None,
    schema=None,
) -> dict:
    """Chunk, embed, and store a document in a LanceDB collection.

    Auto-creates built-in collections on first use. When document_id is
    provided, existing rows with the same document ID are deleted before
    inserting (upsert via delete-then-insert).

    Args:
        collection: Collection name (e.g. "curriculum", "profiles")
        content: Document text content
        scope_path: LanceDB scope path (e.g. "org/acme")
        metadata: Additional metadata as a dict (stored as JSON string)
        document_id: Document-level ID for upsert behavior
        extra_fields: Additional column values to set on each row
        schema: Optional PyArrow schema override (defaults to built-in)

    Returns:
        Dict with summary, chunk_count, and error field
    """
    from backend.indexer.chunking import chunk_markdown
    from backend.indexer.embeddings import generate_embeddings_batch

    try:
        db = get_lance_connection(scope_path)

        # Resolve schema
        if schema is None:
            schema = BUILTIN_SCHEMAS.get(collection)

        # Auto-create table if it doesn't exist
        existing = db.table_names()
        if collection not in existing:
            if schema is None:
                return {
                    "summary": f"Collection '{collection}' does not exist and no schema provided.",
                    "chunk_count": 0,
                    "error": "Collection not found",
                }
            db.create_table(collection, schema=schema)
            logger.info(f"Created LanceDB table '{collection}' at scope '{scope_path}'")

        table = db.open_table(collection)

        # Chunk the content
        chunks = chunk_markdown(content)
        if not chunks:
            return {
                "summary": "No content to index (empty after chunking)",
                "chunk_count": 0,
                "error": None,
            }

        # Generate embeddings
        chunk_texts = [c.text for c in chunks]
        embeddings = await generate_embeddings_batch(chunk_texts, input_type="search_document")

        # Build rows
        now = datetime.now(UTC)
        doc_id_field = DOCUMENT_ID_FIELDS.get(collection, "document_id")
        rows = []

        for i, chunk in enumerate(chunks):
            row = {
                "id": str(uuid.uuid4()),
                "content": chunk.text,
                "created_at": now,
                "metadata": json.dumps(metadata) if metadata else None,
                "vector": embeddings[i],
            }

            # Set document_id field for upsert
            if document_id:
                row[doc_id_field] = document_id

            # Chunk-level metadata for curriculum
            if collection == "curriculum":
                row["chunk_index"] = i
                row["heading_path"] = json.dumps(chunk.heading_path)

            # Apply extra fields
            if extra_fields:
                for k, v in extra_fields.items():
                    if k not in row:
                        row[k] = v

            rows.append(row)

        # Upsert: delete existing rows for this document, then insert
        if document_id:
            try:
                safe_id = document_id.replace("\\", "\\\\").replace('"', '\\"')
                table.delete(f'{doc_id_field} = "{safe_id}"')
            except Exception as e:
                # Table might be empty or field might not exist yet
                logger.debug(f"Delete before upsert skipped: {e}")

        table.add(rows)

        # Create FTS index on content column if table is new
        # (idempotent - LanceDB ignores if index exists)
        try:
            table.create_fts_index("content", replace=True)
        except Exception as e:
            logger.debug(f"FTS index creation skipped: {e}")

        return {
            "summary": f"Indexed {len(chunks)} chunk(s) into '{collection}'",
            "chunk_count": len(chunks),
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Failed to index document into '{collection}'")
        return {
            "summary": f"Failed to index document: {e}",
            "chunk_count": 0,
            "error": str(e),
        }
