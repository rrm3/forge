"""Federated search across multiple LanceDB tables.

Queries multiple tables, deduplicates by content hash, merges ranked
results, and optionally applies name boosting.
"""

import asyncio
import hashlib
import logging

from backend.lance.search import SearchResult, search

logger = logging.getLogger(__name__)

# All available shared tables and their scope paths
SHARED_TABLES = {
    "department_resources": "department_resources",
    "gong_turns": "gong",
    "gong_calls": "gong",
    "dovetail_highlights": "dovetail",
    "dovetail_notes": "dovetail",
    "roadmap": "roadmap",
    "klue_battlecards": "klue",
}

# Name fields for boosting (per table)
NAME_BOOST_FIELDS: dict[str, list[str]] = {
    "gong_turns": ["speaker_name"],
    "gong_calls": ["title"],
    "dovetail_highlights": ["project_name"],
    "dovetail_notes": ["title"],
    "roadmap": ["title", "product"],
    "klue_battlecards": ["competitor", "title"],
    "department_resources": ["department", "section"],
}

NAME_BOOST_FACTOR = 1.25


def _content_hash(text: str) -> str:
    """Hash content for deduplication."""
    return hashlib.md5(text.encode()).hexdigest()


async def federated_search(
    query: str,
    tables: list[str] | None = None,
    limit: int = 20,
    filter_expr: str | None = None,
    rerank: bool = True,
) -> dict:
    """Search across multiple LanceDB tables and merge results.

    Args:
        query: Search query text.
        tables: List of table names to search, or None for all.
        limit: Maximum results to return.
        filter_expr: Optional filter expression (applied to each table).
        rerank: Whether to apply Cohere reranking per table.

    Returns:
        Dict with summary, results array, and error field.
    """
    if tables is None:
        tables = list(SHARED_TABLES.keys())

    # Filter to tables that exist in our registry
    valid_tables = [(t, SHARED_TABLES[t]) for t in tables if t in SHARED_TABLES]

    if not valid_tables:
        return {
            "summary": f"No valid tables specified. Available: {', '.join(SHARED_TABLES.keys())}",
            "results": [],
            "error": "No valid tables",
        }

    # Search each table concurrently
    tasks = []
    for table_name, scope_path in valid_tables:
        tasks.append(
            search(
                query=query,
                scope_path=scope_path,
                collection=table_name,
                limit=limit,
                filter_expr=filter_expr,
                rerank=rerank,
            )
        )

    results_per_table = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results, deduplicate by content hash
    seen_hashes: set[str] = set()
    all_results: list[dict] = []
    errors: list[str] = []

    for i, result in enumerate(results_per_table):
        table_name = valid_tables[i][0]

        if isinstance(result, Exception):
            errors.append(f"{table_name}: {result}")
            continue

        if result.get("error"):
            # Don't treat missing tables as fatal
            if "not found" not in str(result["error"]).lower():
                errors.append(f"{table_name}: {result['error']}")
            continue

        for r in result.get("results", []):
            content = r.get("content", r.get("match_context", ""))
            h = _content_hash(content)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            # Apply name boosting
            score = r.get("score", 0)
            boost_fields = NAME_BOOST_FIELDS.get(table_name, [])
            meta = r.get("metadata", {})
            query_lower = query.lower()
            for field_name in boost_fields:
                val = str(meta.get(field_name, "")).lower()
                if val and any(word in val for word in query_lower.split()):
                    score *= NAME_BOOST_FACTOR

            r["score"] = round(score, 4)
            r["source_table"] = table_name
            all_results.append(r)

    # Sort by score descending
    all_results.sort(key=lambda r: r.get("score", 0), reverse=True)

    # Trim to limit
    all_results = all_results[:limit]

    # Build summary
    table_counts = {}
    for r in all_results:
        t = r.get("source_table", "unknown")
        table_counts[t] = table_counts.get(t, 0) + 1

    summary_parts = [f"Found {len(all_results)} results for '{query}'"]
    if table_counts:
        breakdown = ", ".join(f"{t}: {c}" for t, c in sorted(table_counts.items()))
        summary_parts.append(f"({breakdown})")
    summary = " ".join(summary_parts)

    return {
        "summary": summary,
        "results": all_results,
        "error": "; ".join(errors) if errors else None,
    }
