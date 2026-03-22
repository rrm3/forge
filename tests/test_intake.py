"""Tests for intake: gate, auto-save, resume, analyze_and_advise."""

import os
import pytest
from datetime import UTC, datetime
from unittest.mock import patch, MagicMock

os.environ.setdefault("DEV_MODE", "true")

from backend.main import repos
from backend.models import UserProfile, AIProficiency, Session, Message
from backend.agent.skills import load_skill
from backend.storage import save_transcript, load_transcript, LocalStorage


@pytest.fixture(autouse=True)
def _clean_repos():
    repos["sessions"]._sessions.clear()
    repos["profiles"]._profiles.clear()
    repos["journal"]._entries.clear()
    repos["ideas"]._ideas.clear()
    yield


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


class TestIntakeGate:
    """Test that intake blocks access until complete."""

    def test_no_intake_completed_at(self):
        """Profile without intake_completed_at should gate the user."""
        profile = UserProfile(user_id="u1", name="Alice")
        assert profile.intake_completed_at is None

    def test_intake_completed_at_set(self):
        """Profile with intake_completed_at should pass the gate."""
        profile = UserProfile(
            user_id="u1",
            name="Alice",
            intake_completed_at=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
        )
        assert profile.intake_completed_at is not None


class TestIntakePrompt:
    """Test intake prompt loading and content."""

    def test_load_intake_prompt(self):
        content = load_skill("intake")
        assert content is not None
        assert "Intake" in content
        assert "read_profile" in content
        assert "update_profile" in content

    def test_intake_prompt_has_resume_handling(self):
        content = load_skill("intake")
        assert "Resume" in content or "resume" in content.lower()

    def test_intake_prompt_has_auto_save(self):
        content = load_skill("intake")
        assert "Auto-Save" in content or "Auto-save" in content or "update_profile" in content


class TestIntakeAutoSave:
    """Test incremental profile saving during intake."""

    @pytest.mark.asyncio
    async def test_incremental_field_save(self):
        """Fields should be saveable one phase at a time."""
        profile = UserProfile(user_id="u1", name="Bob")
        await repos["profiles"].create(profile)

        # Phase 2: save products and daily_tasks
        await repos["profiles"].update("u1", {
            "products": ["Dimensions", "Figshare"],
            "daily_tasks": "Reviews PRs, writes design docs",
        })

        loaded = await repos["profiles"].get("u1")
        assert loaded.products == ["Dimensions", "Figshare"]
        assert loaded.daily_tasks == "Reviews PRs, writes design docs"

        # Phase 3: save core_skills
        await repos["profiles"].update("u1", {
            "core_skills": ["Python", "SQL", "data analysis"],
        })

        loaded = await repos["profiles"].get("u1")
        assert loaded.core_skills == ["Python", "SQL", "data analysis"]
        # Previous fields preserved
        assert loaded.products == ["Dimensions", "Figshare"]

    @pytest.mark.asyncio
    async def test_final_save_marks_complete(self):
        """Final phase should set intake_completed_at and onboarding_complete."""
        profile = UserProfile(user_id="u1", name="Carol")
        await repos["profiles"].create(profile)

        now = datetime.now(UTC)
        await repos["profiles"].update("u1", {
            "intake_summary": "Carol is a product manager...",
            "intake_completed_at": now.isoformat(),
            "onboarding_complete": True,
        })

        loaded = await repos["profiles"].get("u1")
        assert loaded.onboarding_complete is True
        assert loaded.intake_summary.startswith("Carol")


class TestIntakeResume:
    """Test resume behavior for interrupted intakes."""

    @pytest.mark.asyncio
    async def test_transcript_preserves_on_interrupt(self, storage):
        """Transcript should be loadable after a save."""
        messages = [
            Message(role="assistant", content="Welcome! Let's get to know each other."),
            Message(role="user", content="I'm a product manager at Dimensions."),
            Message(role="assistant", content="Great! Tell me about your typical week."),
        ]

        await save_transcript(storage, "u1", "intake-session", messages)

        loaded = await load_transcript(storage, "u1", "intake-session")
        assert loaded is not None
        assert len(loaded) == 3
        assert loaded[1].content == "I'm a product manager at Dimensions."


class TestAnalyzeAndAdvise:
    """Test the analyze_and_advise tool."""

    def test_schema_registered(self):
        """The analyze_and_advise tool should be in the registry."""
        from backend.main import tool_registry
        schemas = tool_registry.get_schemas()
        names = [s["name"] for s in schemas]
        assert "analyze_and_advise" in names

    @pytest.mark.asyncio
    async def test_analyze_requires_transcript(self):
        """Should return error message if no transcript exists."""
        from backend.tools.analyze import analyze_and_advise
        from backend.tools.registry import ToolContext

        context = ToolContext(
            user_id="u1",
            session_id="no-such-session",
            storage=LocalStorage("/tmp/forge-test-empty"),
        )

        result = await analyze_and_advise(
            session_id="no-such-session",
            question="Score proficiency",
            context=context,
        )
        assert "No transcript" in result
