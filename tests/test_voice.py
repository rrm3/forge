"""Tests for voice mode: token creation, tool validation, transcript relay."""

import os
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("DEV_MODE", "true")

from backend.main import repos
from backend.models import Session, Message
from backend.tools.registry import ToolRegistry, ToolContext


@pytest.fixture(autouse=True)
def _clean_repos():
    repos["sessions"]._sessions.clear()
    repos["profiles"]._profiles.clear()
    repos["journal"]._entries.clear()
    repos["ideas"]._ideas.clear()
    yield


class TestVoiceTokenCreation:
    """Test ephemeral token generation."""

    def test_voice_tools_defined(self):
        """Voice tools should be a non-empty list of function definitions."""
        from backend.voice import VOICE_TOOLS
        assert len(VOICE_TOOLS) >= 4
        names = [t["name"] for t in VOICE_TOOLS]
        assert "search" in names
        assert "read_profile" in names
        assert "update_profile" in names
        assert "analyze_and_advise" in names

    @pytest.mark.asyncio
    async def test_create_voice_session_builds_correct_payload(self):
        """Verify the payload structure sent to OpenAI."""
        from backend.voice import create_voice_session

        captured_payload = {}

        async def mock_post(self, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "client_secret": {"value": "eph_test123"},
                "expires_at": "2026-03-21T12:00:00Z",
            }
            response.raise_for_status = MagicMock()
            return response

        with patch("backend.voice._get_openai_key", return_value="test-key"):
            with patch("httpx.AsyncClient.post", mock_post):
                result = await create_voice_session(
                    system_prompt="Test prompt",
                    session_id="sess-1",
                )

        assert result["token"] == "eph_test123"
        assert "instructions" in captured_payload
        assert "Test prompt" in captured_payload["instructions"]
        assert "tools" in captured_payload

    @pytest.mark.asyncio
    async def test_resume_includes_transcript(self):
        """Resume should include prior transcript in instructions."""
        from backend.voice import create_voice_session

        captured_payload = {}

        async def mock_post(self, url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "client_secret": {"value": "eph_resume"},
                "expires_at": "2026-03-21T12:00:00Z",
            }
            response.raise_for_status = MagicMock()
            return response

        with patch("backend.voice._get_openai_key", return_value="test-key"):
            with patch("httpx.AsyncClient.post", mock_post):
                result = await create_voice_session(
                    system_prompt="Test prompt",
                    session_id="sess-1",
                    transcript_context="user: Hello\nassistant: Hi there!",
                )

        assert "Prior Conversation" in captured_payload["instructions"]
        assert "Hello" in captured_payload["instructions"]


class TestToolValidation:
    """Test server-side tool validation for voice mode."""

    def test_valid_tool_in_registry(self):
        """Registered tools should be found by name."""
        registry = ToolRegistry()

        async def dummy(context: ToolContext) -> str:
            return "ok"

        registry.register(
            {"name": "search", "description": "Search", "parameters": {}},
            dummy,
        )
        schemas = registry.get_schemas()
        names = {s["name"] for s in schemas}
        assert "search" in names

    def test_unknown_tool_not_in_registry(self):
        """Unknown tools should not be found."""
        registry = ToolRegistry()
        schemas = registry.get_schemas()
        names = {s["name"] for s in schemas}
        assert "fabricated_tool" not in names


class TestTranscriptRelay:
    """Test voice transcript persistence."""

    @pytest.mark.asyncio
    async def test_transcript_message_format(self):
        """Transcript messages should be valid Message objects."""
        msg = Message(role="user", content="Hello from voice")
        assert msg.role == "user"
        assert msg.content == "Hello from voice"

    @pytest.mark.asyncio
    async def test_session_ownership_for_transcript(self):
        """Transcript should only be saved to owned sessions."""
        session = Session(session_id="s1", user_id="u1", title="Test")
        await repos["sessions"].create(session)

        # Owner can access
        result = await repos["sessions"].get("u1", "s1")
        assert result is not None

        # Other user cannot
        result = await repos["sessions"].get("u2", "s1")
        assert result is None
