"""LanceDB search with hybrid (FTS + vector) retrieval.

Supports text (FTS), vector (embedding similarity), and hybrid search modes.
Includes score gap filtering and match context extraction.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime

from backend.lance.connection import get_lance_connection

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from LanceDB."""

    content: str
    match_context: str
    score: float
    source: str  # Collection name
    metadata: dict = field(default_factory=dict)
    vector_score: float | None = None
    fts_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


async def search(
    query: str,
    scope_path: str,
    collection: str,
    limit: int = 20,
    filter_expr: str | None = None,
    rerank: bool = True,
    min_score: float = 0.1,
) -> dict:
    """Search a LanceDB collection with hybrid retrieval.

    Uses FTS + vector hybrid search with RRF reranking, then optionally
    applies Cohere cross-encoder reranking. Falls back to vector-only
    if hybrid search fails.

    Args:
        query: Search query text
        scope_path: LanceDB scope path
        collection: Collection name to search
        limit: Maximum results to return (capped at 50)
        filter_expr: Optional LanceDB filter expression
        rerank: Whether to apply Cohere cross-encoder reranking
        min_score: Minimum rerank score threshold (results below are dropped)

    Returns:
        Dict with summary, results array, and error field
    """
    try:
        limit = min(max(1, limit), 50)

        db = get_lance_connection(scope_path)

        try:
            table = await asyncio.to_thread(db.open_table, collection)
        except Exception as e:
            logger.warning(f"Collection '{collection}' not found: {e}")
            return {
                "summary": f"Collection '{collection}' not found",
                "results": [],
                "error": str(e),
            }

        # Try hybrid search, fall back to vector-only
        results = await _hybrid_search(table, query, collection, limit, filter_expr)

        if not results:
            return {
                "summary": f"No results found for '{query}'",
                "results": [],
                "error": None,
            }

        # Preserve original RRF scores
        for r in results:
            r.rrf_score = r.score

        # Apply Cohere reranking
        if rerank and results:
            from backend.lance.reranking import rerank as rerank_fn

            t_start = time.monotonic()
            rerank_results = await rerank_fn(
                query=query,
                documents=[r.content for r in results],
                top_n=limit,
            )
            logger.info(
                "rerank elapsed=%.0fms docs=%d",
                (time.monotonic() - t_start) * 1000,
                len(results),
            )
            if rerank_results is not None:
                reranked = []
                for orig_idx, rerank_score in rerank_results:
                    if orig_idx < len(results):
                        r = results[orig_idx]
                        r.rerank_score = rerank_score
                        r.score = rerank_score
                        reranked.append(r)
                results = reranked

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        # Relevance filtering (threshold + score gap)
        has_rerank = any(r.rerank_score is not None for r in results)
        if has_rerank:
            if min_score > 0:
                results = [r for r in results if r.score >= min_score]

            if len(results) >= 2:
                gap_idx = _find_score_gap(results)
                if gap_idx is not None:
                    results = results[: gap_idx + 1]

        # Format output
        formatted = []
        for i, r in enumerate(results[:limit]):
            entry = {
                "source": r.source,
                "score": round(r.score, 4),
                "metadata": r.metadata,
                "match_context": r.match_context,
            }
            if r.vector_score is not None:
                entry["vector_score"] = round(r.vector_score, 4)
            if r.fts_score is not None:
                entry["fts_score"] = round(r.fts_score, 4)
            if r.rrf_score is not None:
                entry["rrf_score"] = round(r.rrf_score, 4)
            if r.rerank_score is not None:
                entry["rerank_score"] = round(r.rerank_score, 4)
            # Top 5 results get full content
            if i < 5:
                entry["content"] = r.content
            formatted.append(entry)

        sources = list(dict.fromkeys(r.source for r in results[:limit]))
        summary = f"Found {len(formatted)} results for '{query}':\n"
        for r in formatted[:10]:
            preview = r.get("match_context", "")[:200]
            summary += f"  * [{r['source']}] (score: {r['score']}): {preview}\n"

        return {
            "summary": summary,
            "results": formatted,
            "error": None,
        }

    except Exception as e:
        logger.exception("LanceDB search failed")
        return {
            "summary": f"Search failed: {e}",
            "results": [],
            "error": str(e),
        }


async def _hybrid_search(
    table,
    query: str,
    collection: str,
    limit: int,
    filter_expr: str | None = None,
) -> list[SearchResult]:
    """Hybrid search combining FTS and vector via RRF reranker.

    Falls back to vector-only if hybrid mode isn't supported.
    """
    from backend.indexer.embeddings import generate_embedding

    try:
        t0 = time.monotonic()
        query_embedding = await generate_embedding(query, input_type="search_query")
        t_embed = time.monotonic()

        from lancedb.rerankers import RRFReranker

        reranker = RRFReranker(return_score="all")

        builder = table.search(query_type="hybrid").vector(query_embedding).text(query)
        builder = builder.rerank(reranker)
        builder = builder.limit(limit)
        if filter_expr:
            builder = builder.where(filter_expr)

        rows = await asyncio.to_thread(builder.to_list)
        t_search = time.monotonic()
        logger.info(
            "hybrid_search collection=%s embed=%.0fms search=%.0fms rows=%d",
            collection,
            (t_embed - t0) * 1000,
            (t_search - t_embed) * 1000,
            len(rows),
        )
        return _rows_to_results(rows, collection, query)

    except Exception as e:
        logger.warning(f"Hybrid search failed for '{collection}', falling back to vector: {e}")
        return await _vector_search(table, query, collection, limit, filter_expr)


async def _vector_search(
    table,
    query: str,
    collection: str,
    limit: int,
    filter_expr: str | None = None,
) -> list[SearchResult]:
    """Vector similarity search using embeddings."""
    from backend.indexer.embeddings import generate_embedding

    try:
        query_embedding = await generate_embedding(query, input_type="search_query")

        builder = table.search(query_embedding, query_type="vector")
        builder = builder.limit(limit)
        if filter_expr:
            builder = builder.where(filter_expr)

        rows = await asyncio.to_thread(builder.to_list)
        return _rows_to_results(rows, collection, query)

    except Exception as e:
        logger.warning(f"Vector search failed for '{collection}': {e}")
        return []


def _make_serializable(value):
    """Convert a value to a JSON-serializable type."""
    if isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _rows_to_results(rows: list[dict], collection: str, query: str = "") -> list[SearchResult]:
    """Convert LanceDB result rows to SearchResult objects.

    With RRFReranker(return_score="all"), rows contain:
    * _relevance_score: combined RRF score
    * _distance: vector similarity distance (lower = more similar)
    * _score: FTS relevance score (higher = more relevant)
    """
    results = []
    for row in rows:
        content = str(row.get("content", ""))

        # Primary score
        score = 0.0
        if "_relevance_score" in row:
            score = float(row["_relevance_score"])
        elif "_score" in row:
            score = float(row["_score"])
        elif "_distance" in row:
            score = 1.0 / (1.0 + float(row["_distance"]))

        # Individual scores
        vector_score = None
        fts_score = None
        if "_distance" in row:
            try:
                dist = float(row["_distance"])
                vector_score = 1.0 / (1.0 + dist)
            except (TypeError, ValueError):
                pass
        if "_score" in row:
            try:
                fts_score = float(row["_score"])
            except (TypeError, ValueError):
                pass

        match_context = _extract_match_context(content, query) if query else content[:500]

        # Collect metadata (exclude internal and large fields)
        meta = {}
        skip_keys = {"content", "vector", "_distance", "_score", "_relevance_score", "id"}
        for k, v in row.items():
            if k not in skip_keys and v is not None:
                meta[k] = _make_serializable(v)

        results.append(
            SearchResult(
                content=content,
                match_context=match_context,
                score=score,
                source=collection,
                metadata=meta,
                vector_score=vector_score,
                fts_score=fts_score,
            )
        )

    return results


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n\n+")


def _extract_match_context(content: str, query: str, max_chars: int = 500) -> str:
    """Extract the most relevant sentences from content based on query keywords.

    Uses keyword overlap scoring to pick the best 2-3 sentences,
    preserving document order. Falls back to truncation if extraction fails.
    """
    if not content or not query:
        return content[:max_chars] if content else ""

    try:
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(content) if s.strip()]
        if len(sentences) <= 2:
            return content[:max_chars]

        query_words = set(query.lower().split())
        scored = []
        for i, sentence in enumerate(sentences):
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)
            scored.append((i, overlap, sentence))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_indices = sorted(s[0] for s in scored[:3])

        selected = [sentences[i] for i in top_indices]
        result = " ... ".join(selected)

        if len(result) > max_chars:
            result = result[:max_chars]

        return result
    except Exception:
        return content[:max_chars]


def _find_score_gap(results: list[SearchResult], min_drop_ratio: float = 0.4) -> int | None:
    """Find the index of the last result before the largest relative score drop.

    Returns the index to cut at (inclusive), or None if no significant gap found.
    A gap is significant when the relative drop exceeds min_drop_ratio (40%).
    """
    if len(results) < 2:
        return None

    best_idx = -1
    best_ratio = 0.0

    for i in range(len(results) - 1):
        current = results[i].score
        nxt = results[i + 1].score
        if current <= 0:
            continue
        drop = (current - nxt) / current
        if drop > best_ratio:
            best_ratio = drop
            best_idx = i

    if best_idx < 0 or best_ratio < min_drop_ratio:
        return None

    return best_idx
