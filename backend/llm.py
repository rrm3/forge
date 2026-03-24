"""LLM client wrapping LiteLLM for model-agnostic API calls."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import litellm

from backend.config import settings
from backend.models import TokenUsage

logger = logging.getLogger(__name__)

# Transient errors worth retrying with backoff
RETRYABLE_ERRORS = (
    litellm.RateLimitError,
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.APIConnectionError,
)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


def is_retryable_error(exc: Exception) -> bool:
    return isinstance(exc, RETRYABLE_ERRORS)


def classify_llm_error(exc: Exception) -> str:
    """Return a user-facing message for non-retryable LLM errors."""
    if isinstance(exc, litellm.AuthenticationError):
        return "API key rejected by the provider."
    if isinstance(exc, litellm.PermissionDeniedError):
        return "API key lacks permission for this model."
    if isinstance(exc, litellm.NotFoundError):
        return "Model not found or not available with your credentials."
    if isinstance(exc, litellm.BadRequestError):
        detail = str(exc)[:200]
        if detail:
            return f"Provider rejected the request: {detail}"
    return "Internal error processing message."


def _get_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header value if present."""
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None) or {}
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            try:
                return max(1.0, min(float(raw), 60.0))
            except (ValueError, TypeError):
                pass
    return None


@dataclass
class ToolCall:
    """Parsed tool call from LLM response."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Parsed LLM response."""

    content: str | None
    tool_calls: list[ToolCall] | None
    usage: TokenUsage | None = None


async def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    stream: bool = False,
    max_tokens: int | None = None,
    metadata: dict | None = None,
) -> LLMResponse:
    """Call LLM via LiteLLM and return a parsed response.

    Retries on transient errors (rate limits, 503s, connection errors) with
    exponential backoff up to _MAX_RETRIES attempts.

    Args:
        messages: Conversation history as role/content dicts.
        tools: Optional tool definitions in OpenAI format.
        model: Model identifier (defaults to settings.llm_model).
        stream: If True, uses streaming internally (collected before return).

    Returns:
        LLMResponse with content, tool_calls, and usage.

    Raises:
        Exception: Re-raises non-retryable errors after classify_llm_error logging.
    """
    model = model or settings.llm_model

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "aws_region_name": settings.aws_region,
    }
    # In production, uses the Lambda's IAM role (forge account Bedrock).
    # Locally, uses explicit keys from .env if set.
    if settings.bedrock_access_key_id:
        kwargs["aws_access_key_id"] = settings.bedrock_access_key_id
        kwargs["aws_secret_access_key"] = settings.bedrock_secret_access_key
    if tools:
        kwargs["tools"] = tools
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if metadata:
        kwargs["metadata"] = metadata

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            t0 = time.time()
            logger.info(
                "Calling LLM model=%s tools=%d attempt=%d",
                model,
                len(tools) if tools else 0,
                attempt + 1,
            )
            logger.debug("LLM messages: %s", json.dumps(messages, default=str))

            if stream:
                response = await _collect_stream(kwargs)
            else:
                response = await litellm.acompletion(**kwargs)

            elapsed = time.time() - t0
            logger.info("LLM completed in %.1fs", elapsed)
            return _parse_response(response)

        except RETRYABLE_ERRORS as exc:
            last_exc = exc
            delay = _get_retry_after(exc) or (_BASE_DELAY * (2**attempt))
            if attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "Retryable LLM error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("LLM call failed after %d attempts: %s", _MAX_RETRIES, exc)

        except Exception as exc:
            msg = classify_llm_error(exc)
            logger.error("Non-retryable LLM error: %s — %s", exc, msg)
            raise

    raise last_exc  # type: ignore[misc]


async def _collect_stream(kwargs: dict) -> object:
    """Consume a streaming litellm response and return a response-like object."""
    chunks = []
    async for chunk in await litellm.acompletion(**kwargs):
        chunks.append(chunk)
    return litellm.stream_chunk_builder(chunks)


def _parse_response(response) -> LLMResponse:
    """Parse a litellm completion response into LLMResponse."""
    message = response.choices[0].message

    # Parse tool calls
    tool_calls = None
    if message.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
            )
            for tc in message.tool_calls
        ]

    # Extract text content (may be str or list of blocks)
    text_content: str | None = None
    if isinstance(message.content, str):
        text_content = message.content
    elif isinstance(message.content, list):
        parts = []
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        text_content = "".join(parts) or None

    # Extract token usage
    usage = None
    if hasattr(response, "usage") and response.usage:
        usage = TokenUsage(
            prompt_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(response.usage, "total_tokens", 0) or 0,
        )
        logger.debug(
            "Token usage: %d prompt, %d completion, %d total",
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
        )

    return LLMResponse(content=text_content, tool_calls=tool_calls, usage=usage)
