"""Tests for v2 profile schema expansion."""

import os
import pytest
from datetime import UTC, datetime

os.environ.setdefault("DEV_MODE", "true")

from backend.models import UserProfile, AIProficiency
from backend.main import repos


@pytest.fixture(autouse=True)
def _clean_repos():
    repos["profiles"]._profiles.clear()
    yield


class TestProfileSchemaExpansion:
    """Test the new intake fields on UserProfile."""

    def test_default_values(self):
        """New fields should have sensible defaults."""
        profile = UserProfile(user_id="u1")
        assert profile.products == []
        assert profile.daily_tasks == ""
        assert profile.core_skills == []
        assert profile.learning_goals == []
        assert profile.ai_tools_used == []
        assert profile.ai_superpower == ""
        assert profile.ai_proficiency is None
        assert profile.intake_summary == ""
        assert profile.intake_completed_at is None

    def test_ai_proficiency_model(self):
        """AIProficiency model should have level and rationale."""
        prof = AIProficiency(
            level=3,
            rationale="Regular chatbot user with some customization",
        )
        assert prof.level == 3
        assert "chatbot" in prof.rationale

    def test_ai_proficiency_defaults(self):
        """AIProficiency defaults to level 0 and empty rationale."""
        prof = AIProficiency()
        assert prof.level == 0
        assert prof.rationale == ""

    def test_profile_with_all_fields(self):
        """Profile should accept all v2 fields."""
        profile = UserProfile(
            user_id="u1",
            name="Alice",
            products=["Dimensions", "Figshare"],
            daily_tasks="Manages product roadmap",
            core_skills=["product management", "SQL"],
            learning_goals=["prompt engineering"],
            ai_tools_used=["ChatGPT", "Claude"],
            ai_superpower="Build prototypes users can test",
            ai_proficiency=AIProficiency(
                level=3,
                rationale="Uses AI regularly with some customization",
            ),
            intake_summary="Alice is a PM with strong delegation instincts.",
            intake_completed_at=datetime(2026, 3, 25, 10, 30, tzinfo=UTC),
        )
        assert profile.products == ["Dimensions", "Figshare"]
        assert profile.ai_proficiency.level == 3
        assert profile.intake_completed_at is not None

    @pytest.mark.asyncio
    async def test_incremental_save(self):
        """Profile fields should be saveable incrementally."""
        # Create base profile
        profile = UserProfile(user_id="u1", name="Bob")
        await repos["profiles"].create(profile)

        # Save products
        await repos["profiles"].update("u1", {"products": ["Dimensions"]})
        loaded = await repos["profiles"].get("u1")
        assert loaded.products == ["Dimensions"]

        # Save proficiency
        await repos["profiles"].update("u1", {
            "ai_proficiency": {
                "level": 3,
                "rationale": "Regular user with customization",
            }
        })
        loaded = await repos["profiles"].get("u1")
        assert loaded.products == ["Dimensions"]  # Previous field preserved

    @pytest.mark.asyncio
    async def test_intake_completed_at_persistence(self):
        """intake_completed_at should round-trip through storage."""
        now = datetime(2026, 3, 20, 10, 30, tzinfo=UTC)
        profile = UserProfile(
            user_id="u1",
            intake_completed_at=now,
        )
        await repos["profiles"].create(profile)

        loaded = await repos["profiles"].get("u1")
        assert loaded.intake_completed_at is not None
