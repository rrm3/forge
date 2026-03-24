"""PyArrow schemas for LanceDB collections.

Forge has two built-in collections: curriculum (training content) and profiles
(people). Each schema includes a 1024-dim float32 vector column for Cohere
Embed v3 embeddings.
"""

import pyarrow as pa

# All embeddings use Cohere Embed v3 (1024 dimensions)
VECTOR_DIM = 1024
VECTOR_TYPE = pa.list_(pa.float32(), VECTOR_DIM)


CURRICULUM_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("document_key", pa.string(), nullable=False),
        pa.field("filename", pa.string(), nullable=False),
        pa.field("category", pa.string()),
        pa.field("difficulty", pa.string()),
        pa.field("chunk_index", pa.int32(), nullable=False),
        pa.field("content", pa.string(), nullable=False),
        pa.field("heading_path", pa.string()),  # JSON array
        pa.field("metadata", pa.string()),  # JSON blob
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("vector", VECTOR_TYPE),
    ]
)

PROFILES_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("name", pa.string()),
        pa.field("title", pa.string()),
        pa.field("department", pa.string()),
        pa.field("content", pa.string(), nullable=False),
        pa.field("metadata", pa.string()),  # JSON blob
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("vector", VECTOR_TYPE),
    ]
)

DEPARTMENT_RESOURCES_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("document_id", pa.string()),
        pa.field("department", pa.string()),
        pa.field("section", pa.string()),
        pa.field("source_file", pa.string()),
        pa.field("content", pa.string(), nullable=False),
        pa.field("metadata", pa.string()),
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("vector", VECTOR_TYPE),
    ]
)

TIPS_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("tip_id", pa.string(), nullable=False),
        pa.field("title", pa.string()),
        pa.field("category", pa.string()),
        pa.field("content", pa.string(), nullable=False),
        pa.field("metadata", pa.string()),  # JSON blob
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("vector", VECTOR_TYPE),
    ]
)

# Maps collection name -> schema for auto-creation
BUILTIN_SCHEMAS: dict[str, pa.Schema] = {
    "curriculum": CURRICULUM_SCHEMA,
    "profiles": PROFILES_SCHEMA,
    "department_resources": DEPARTMENT_RESOURCES_SCHEMA,
    "tips": TIPS_SCHEMA,
}

# Maps collection name -> the field used as document-level ID for upsert
DOCUMENT_ID_FIELDS: dict[str, str] = {
    "curriculum": "document_key",
    "profiles": "user_id",
    "department_resources": "document_id",
    "tips": "tip_id",
}
