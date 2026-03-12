"""Embedding generation using Cohere Embed v3 via AWS Bedrock.

Simplified version for forge: no BYOK credentials, no token usage repo.
Cost is logged but not tracked to a database.
"""

import asyncio
import json
import logging
import re

import boto3

logger = logging.getLogger(__name__)

_bedrock_clients: dict[str, object] = {}


def _bedrock_client(region: str):
    """Get or create a cached Bedrock client for the given region."""
    if region not in _bedrock_clients:
        _bedrock_clients[region] = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_clients[region]


# Matches Markdown images with base64 data URIs
_BASE64_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\(data:image/[^)]+\)")


def strip_base64_images(text: str) -> str:
    """Replace base64 image references in Markdown with [image] placeholder.

    Ensures embedding vectors represent text semantics, not base64 noise.
    """
    return _BASE64_IMAGE_MD_RE.sub("[image]", text)


# Cohere Embed v3 model ID for Bedrock
COHERE_MODEL_ID = "cohere.embed-english-v3"

# Embedding dimension for Cohere Embed v3
EMBEDDING_DIMENSION = 1024


def _estimate_tokens(text: str) -> int:
    """Estimate Cohere token count from text length (~4 chars per token)."""
    return max(1, len(text) // 4)


async def generate_embedding(
    text: str,
    input_type: str = "search_document",
    region: str = "us-east-1",
) -> list[float]:
    """Generate embedding using Cohere Embed v3 via Bedrock.

    Args:
        text: Text to embed (max ~500 tokens for optimal results)
        input_type: "search_document" for indexing, "search_query" for queries
        region: AWS region for Bedrock

    Returns:
        List of 1024 floats representing the embedding vector
    """
    valid_input_types = {"search_document", "search_query"}
    if input_type not in valid_input_types:
        raise ValueError(f"input_type must be one of {valid_input_types}, got: {input_type}")

    # Strip base64 images before embedding
    text = strip_base64_images(text)

    # Truncate if too long (~512 token limit, rough 4 chars/token)
    max_chars = 2000
    if len(text) > max_chars:
        logger.warning(f"Truncating text from {len(text)} to {max_chars} chars for embedding")
        text = text[:max_chars]

    loop = asyncio.get_event_loop()
    embedding, input_tokens = await loop.run_in_executor(
        None,
        lambda: _generate_embedding_sync(text, input_type, region),
    )

    cost = input_tokens * 0.0000001  # ~$0.10 per 1M tokens
    logger.debug(f"Embedding: {input_tokens} tokens, est. cost ${cost:.6f}")

    return embedding


def _generate_embedding_sync(
    text: str,
    input_type: str,
    region: str,
) -> tuple[list[float], int]:
    """Synchronous embedding generation. Returns (embedding, input_tokens)."""
    client = _bedrock_client(region)

    request_body = {
        "texts": [text],
        "input_type": input_type,
        "truncate": "END",
    }

    response = client.invoke_model(
        modelId=COHERE_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())

    # Bedrock doesn't return Cohere's billed_units, estimate from text length
    input_tokens = _estimate_tokens(text)

    embeddings = response_body.get("embeddings", [])
    if not embeddings or not embeddings[0]:
        raise ValueError("No embedding returned from Cohere")

    embedding = embeddings[0]

    if len(embedding) != EMBEDDING_DIMENSION:
        logger.warning(
            f"Unexpected embedding dimension: {len(embedding)}, expected {EMBEDDING_DIMENSION}"
        )

    return embedding, input_tokens


async def generate_embeddings_batch(
    texts: list[str],
    input_type: str = "search_document",
    batch_size: int = 96,
    region: str = "us-east-1",
) -> list[list[float]]:
    """Generate embeddings for multiple texts in batches.

    Cohere Embed v3 supports batch requests (max 96 texts per call).

    Args:
        texts: List of texts to embed
        input_type: "search_document" or "search_query"
        batch_size: Texts per batch (max 96 for Cohere)
        region: AWS region for Bedrock

    Returns:
        List of embedding vectors, one per input text
    """
    all_embeddings: list[list[float]] = []
    total_input_tokens = 0

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        # Strip base64 images and truncate each text
        max_chars = 2000
        batch = [strip_base64_images(t) for t in batch]
        batch = [t[:max_chars] if len(t) > max_chars else t for t in batch]

        loop = asyncio.get_event_loop()
        batch_embeddings, input_tokens = await loop.run_in_executor(
            None,
            lambda b=batch: _generate_embeddings_batch_sync(b, input_type, region),
        )
        all_embeddings.extend(batch_embeddings)
        total_input_tokens += input_tokens

    cost = total_input_tokens * 0.0000001
    logger.debug(f"Batch embedding: {total_input_tokens} tokens, est. cost ${cost:.6f}")

    return all_embeddings


def _generate_embeddings_batch_sync(
    texts: list[str],
    input_type: str,
    region: str,
) -> tuple[list[list[float]], int]:
    """Synchronous batch embedding generation. Returns (embeddings, input_tokens)."""
    client = _bedrock_client(region)

    request_body = {
        "texts": texts,
        "input_type": input_type,
        "truncate": "END",
    }

    response = client.invoke_model(
        modelId=COHERE_MODEL_ID,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    embeddings = response_body.get("embeddings", [])

    input_tokens = sum(_estimate_tokens(t) for t in texts)

    if len(embeddings) != len(texts):
        raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")

    return embeddings, input_tokens
