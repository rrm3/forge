"""Tests for backend/llm.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from backend.llm import (
    LLMResponse,
    ToolCall,
    _MAX_RETRIES,
    call_llm,
    classify_llm_error,
    is_retryable_error,
)
from backend.models import TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    content="Hello!",
    tool_calls=None,
    prompt_tokens=10,
    completion_tokens=5,
    total_tokens=15,
):
    """Build a minimal mock litellm completion response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    def test_rate_limit_is_retryable(self):
        exc = litellm.RateLimitError("rate limited", llm_provider="anthropic", model="claude")
        assert is_retryable_error(exc)

    def test_service_unavailable_is_retryable(self):
        exc = litellm.ServiceUnavailableError(
            "503", llm_provider="anthropic", model="claude"
        )
        assert is_retryable_error(exc)

    def test_auth_error_not_retryable(self):
        exc = litellm.AuthenticationError(
            "bad key", llm_provider="anthropic", model="claude"
        )
        assert not is_retryable_error(exc)

    def test_value_error_not_retryable(self):
        assert not is_retryable_error(ValueError("oops"))


# ---------------------------------------------------------------------------
# classify_llm_error
# ---------------------------------------------------------------------------


class TestClassifyLlmError:
    def test_auth_error(self):
        exc = litellm.AuthenticationError(
            "bad key", llm_provider="anthropic", model="claude"
        )
        msg = classify_llm_error(exc)
        assert "API key rejected" in msg

    def test_permission_denied(self):
        exc = litellm.PermissionDeniedError(
            "forbidden", llm_provider="anthropic", model="claude", response=MagicMock()
        )
        msg = classify_llm_error(exc)
        assert "permission" in msg.lower()

    def test_not_found(self):
        exc = litellm.NotFoundError("no model", llm_provider="anthropic", model="claude")
        msg = classify_llm_error(exc)
        assert "not found" in msg.lower()

    def test_bad_request_includes_detail(self):
        exc = litellm.BadRequestError(
            "context length exceeded", llm_provider="anthropic", model="claude"
        )
        msg = classify_llm_error(exc)
        assert "context length exceeded" in msg

    def test_generic_error(self):
        msg = classify_llm_error(RuntimeError("boom"))
        assert "Internal error" in msg


# ---------------------------------------------------------------------------
# call_llm - happy path
# ---------------------------------------------------------------------------


class TestCallLlm:
    @pytest.mark.asyncio
    async def test_returns_content(self):
        mock_response = _make_response(content="Paris")
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await call_llm([{"role": "user", "content": "Capital of France?"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Paris"
        assert result.tool_calls is None

    @pytest.mark.asyncio
    async def test_uses_settings_model_by_default(self):
        mock_response = _make_response()
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            with patch("backend.llm.settings") as mock_settings:
                mock_settings.llm_model = "anthropic/claude-test"
                await call_llm([{"role": "user", "content": "hi"}])

        called_kwargs = mock_call.call_args.kwargs
        assert called_kwargs["model"] == "anthropic/claude-test"

    @pytest.mark.asyncio
    async def test_explicit_model_overrides_default(self):
        mock_response = _make_response()
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await call_llm(
                [{"role": "user", "content": "hi"}],
                model="openai/gpt-4o",
            )

        assert mock_call.call_args.kwargs["model"] == "openai/gpt-4o"

    @pytest.mark.asyncio
    async def test_passes_tools(self):
        mock_response = _make_response()
        tools = [{"type": "function", "function": {"name": "get_weather"}}]
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await call_llm([{"role": "user", "content": "weather?"}], tools=tools)

        assert mock_call.call_args.kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_token_usage_extracted(self):
        mock_response = _make_response(prompt_tokens=20, completion_tokens=8, total_tokens=28)
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await call_llm([{"role": "user", "content": "hi"}])

        assert result.usage is not None
        assert result.usage.prompt_tokens == 20
        assert result.usage.completion_tokens == 8
        assert result.usage.total_tokens == 28

    @pytest.mark.asyncio
    async def test_tool_calls_parsed(self):
        tc = MagicMock()
        tc.id = "call_abc"
        tc.function.name = "get_weather"
        tc.function.arguments = '{"city": "London"}'

        mock_response = _make_response(content=None, tool_calls=[tc])
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await call_llm([{"role": "user", "content": "weather?"}])

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        call = result.tool_calls[0]
        assert isinstance(call, ToolCall)
        assert call.id == "call_abc"
        assert call.name == "get_weather"
        assert call.arguments == {"city": "London"}

    @pytest.mark.asyncio
    async def test_list_content_blocks_extracted(self):
        """Content as a list of typed blocks is flattened to a string."""
        mock_response = _make_response(
            content=[
                {"type": "text", "text": "Hello, "},
                {"type": "text", "text": "world!"},
            ]
        )
        with patch("backend.llm.litellm.acompletion", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await call_llm([{"role": "user", "content": "hi"}])

        assert result.content == "Hello, world!"


# ---------------------------------------------------------------------------
# call_llm - retry behavior
# ---------------------------------------------------------------------------


class TestCallLlmRetry:
    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_then_succeeds(self):
        rate_limit_exc = litellm.RateLimitError(
            "rate limited", llm_provider="anthropic", model="claude"
        )
        mock_response = _make_response(content="ok")

        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise rate_limit_exc
            return mock_response

        with patch("backend.llm.litellm.acompletion", side_effect=side_effect):
            with patch("backend.llm.asyncio.sleep", new_callable=AsyncMock):
                result = await call_llm([{"role": "user", "content": "hi"}])

        assert result.content == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        rate_limit_exc = litellm.RateLimitError(
            "rate limited", llm_provider="anthropic", model="claude"
        )

        async def always_fail(**kwargs):
            raise rate_limit_exc

        with patch("backend.llm.litellm.acompletion", side_effect=always_fail):
            with patch("backend.llm.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.RateLimitError):
                    await call_llm([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self):
        auth_exc = litellm.AuthenticationError(
            "bad key", llm_provider="anthropic", model="claude"
        )
        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            raise auth_exc

        with patch("backend.llm.litellm.acompletion", side_effect=side_effect):
            with patch("backend.llm.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.AuthenticationError):
                    await call_llm([{"role": "user", "content": "hi"}])

        # Should not have retried
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_count_is_max_retries(self):
        """Exactly _MAX_RETRIES attempts are made before giving up."""
        exc = litellm.ServiceUnavailableError(
            "503", llm_provider="anthropic", model="claude"
        )
        call_count = 0

        async def always_fail(**kwargs):
            nonlocal call_count
            call_count += 1
            raise exc

        with patch("backend.llm.litellm.acompletion", side_effect=always_fail):
            with patch("backend.llm.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(litellm.ServiceUnavailableError):
                    await call_llm([{"role": "user", "content": "hi"}])

        assert call_count == _MAX_RETRIES
