"""Cohere Rerank v3 via AWS Bedrock.

Reranks search results by relevance using a cross-encoder model.
Falls back gracefully if the Bedrock call fails.
"""

import asyncio
import json
import logging

import boto3

logger = logging.getLogger(__name__)

_bedrock_clients: dict[str, object] = {}


def _get_bedrock_client(region: str):
    """Get or create a cached Bedrock client."""
    if region not in _bedrock_clients:
        _bedrock_clients[region] = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_clients[region]


RERANK_MODEL_ID = "cohere.rerank-v3-5:0"
MAX_DOCUMENTS = 1000  # Cohere Rerank limit per call


async def rerank(
    query: str,
    documents: list[str],
    top_n: int,
    region: str = "us-east-1",
) -> list[tuple[int, float]] | None:
    """Rerank documents by relevance to a query using Cohere Rerank v3.

    Args:
        query: The search query
        documents: List of document texts to rerank
        top_n: Number of top results to return
        region: AWS region for Bedrock

    Returns:
        List of (original_index, relevance_score) pairs sorted by score desc,
        or None if reranking fails (caller should keep original ordering).
    """
    if not documents:
        return None

    # Enforce Cohere's document limit
    docs_to_rerank = documents[:MAX_DOCUMENTS]

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: _rerank_sync(query, docs_to_rerank, top_n, region),
        )
        logger.debug(f"Reranked {len(docs_to_rerank)} documents, returning top {top_n}")
        return result
    except Exception:
        logger.warning("Reranking failed, keeping original ordering", exc_info=True)
        return None


def _rerank_sync(
    query: str,
    documents: list[str],
    top_n: int,
    region: str,
) -> list[tuple[int, float]]:
    """Synchronous reranking via Bedrock."""
    client = _get_bedrock_client(region)

    request_body = {
        "api_version": 2,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }

    response = client.invoke_model(
        modelId=RERANK_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())

    # Response format: {"results": [{"index": 0, "relevance_score": 0.95}, ...]}
    results = response_body.get("results", [])

    return [
        (r["index"], float(r["relevance_score"]))
        for r in sorted(results, key=lambda x: x["relevance_score"], reverse=True)
    ]
