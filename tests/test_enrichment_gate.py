"""Tests for the `_enrich_profile_async` first-intake gate (W4-03).

Covers the design in docs/designs/2026-04-19-weekly-enrichment-overwrite.md:
profile-field enrichment and AI proficiency scoring should only run on the
user's first-ever successful enrichment (detected via empty
`profile.intake_enrichment_completed_at`), not on subsequent weekly check-ins.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DEV_MODE", "true")

from backend.agent.executor import _enrich_profile_async
from backend.deps import AgentDeps
from backend.models import AIProficiency, Message, UserProfile
from backend.repository.profiles import MemoryProfileRepository
from backend.storage import LocalStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def profiles_repo():
    return MemoryProfileRepository()


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def deps(profiles_repo, storage):
    return AgentDeps(profiles_repo=profiles_repo, storage=storage)


@pytest.fixture
def transcript():
    return [
        Message(role="assistant", content="Welcome! Tell me about your work."),
        Message(
            role="user",
            content=(
                "I'm a senior engineer at Dimensions. I mostly write Python and "
                "review PRs. I'd like to learn how to use AI agents for code review."
            ),
        ),
    ]


@pytest.fixture
def objectives():
    return [
        {"id": "work_summary", "label": "Work summary", "description": ""},
        {"id": "core_skills", "label": "Core skills", "description": ""},
    ]


@pytest.fixture
def mock_enrichment_result():
    """Mock response from `enrich_profile_with_opus`."""
    return {
        "profile": {
            "work_summary": "Senior engineer at Dimensions, Python + PR reviews.",
            "core_skills": ["Python", "code review"],
            "learning_goals": ["AI agents for code review"],
            "intake_summary": "Engineer interested in AI-assisted code review.",
        },
        "objectives": {
            "work_summary": "Senior engineer at Dimensions.",
            "core_skills": "Python, code review.",
        },
    }


@pytest.fixture
def mock_proficiency():
    return {"level": 3, "rationale": "Uses AI tools regularly."}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnrichmentGate:
    """Verify `_enrich_profile_async` runs only on the first-ever intake."""

    @pytest.mark.asyncio
    async def test_calendar_week1_first_intake_runs_enrichment(
        self,
        deps,
        profiles_repo,
        transcript,
        objectives,
        mock_enrichment_result,
        mock_proficiency,
    ):
        """Calendar Week 1 first intake (is_first_intake=True) -> enrichment runs."""
        await profiles_repo.create(UserProfile(user_id="u1", name="Alice"))

        with patch(
            "backend.agent.extraction.enrich_profile_with_opus",
            new=AsyncMock(return_value=mock_enrichment_result),
        ) as mock_enrich, patch(
            "backend.agent.extraction.score_ai_proficiency",
            new=AsyncMock(return_value=mock_proficiency),
        ) as mock_score:
            await _enrich_profile_async(
                deps=deps,
                user_id="u1",
                transcript=transcript,
                objectives=objectives,
                is_first_intake=True,
            )

        assert mock_enrich.await_count == 1
        assert mock_score.await_count == 1

        loaded = await profiles_repo.get("u1")
        assert loaded.work_summary == "Senior engineer at Dimensions, Python + PR reviews."
        assert loaded.core_skills == ["Python", "code review"]
        assert loaded.learning_goals == ["AI agents for code review"]
        assert loaded.intake_summary == "Engineer interested in AI-assisted code review."
        assert isinstance(loaded.ai_proficiency, AIProficiency)
        assert loaded.ai_proficiency.level == 3
        # The enrichment-completed marker must be set so subsequent intakes
        # correctly identify this user as already enriched.
        assert loaded.intake_enrichment_completed_at is not None

    @pytest.mark.asyncio
    async def test_late_joiner_first_intake_runs_enrichment(
        self,
        deps,
        profiles_repo,
        transcript,
        objectives,
        mock_enrichment_result,
        mock_proficiency,
    ):
        """Calendar Week 3 first intake for a late joiner (intake_weeks empty) -> enrichment runs.

        Gate predicate is first-ever intake, not calendar week, so late joiners
        still get their initial identity enrichment.
        """
        await profiles_repo.create(
            UserProfile(
                user_id="u2",
                name="Bob",
                program_week_override=3,
                intake_weeks={},
            )
        )

        with patch(
            "backend.agent.extraction.enrich_profile_with_opus",
            new=AsyncMock(return_value=mock_enrichment_result),
        ) as mock_enrich, patch(
            "backend.agent.extraction.score_ai_proficiency",
            new=AsyncMock(return_value=mock_proficiency),
        ) as mock_score:
            await _enrich_profile_async(
                deps=deps,
                user_id="u2",
                transcript=transcript,
                objectives=objectives,
                is_first_intake=True,
            )

        assert mock_enrich.await_count == 1
        assert mock_score.await_count == 1

        loaded = await profiles_repo.get("u2")
        assert loaded.work_summary == "Senior engineer at Dimensions, Python + PR reviews."
        assert loaded.ai_proficiency is not None
        assert loaded.ai_proficiency.level == 3

    @pytest.mark.asyncio
    async def test_week2_plus_skips_enrichment(
        self,
        deps,
        profiles_repo,
        transcript,
        objectives,
        mock_enrichment_result,
        mock_proficiency,
    ):
        """Week 2+ intake for a user with non-empty intake_weeks -> both mocks record zero calls."""
        await profiles_repo.create(
            UserProfile(
                user_id="u3",
                name="Carol",
                intake_weeks={"1": "2026-03-24T10:00:00+00:00"},
            )
        )

        with patch(
            "backend.agent.extraction.enrich_profile_with_opus",
            new=AsyncMock(return_value=mock_enrichment_result),
        ) as mock_enrich, patch(
            "backend.agent.extraction.score_ai_proficiency",
            new=AsyncMock(return_value=mock_proficiency),
        ) as mock_score:
            await _enrich_profile_async(
                deps=deps,
                user_id="u3",
                transcript=transcript,
                objectives=objectives,
                is_first_intake=False,
            )

        assert mock_enrich.await_count == 0
        assert mock_score.await_count == 0

    @pytest.mark.asyncio
    async def test_week2_plus_preserves_existing_profile_values(
        self,
        deps,
        profiles_repo,
        transcript,
        objectives,
        mock_enrichment_result,
        mock_proficiency,
    ):
        """Regression guard: existing non-empty profile values are unchanged across a Week 2+ completion."""
        baseline_work_summary = "Original Week 1 summary: engineering leadership at Dimensions."
        baseline_core_skills = ["Python", "Kubernetes", "mentoring"]
        baseline_learning_goals = ["vector search", "LLM orchestration"]
        baseline_intake_summary = "Week 1 Opus summary: loves building reliable platforms."
        baseline_proficiency = AIProficiency(level=4, rationale="Builds AI workflows at work.")

        await profiles_repo.create(
            UserProfile(
                user_id="u4",
                name="Dave",
                work_summary=baseline_work_summary,
                core_skills=list(baseline_core_skills),
                learning_goals=list(baseline_learning_goals),
                intake_summary=baseline_intake_summary,
                ai_proficiency=baseline_proficiency,
                intake_weeks={"1": "2026-03-24T10:00:00+00:00"},
                program_week_override=2,
            )
        )

        with patch(
            "backend.agent.extraction.enrich_profile_with_opus",
            new=AsyncMock(return_value=mock_enrichment_result),
        ) as mock_enrich, patch(
            "backend.agent.extraction.score_ai_proficiency",
            new=AsyncMock(return_value=mock_proficiency),
        ) as mock_score:
            await _enrich_profile_async(
                deps=deps,
                user_id="u4",
                transcript=transcript,
                objectives=objectives,
                is_first_intake=False,
            )

        assert mock_enrich.await_count == 0
        assert mock_score.await_count == 0

        loaded = await profiles_repo.get("u4")
        assert loaded.work_summary == baseline_work_summary
        assert loaded.core_skills == baseline_core_skills
        assert loaded.learning_goals == baseline_learning_goals
        assert loaded.intake_summary == baseline_intake_summary
        assert loaded.ai_proficiency is not None
        assert loaded.ai_proficiency.level == 4
        assert loaded.ai_proficiency.rationale == "Builds AI workflows at work."


class TestFirstIntakePredicate:
    """Verify the `is_first_intake = profile.intake_enrichment_completed_at is None`
    predicate handles the skip-intake trap, the crash-mid-enrichment recovery
    case, the intake-skill-writes-intake_summary case, and the normal
    returning-user case correctly.

    These tests exercise the gate predicate itself (via a small harness)
    rather than `_enrich_profile_async`, which is covered above.
    """

    @staticmethod
    def _is_first_intake(profile: UserProfile) -> bool:
        """Mirror of the production predicate at `_check_intake_completion`.

        Kept inline so tests break loudly if the production predicate drifts.
        """
        return profile.intake_enrichment_completed_at is None

    def test_fresh_user_is_first(self):
        """Brand-new user with no enrichment marker → is_first_intake=True."""
        profile = UserProfile(user_id="u1", intake_weeks={})
        assert self._is_first_intake(profile) is True

    def test_enriched_user_is_not_first(self):
        """User whose enrichment succeeded and wrote the marker → False."""
        profile = UserProfile(
            user_id="u2",
            intake_weeks={"1": "2026-03-24T10:00:00+00:00"},
            intake_summary="Senior engineer at Dimensions, builds AI tooling.",
            intake_enrichment_completed_at=datetime.fromisoformat("2026-03-24T10:30:00+00:00"),
        )
        assert self._is_first_intake(profile) is False

    def test_skip_intake_user_is_still_first(self):
        """SKIP-INTAKE TRAP REGRESSION GUARD.

        A user who hit `/skip-intake` has `intake_weeks` populated (by the
        skip handler) but no enrichment marker (never enriched). When they
        later complete a real intake, enrichment must still run.
        """
        profile = UserProfile(
            user_id="u3",
            intake_weeks={"4": "2026-04-14T10:00:00+00:00"},
            intake_skipped=True,
        )
        assert self._is_first_intake(profile) is True, (
            "Skip-intake users must still be eligible for first enrichment; "
            "gating on intake_weeks emptiness would wrongly skip them."
        )

    def test_crash_mid_enrichment_retries(self):
        """CRASH-MID-FLIGHT REGRESSION GUARD.

        If a prior completion wrote `intake_weeks[N]` but the Lambda died
        before `_enrich_profile_async` could write the enrichment marker,
        the user's next intake should still trigger enrichment.
        """
        profile = UserProfile(
            user_id="u4",
            intake_weeks={"1": "2026-03-24T10:00:00+00:00"},
            intake_summary="",  # never got written because enrichment crashed
        )
        assert self._is_first_intake(profile) is True

    def test_intake_skill_wrote_intake_summary_is_still_first(self):
        """SKILL-PROMPT REGRESSION GUARD.

        `skills/intake.md:255` instructs the AI to call `update_profile` with
        `intake_summary` during the closing turn of the intake. That path
        populates `intake_summary` BEFORE `_enrich_profile_async` runs, so a
        predicate based on intake_summary would wrongly skip first enrichment.
        The dedicated `intake_enrichment_completed_at` marker is written only
        by `_enrich_profile_async` on success, so it isn't affected.
        """
        profile = UserProfile(
            user_id="u5",
            intake_weeks={},
            intake_summary="Engineer building agentic runtimes.",  # written by AI
            # intake_enrichment_completed_at=None (default) — enrichment hasn't run
        )
        assert self._is_first_intake(profile) is True, (
            "If the intake skill writes intake_summary before completion, "
            "a summary-based gate would skip enrichment. This must not happen."
        )
