"""Search tool: federated search across all LanceDB tables."""

import logging

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

SEARCH_SCHEMA = {
    "name": "search_internal",
    "description": (
        "Search across Digital Science's knowledge base including department resources, "
        "Gong call transcripts, Dovetail user research, product roadmap, and Klue competitive intelligence. "
        "Use this to find relevant information for the user's question."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "tables": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "department_resources",
                        "gong_turns",
                        "gong_calls",
                        "dovetail_highlights",
                        "dovetail_notes",
                        "roadmap",
                        "klue_battlecards",
                    ],
                },
                "description": "Specific tables to search. Omit to search all.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default 20, max 50)",
            },
            "filter_expr": {
                "type": "string",
                "description": "Optional LanceDB filter expression (e.g., 'department = \"marketing\"')",
            },
        },
        "required": ["query"],
    },
}

RETRIEVE_DOCUMENT_SCHEMA = {
    "name": "retrieve_document",
    "description": "Retrieve the full text of a document by its S3 key",
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


async def search_tool(
    query: str,
    context: ToolContext,
    tables: list[str] | None = None,
    limit: int = 20,
    filter_expr: str | None = None,
) -> str:
    """Execute a federated search across LanceDB tables."""
    from backend.lance.federated import federated_search

    result = await federated_search(
        query=query,
        tables=tables,
        limit=limit,
        filter_expr=filter_expr,
    )

    if result.get("error") and not result.get("results"):
        return f"Search failed: {result['error']}"

    results = result.get("results", [])
    if not results:
        return f"No results found for '{query}'."

    lines = [f"Found {len(results)} result(s) for '{query}':\n"]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        source_table = r.get("source_table", r.get("source", ""))
        score = r.get("score", 0)
        context_text = r.get("match_context", r.get("content", ""))[:300]

        # Build header with available metadata
        title = meta.get("title", "")
        department = meta.get("department", "")
        label_parts = []
        if title:
            label_parts.append(title)
        if department:
            label_parts.append(f"[{department}]")
        label_parts.append(f"({source_table}, score: {score:.3f})")
        header = f"{i}. {' '.join(label_parts)}"

        lines.append(header)
        lines.append(f"   {context_text}")
        lines.append("")

    return "\n".join(lines)


async def retrieve_document(document_key: str, context: ToolContext) -> str:
    """Retrieve a document from S3 storage."""
    if context.storage is None:
        return "Storage backend not available."

    data = await context.storage.read(document_key)
    if data is None:
        return f"Document not found: {document_key}"

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return f"Document at '{document_key}' is not readable as text."


def register_search_tools(registry) -> None:
    """Register the general search and retrieve_document tools."""
    registry.register(SEARCH_SCHEMA, search_tool)
    registry.register(RETRIEVE_DOCUMENT_SCHEMA, retrieve_document)
