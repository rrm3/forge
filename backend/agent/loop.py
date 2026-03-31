"""Core ReAct loop for the Forge agent.

Alternates between reasoning (LLM responses) and acting (tool execution)
until the LLM provides a final response without tool calls.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import litellm

from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    LoopEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.config import settings
from backend.llm import ToolCall, classify_llm_error, is_retryable_error
from backend.models import TokenUsage
from backend.tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


async def react_loop(
    user_message: str,
    messages: list[dict],
    system_prompt: str,
    tools: ToolRegistry,
    context: ToolContext,
    max_iterations: int = 10,
    cancel_event: asyncio.Event | None = None,
    metadata: dict | None = None,
) -> AsyncGenerator[LoopEvent, None]:
    """Run the ReAct loop, yielding events as they occur.

    Args:
        user_message: The latest user message to process.
        messages: Conversation history in LLM message format. Modified in place.
        system_prompt: System prompt for the LLM.
        tools: Tool registry with schemas and handlers.
        context: Execution context passed to tool handlers.
        max_iterations: Safety limit on tool-use iterations.
        cancel_event: Optional event to signal cancellation.

    Yields:
        LoopEvent instances (TextEvent, ToolCallEvent, ToolResultEvent,
        DoneEvent, or ErrorEvent).
    """
    # Ensure system prompt is the first message
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": system_prompt})
    else:
        messages[0] = {"role": "system", "content": system_prompt}

    # Append the user message
    messages.append({"role": "user", "content": user_message})

    tool_schemas = _format_tool_schemas(tools.get_schemas())
    model = settings.llm_model

    # Accumulate usage across iterations
    acc_prompt = 0
    acc_completion = 0
    acc_total = 0

    for iteration in range(max_iterations):
        # Check cancellation
        if cancel_event and cancel_event.is_set():
            yield DoneEvent(usage=_make_usage(acc_prompt, acc_completion, acc_total))
            return

        try:
            response, text_parts = await _call_llm_streaming(
                messages, tool_schemas, model, metadata=metadata
            )
        except Exception as exc:
            msg = classify_llm_error(exc)
            logger.error("LLM call failed: %s - %s", exc, msg)
            yield ErrorEvent(error=msg)
            return

        # Separate text from previous iteration with a paragraph break
        if iteration > 0 and text_parts:
            yield TextEvent(text="\n\n")

        # Yield text deltas that were collected during streaming
        for part in text_parts:
            yield TextEvent(text=part)

        # Parse the assembled response
        parsed_tool_calls, content, usage = _parse_stream_response(response)

        # Accumulate usage
        if usage:
            acc_prompt += usage.prompt_tokens
            acc_completion += usage.completion_tokens
            acc_total += usage.total_tokens

        # No tool calls -> done
        if not parsed_tool_calls:
            messages.append({"role": "assistant", "content": content or ""})
            yield DoneEvent(
                usage=_make_usage(acc_prompt, acc_completion, acc_total)
            )
            return

        # Build assistant message with tool calls
        assistant_msg: dict = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments)
                        if isinstance(tc.arguments, dict)
                        else tc.arguments,
                    },
                }
                for tc in parsed_tool_calls
            ],
        }
        if content:
            assistant_msg["content"] = content
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in parsed_tool_calls:
            yield ToolCallEvent(
                tool_name=tc.name,
                tool_call_id=tc.id,
                arguments=tc.arguments,
            )

            try:
                result = await tools.execute(tc.name, tc.arguments, context)
            except Exception as exc:
                logger.exception("Tool '%s' failed", tc.name)
                result = f"Error executing {tc.name}: {exc}"

            yield ToolResultEvent(tool_call_id=tc.id, result=result)

            # Append tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result if isinstance(result, str) else json.dumps(result),
                }
            )

        # Check cancellation before next iteration
        if cancel_event and cancel_event.is_set():
            yield DoneEvent(usage=_make_usage(acc_prompt, acc_completion, acc_total))
            return

    # Exhausted iterations
    yield ErrorEvent(error=f"Reached maximum iterations ({max_iterations})")


async def _call_llm_streaming(
    messages: list[dict],
    tools: list[dict],
    model: str,
    metadata: dict | None = None,
) -> tuple[object, list[str]]:
    """Call the LLM with streaming enabled, yielding text deltas as they arrive.

    Returns the assembled response object and a list of text chunks that were
    streamed (so the caller can yield them as TextEvents).

    Retries on transient errors with exponential backoff.
    """
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "aws_region_name": settings.aws_region,
    }
    if settings.bedrock_access_key_id:
        kwargs["aws_access_key_id"] = settings.bedrock_access_key_id
        kwargs["aws_secret_access_key"] = settings.bedrock_secret_access_key
    if tools:
        kwargs["tools"] = tools
    if metadata:
        kwargs["metadata"] = metadata

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            logger.info(
                "Calling LLM model=%s tools=%d attempt=%d stream=True",
                model, len(tools) if tools else 0, attempt + 1,
            )

            chunks = []
            text_parts: list[str] = []

            async for chunk in await litellm.acompletion(**kwargs):
                chunks.append(chunk)
                # Extract text delta for immediate streaming
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and getattr(delta, "content", None):
                    text_parts.append(delta.content)

            # Build a complete response from chunks
            response = litellm.stream_chunk_builder(chunks)
            return response, text_parts

        except Exception as exc:
            if not is_retryable_error(exc) or attempt >= _MAX_RETRIES - 1:
                raise
            last_exc = exc
            delay = _BASE_DELAY * (2 ** attempt)
            logger.warning(
                "Retryable error (attempt %d/%d): %s - retrying in %.1fs",
                attempt + 1, _MAX_RETRIES, exc, delay,
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]


def _parse_stream_response(
    response: object,
) -> tuple[list[ToolCall] | None, str | None, TokenUsage | None]:
    """Parse a collected stream response into tool calls, content, and usage."""
    message = response.choices[0].message  # type: ignore[attr-defined]

    # Parse tool calls
    tool_calls = None
    if message.tool_calls:
        tool_calls = []
        for tc in message.tool_calls:
            raw_args = tc.function.arguments
            if isinstance(raw_args, dict):
                arguments = raw_args
            elif isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    logger.warning("Tool '%s': failed to parse arguments (len=%d)", tc.function.name, len(raw_args))
                    arguments = {}
            else:
                logger.warning("Tool '%s': unexpected arguments type %s", tc.function.name, type(raw_args).__name__)
                arguments = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=arguments)
            )

    # Extract text content
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

    # Extract usage
    usage = None
    resp_usage = getattr(response, "usage", None)
    if resp_usage:
        usage = TokenUsage(
            prompt_tokens=getattr(resp_usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(resp_usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(resp_usage, "total_tokens", 0) or 0,
        )

    return tool_calls, text_content, usage


def _format_tool_schemas(schemas: list[dict]) -> list[dict]:
    """Wrap tool schemas in OpenAI function-calling format if not already wrapped.

    Schemas use Anthropic's ``input_schema`` key internally; litellm's OpenAI
    translation layer expects ``parameters``, so we rename during formatting.
    """
    formatted = []
    for schema in schemas:
        if schema.get("type") == "function":
            formatted.append(schema)
        else:
            func = dict(schema)
            if "input_schema" in func and "parameters" not in func:
                func["parameters"] = func.pop("input_schema")
            formatted.append(
                {
                    "type": "function",
                    "function": func,
                }
            )
    return formatted


def _make_usage(prompt: int, completion: int, total: int) -> TokenUsage | None:
    if prompt or completion or total:
        return TokenUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )
    return None
