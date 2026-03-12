"""Curriculum tools: search curriculum content and retrieve full documents."""

import logging

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

SEARCH_CURRICULUM_SCHEMA = {
    "name": "search_curriculum",
    "description": "Search the curriculum for AI learning materials, guides, and best practices",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "category": {
                "type": "string",
                "description": "Optional category filter",
            },
            "difficulty": {
                "type": "string",
                "enum": ["beginner", "intermediate", "advanced"],
                "description": "Optional difficulty filter",
            },
        },
        "required": ["query"],
    },
}

RETRIEVE_DOCUMENT_SCHEMA = {
    "name": "retrieve_document",
    "description": "Retrieve the full text of a curriculum document by its S3 key",
    "input_schema": {
        "type": "object",
        "properties": {
            "document_key": {
                "type": "string",
                "description": "S3 key of the document to retrieve",
            },
        },
        "required": ["document_key"],
    },
}


async def search_curriculum(
    query: str,
    context: ToolContext,
    category: str | None = None,
    difficulty: str | None = None,
) -> str:
    from backend.lance.search import search

    filters = []
    if category:
        safe = category.replace('"', '\\"')
        filters.append(f'category = "{safe}"')
    if difficulty:
        safe = difficulty.replace('"', '\\"')
        filters.append(f'difficulty = "{safe}"')
    filter_expr = " AND ".join(filters) if filters else None

    result = await search(
        query=query,
        scope_path="curriculum",
        collection="curriculum",
        filter_expr=filter_expr,
    )

    if result.get("error"):
        return f"Search failed: {result['error']}"

    results = result.get("results", [])
    if not results:
        return f"No curriculum materials found for '{query}'."

    lines = [f"Found {len(results)} result(s) for '{query}':\n"]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        title = meta.get("title", "")
        score = r.get("score", 0)
        context_text = r.get("match_context", r.get("content", ""))[:300]
        header = f"{i}. {title}" if title else f"{i}. [score: {score:.3f}]"
        lines.append(header)
        lines.append(f"   {context_text}")
        lines.append("")

    return "\n".join(lines)


async def retrieve_document(document_key: str, context: ToolContext) -> str:
    if context.storage is None:
        return "Storage backend not available."

    data = await context.storage.read(document_key)
    if data is None:
        return f"Document not found: {document_key}"

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return f"Document at '{document_key}' is not readable as text."


def register_curriculum_tools(registry) -> None:
    registry.register(SEARCH_CURRICULUM_SCHEMA, search_curriculum)
    registry.register(RETRIEVE_DOCUMENT_SCHEMA, retrieve_document)
