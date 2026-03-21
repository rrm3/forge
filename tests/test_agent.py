"""Tests for the backend.agent package."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agent.context import build_system_prompt
from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.agent.loop import react_loop
from backend.agent.skills import detect_active_skill, load_skill
from backend.models import TokenUsage, UserProfile
from backend.tools.registry import ToolContext, ToolRegistry


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_base_prompt_only(self):
        prompt = build_system_prompt()
        assert "AI Tuesdays" in prompt
        assert "## About the User" not in prompt
        assert "## Memory" not in prompt

    def test_with_profile(self):
        profile = UserProfile(
            user_id="u1",
            name="Alice",
            email="alice@example.com",
            title="Engineer",
            department="R&D",
            ai_experience_level="intermediate",
        )
        prompt = build_system_prompt(profile=profile)
        assert "## About the User" in prompt
        assert "Alice" in prompt
        assert "Engineer" in prompt
        assert "intermediate" in prompt

    def test_with_memory(self):
        prompt = build_system_prompt(memory="User prefers Python examples")
        assert "## Memory" in prompt
        assert "Python examples" in prompt

    def test_with_skill(self):
        skill = "# Onboarding\nWelcome to AI Tuesdays!"
        prompt = build_system_prompt(skill_instructions=skill)
        assert "Onboarding" in prompt
        assert "Welcome to AI Tuesdays!" in prompt

    def test_all_sections(self):
        profile = UserProfile(user_id="u1", name="Bob", goals=["learn LLMs"])
        prompt = build_system_prompt(
            profile=profile,
            memory="Bob is a fast learner",
            skill_instructions="# Welcome\nHi Bob",
        )
        assert "AI Tuesdays" in prompt
        assert "## About the User" in prompt
        assert "Bob" in prompt
        assert "learn LLMs" in prompt
        assert "## Memory" in prompt
        assert "fast learner" in prompt
        assert "# Welcome" in prompt

    def test_empty_profile_fields(self):
        profile = UserProfile(user_id="u1")
        prompt = build_system_prompt(profile=profile)
        # No "About the User" section when all fields are empty
        assert "## About the User" not in prompt


# ---------------------------------------------------------------------------
# Skill loading and detection
# ---------------------------------------------------------------------------


class TestSkills:
    def test_load_skill_not_found(self):
        result = load_skill("nonexistent_skill_xyz")
        assert result is None

    def test_load_skill_found(self, tmp_path, monkeypatch):
        # Create a fake skill file
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "test_skill.md").write_text("# Test Skill\nContent here")

        monkeypatch.setattr(
            "backend.agent.skills._PROJECT_ROOT", tmp_path
        )
        result = load_skill("test_skill")
        assert result == "# Test Skill\nContent here"

    def test_detect_no_profile(self):
        assert detect_active_skill(None, 0) == "onboarding"

    def test_detect_onboarding_incomplete(self):
        profile = UserProfile(user_id="u1", onboarding_complete=False)
        assert detect_active_skill(profile, 0) == "onboarding"

    def test_detect_tuesday_new_session(self):
        profile = UserProfile(user_id="u1", onboarding_complete=True)
        # Tuesday = weekday 1
        tuesday = date(2026, 3, 10)  # A Tuesday
        assert detect_active_skill(profile, 0, current_date=tuesday) == "tuesday_checkin"

    def test_detect_tuesday_existing_session(self):
        profile = UserProfile(user_id="u1", onboarding_complete=True)
        tuesday = date(2026, 3, 10)
        # Session already has messages -> no forced skill
        assert detect_active_skill(profile, 5, current_date=tuesday) is None

    def test_detect_non_tuesday(self):
        profile = UserProfile(user_id="u1", onboarding_complete=True)
        wednesday = date(2026, 3, 11)  # A Wednesday
        assert detect_active_skill(profile, 0, current_date=wednesday) is None


# ---------------------------------------------------------------------------
# ReAct loop helpers
# ---------------------------------------------------------------------------


def _make_stream_chunks(content: str = "", tool_calls=None):
    """Build a list of mock stream chunks that litellm.acompletion would yield."""
    chunks = []

    if content:
        # Split content into character-level deltas for realism
        for char in content:
            delta = SimpleNamespace(content=char, tool_calls=None, role=None)
            choice = SimpleNamespace(delta=delta, finish_reason=None)
            chunk = SimpleNamespace(choices=[choice], usage=None)
            chunks.append(chunk)

    if tool_calls:
        for tc in tool_calls:
            delta = SimpleNamespace(
                content=None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id=tc["id"],
                        type="function",
                        function=SimpleNamespace(
                            name=tc["name"],
                            arguments=json.dumps(tc["arguments"]),
                        ),
                    )
                ],
                role=None,
            )
            choice = SimpleNamespace(delta=delta, finish_reason=None)
            chunk = SimpleNamespace(choices=[choice], usage=None)
            chunks.append(chunk)

    # Final chunk with finish_reason
    finish_delta = SimpleNamespace(content=None, tool_calls=None, role=None)
    finish_choice = SimpleNamespace(
        delta=finish_delta,
        finish_reason="tool_calls" if tool_calls else "stop",
    )
    finish_chunk = SimpleNamespace(choices=[finish_choice], usage=None)
    chunks.append(finish_chunk)

    return chunks


def _make_built_response(content: str | None = None, tool_calls=None, usage=None):
    """Build a mock response that stream_chunk_builder would return."""
    tc_list = None
    if tool_calls:
        tc_list = [
            SimpleNamespace(
                id=tc["id"],
                type="function",
                function=SimpleNamespace(
                    name=tc["name"],
                    arguments=json.dumps(tc["arguments"]),
                ),
            )
            for tc in tool_calls
        ]

    message = SimpleNamespace(content=content, tool_calls=tc_list)
    choice = SimpleNamespace(message=message, finish_reason="stop")

    resp_usage = None
    if usage:
        resp_usage = SimpleNamespace(**usage)

    return SimpleNamespace(choices=[choice], usage=resp_usage)


async def _collect_events(gen) -> list:
    events = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# ReAct loop tests
# ---------------------------------------------------------------------------


class TestReactLoop:
    """Test the ReAct loop with mocked LLM calls."""

    @pytest.fixture
    def tool_context(self):
        return ToolContext(user_id="test-user", session_id="test-session")

    @pytest.fixture
    def empty_registry(self):
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_text_only_response(self, tool_context, empty_registry):
        """LLM returns text with no tool calls -> TextEvent + DoneEvent."""
        chunks = _make_stream_chunks(content="Hello, world!")
        built = _make_built_response(
            content="Hello, world!",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        async def mock_acompletion(**kwargs):
            async def gen():
                for c in chunks:
                    yield c
            return gen()

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = MagicMock(return_value=built)

            events = await _collect_events(
                react_loop(
                    user_message="Hi",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=empty_registry,
                    context=tool_context,
                )
            )

        # Should have text events (one per character) and a done event
        text_events = [e for e in events if isinstance(e, TextEvent)]
        done_events = [e for e in events if isinstance(e, DoneEvent)]

        assert len(text_events) > 0
        full_text = "".join(e.text for e in text_events)
        assert full_text == "Hello, world!"

        assert len(done_events) == 1
        assert done_events[0].usage is not None
        assert done_events[0].usage.prompt_tokens == 10
        assert done_events[0].usage.completion_tokens == 5

    @pytest.mark.asyncio
    async def test_tool_call_and_response(self, tool_context):
        """LLM calls a tool, gets result, then produces final text."""
        registry = ToolRegistry()

        # Register a simple tool
        async def echo_handler(text: str, context: ToolContext) -> str:
            return f"Echo: {text}"

        registry.register(
            {"name": "echo", "description": "Echo text", "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            }},
            echo_handler,
        )

        # First call: LLM returns a tool call
        tool_call_data = [{"id": "call_1", "name": "echo", "arguments": {"text": "ping"}}]
        chunks_1 = _make_stream_chunks(tool_calls=tool_call_data)
        built_1 = _make_built_response(
            tool_calls=tool_call_data,
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        )

        # Second call: LLM returns text
        chunks_2 = _make_stream_chunks(content="Got it!")
        built_2 = _make_built_response(
            content="Got it!",
            usage={"prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35},
        )

        call_count = 0

        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            current_chunks = chunks_1 if call_count == 1 else chunks_2

            async def gen():
                for c in current_chunks:
                    yield c
            return gen()

        built_responses = [built_1, built_2]
        build_call = 0

        def mock_stream_builder(chunks):
            nonlocal build_call
            resp = built_responses[build_call]
            build_call += 1
            return resp

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = mock_stream_builder

            events = await _collect_events(
                react_loop(
                    user_message="Say ping",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=registry,
                    context=tool_context,
                )
            )

        tool_call_events = [e for e in events if isinstance(e, ToolCallEvent)]
        tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        text_events = [e for e in events if isinstance(e, TextEvent)]
        done_events = [e for e in events if isinstance(e, DoneEvent)]

        assert len(tool_call_events) == 1
        assert tool_call_events[0].tool_name == "echo"
        assert tool_call_events[0].arguments == {"text": "ping"}

        assert len(tool_result_events) == 1
        assert tool_result_events[0].result == "Echo: ping"

        assert len(text_events) > 0
        assert "".join(e.text for e in text_events) == "Got it!"

        assert len(done_events) == 1
        # Usage should be accumulated across both calls
        assert done_events[0].usage.prompt_tokens == 50
        assert done_events[0].usage.completion_tokens == 15

    @pytest.mark.asyncio
    async def test_tool_execution_error(self, tool_context):
        """Tool raises an exception -> error is captured as result, loop continues."""
        registry = ToolRegistry()

        async def failing_handler(context: ToolContext) -> str:
            raise ValueError("Something broke")

        registry.register(
            {"name": "fail_tool", "description": "Always fails", "parameters": {
                "type": "object", "properties": {},
            }},
            failing_handler,
        )

        tool_call_data = [{"id": "call_f", "name": "fail_tool", "arguments": {}}]
        chunks_1 = _make_stream_chunks(tool_calls=tool_call_data)
        built_1 = _make_built_response(
            tool_calls=tool_call_data,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        chunks_2 = _make_stream_chunks(content="Tool failed, sorry.")
        built_2 = _make_built_response(
            content="Tool failed, sorry.",
            usage={"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
        )

        call_count = 0

        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            current = chunks_1 if call_count == 1 else chunks_2

            async def gen():
                for c in current:
                    yield c
            return gen()

        builds = [built_1, built_2]
        bi = 0

        def mock_builder(chunks):
            nonlocal bi
            r = builds[bi]
            bi += 1
            return r

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = mock_builder

            events = await _collect_events(
                react_loop(
                    user_message="Do the thing",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=registry,
                    context=tool_context,
                )
            )

        # Tool result should contain the error
        result_events = [e for e in events if isinstance(e, ToolResultEvent)]
        assert len(result_events) == 1
        assert "Something broke" in result_events[0].result

        # Loop should still complete with done
        done_events = [e for e in events if isinstance(e, DoneEvent)]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_max_iterations(self, tool_context):
        """Loop stops after max_iterations and yields ErrorEvent."""
        registry = ToolRegistry()

        async def noop_handler(context: ToolContext) -> str:
            return "ok"

        registry.register(
            {"name": "noop", "description": "No-op", "parameters": {
                "type": "object", "properties": {},
            }},
            noop_handler,
        )

        tool_call_data = [{"id": "call_n", "name": "noop", "arguments": {}}]
        chunks = _make_stream_chunks(tool_calls=tool_call_data)
        built = _make_built_response(
            tool_calls=tool_call_data,
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

        async def mock_acompletion(**kwargs):
            async def gen():
                for c in chunks:
                    yield c
            return gen()

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = MagicMock(return_value=built)

            events = await _collect_events(
                react_loop(
                    user_message="Loop forever",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=registry,
                    context=tool_context,
                    max_iterations=2,
                )
            )

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1
        assert "maximum iterations" in error_events[0].error.lower()

    @pytest.mark.asyncio
    async def test_cancel_event(self, tool_context, empty_registry):
        """Cancel event stops the loop cleanly."""
        cancel = asyncio.Event()
        cancel.set()  # Already cancelled

        chunks = _make_stream_chunks(content="Hello")
        built = _make_built_response(content="Hello")

        async def mock_acompletion(**kwargs):
            async def gen():
                for c in chunks:
                    yield c
            return gen()

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = MagicMock(return_value=built)

            events = await _collect_events(
                react_loop(
                    user_message="Hi",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=empty_registry,
                    context=tool_context,
                    cancel_event=cancel,
                )
            )

        # Should get DoneEvent immediately due to cancellation
        done_events = [e for e in events if isinstance(e, DoneEvent)]
        assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_llm_error(self, tool_context, empty_registry):
        """Non-retryable LLM error yields ErrorEvent."""

        async def mock_acompletion(**kwargs):
            raise Exception("API key invalid")

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion

            # Patch is_retryable_error to return False
            with patch("backend.agent.loop.is_retryable_error", return_value=False):
                events = await _collect_events(
                    react_loop(
                        user_message="Hi",
                        messages=[],
                        system_prompt="You are helpful.",
                        tools=empty_registry,
                        context=tool_context,
                    )
                )

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_messages_built_correctly(self, tool_context, empty_registry):
        """System prompt and user message are added to messages list."""
        messages: list[dict] = []

        chunks = _make_stream_chunks(content="Reply")
        built = _make_built_response(content="Reply")

        async def mock_acompletion(**kwargs):
            async def gen():
                for c in chunks:
                    yield c
            return gen()

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = MagicMock(return_value=built)

            await _collect_events(
                react_loop(
                    user_message="Hello there",
                    messages=messages,
                    system_prompt="System prompt here",
                    tools=empty_registry,
                    context=tool_context,
                )
            )

        # messages should have been modified in place
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt here"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello there"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Reply"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, tool_context):
        """LLM returns multiple tool calls in a single response."""
        registry = ToolRegistry()

        async def add_handler(a: int, b: int, context: ToolContext) -> str:
            return str(a + b)

        async def mul_handler(a: int, b: int, context: ToolContext) -> str:
            return str(a * b)

        registry.register(
            {"name": "add", "description": "Add numbers", "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            }},
            add_handler,
        )
        registry.register(
            {"name": "mul", "description": "Multiply numbers", "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            }},
            mul_handler,
        )

        tool_calls = [
            {"id": "call_a", "name": "add", "arguments": {"a": 2, "b": 3}},
            {"id": "call_m", "name": "mul", "arguments": {"a": 4, "b": 5}},
        ]
        chunks_1 = _make_stream_chunks(tool_calls=tool_calls)
        built_1 = _make_built_response(
            tool_calls=tool_calls,
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        )

        chunks_2 = _make_stream_chunks(content="2+3=5, 4*5=20")
        built_2 = _make_built_response(
            content="2+3=5, 4*5=20",
            usage={"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
        )

        call_count = 0

        async def mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            current = chunks_1 if call_count == 1 else chunks_2

            async def gen():
                for c in current:
                    yield c
            return gen()

        builds = [built_1, built_2]
        bi = 0

        def mock_builder(chunks):
            nonlocal bi
            r = builds[bi]
            bi += 1
            return r

        with patch("backend.agent.loop.litellm") as mock_litellm:
            mock_litellm.acompletion = mock_acompletion
            mock_litellm.stream_chunk_builder = mock_builder

            events = await _collect_events(
                react_loop(
                    user_message="Add 2+3 and multiply 4*5",
                    messages=[],
                    system_prompt="You are helpful.",
                    tools=registry,
                    context=tool_context,
                )
            )

        tc_events = [e for e in events if isinstance(e, ToolCallEvent)]
        tr_events = [e for e in events if isinstance(e, ToolResultEvent)]

        assert len(tc_events) == 2
        assert tc_events[0].tool_name == "add"
        assert tc_events[1].tool_name == "mul"

        assert len(tr_events) == 2
        assert tr_events[0].result == "5"
        assert tr_events[1].result == "20"
