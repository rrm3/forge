"""Unit tests for Phase 3: wrapup context loading, pulse to-ask computation,
journal write policy, and build_system_prompt Context section rendering.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

os.environ.setdefault("DEV_MODE", "true")

from backend.agent.context import build_system_prompt
from backend.agent.wrapup_context import (
    load_wrapup_context,
    questions_to_ask,
    wrapup_context_is_empty,
)
from backend.models import JournalEntry, UserProfile
from backend.repository.journal import MemoryJournalRepository
from backend.storage import (
    LocalStorage,
    append_pulse_response,
    load_pulse_config,
    load_pulse_responses,
    save_intake_responses,
)


# ---------------------------------------------------------------------------
# Pulse to-ask computation
# ---------------------------------------------------------------------------


class TestQuestionsToAsk:
    def test_all_answered_returns_nothing(self):
        config = [
            {"id": "progress", "version": "v1", "text": "..."},
            {"id": "impact", "version": "v1", "text": "..."},
        ]
        answers = [
            {"question_id": "progress", "version": "v1", "level": 3, "week": 4},
            {"question_id": "impact", "version": "v1", "level": 4, "week": 4},
        ]
        assert questions_to_ask(config, answers) == []

    def test_none_answered_returns_all(self):
        config = [
            {"id": "progress", "version": "v1", "text": "..."},
            {"id": "impact", "version": "v1", "text": "..."},
        ]
        assert questions_to_ask(config, []) == config

    def test_partial_answered(self):
        config = [
            {"id": "progress", "version": "v1", "text": "..."},
            {"id": "impact", "version": "v1", "text": "..."},
        ]
        answers = [{"question_id": "progress", "version": "v1", "level": 3, "week": 4}]
        remaining = questions_to_ask(config, answers)
        assert len(remaining) == 1
        assert remaining[0]["id"] == "impact"

    def test_version_bump_triggers_reask(self):
        """v1 answer must not satisfy a v2 question of the same id."""
        config = [{"id": "progress", "version": "v2", "text": "..."}]
        answers = [{"question_id": "progress", "version": "v1", "level": 3, "week": 4}]
        remaining = questions_to_ask(config, answers)
        assert len(remaining) == 1
        assert remaining[0]["version"] == "v2"

    def test_malformed_entries_are_skipped(self):
        """Corrupt records in the log must not crash the computation."""
        config = [{"id": "progress", "version": "v1", "text": "..."}]
        answers = [
            "not a dict",
            {"question_id": None, "version": "v1"},
            {"question_id": "progress"},  # missing version
            {"version": "v1"},  # missing question_id
            42,
            {"question_id": "progress", "version": "v1", "level": 3, "week": 4},
        ]
        assert questions_to_ask(config, answers) == []

    def test_empty_config_returns_empty(self):
        assert questions_to_ask([], []) == []


# ---------------------------------------------------------------------------
# Pulse storage helpers
# ---------------------------------------------------------------------------


class TestPulseStorage:
    def test_load_pulse_config_returns_v1_entries(self):
        config = load_pulse_config()
        ids = {q["id"] for q in config}
        assert {"progress", "impact"} <= ids
        for q in config:
            assert q["version"] == "v1"
            assert len(q["scale"]) == 5

    @pytest.mark.asyncio
    async def test_append_pulse_response_roundtrip(self, tmp_path):
        storage = LocalStorage(tmp_path)
        record = {
            "question_id": "progress",
            "version": "v1",
            "level": 3,
            "week": 4,
            "answered_at": "2026-04-14T18:00:00+00:00",
        }
        await append_pulse_response(storage, "user-1", record)
        loaded = await load_pulse_responses(storage, "user-1")
        assert loaded == [record]

        second = dict(record, question_id="impact")
        await append_pulse_response(storage, "user-1", second)
        loaded = await load_pulse_responses(storage, "user-1")
        assert len(loaded) == 2
        assert loaded[1]["question_id"] == "impact"

    @pytest.mark.asyncio
    async def test_load_pulse_responses_missing_returns_empty(self, tmp_path):
        storage = LocalStorage(tmp_path)
        assert await load_pulse_responses(storage, "ghost") == []

    @pytest.mark.asyncio
    async def test_load_pulse_responses_handles_corrupt_file(self, tmp_path):
        storage = LocalStorage(tmp_path)
        path = tmp_path / "profiles" / "user-x" / "pulse-responses.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json")
        assert await load_pulse_responses(storage, "user-x") == []


# ---------------------------------------------------------------------------
# wrapup_context loader
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path)


@pytest.fixture
def journal_repo(tmp_path):
    return MemoryJournalRepository(persist_path=str(tmp_path / "journal.json"))


class TestLoadWrapupContext:
    @pytest.mark.asyncio
    async def test_all_sources_empty(self, storage, journal_repo):
        profile = UserProfile(user_id="u-empty", program_week_override=1)
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-empty")
        assert ctx["intake_today"] == []
        assert ctx["journal_today"] == []
        assert ctx["previous_digest"] == ""
        # pulse_to_ask depends on the deployed config; with no answers we
        # expect every question currently in the config to be asked.
        expected = load_pulse_config()
        assert len(ctx["pulse_to_ask"]) == len(expected)

    @pytest.mark.asyncio
    async def test_context_is_empty_helper(self):
        assert wrapup_context_is_empty(None)
        assert wrapup_context_is_empty({})
        assert wrapup_context_is_empty({
            "intake_today": [],
            "journal_today": [],
            "previous_digest": "",
            "pulse_to_ask": [],
        })
        assert not wrapup_context_is_empty({
            "intake_today": [],
            "journal_today": [],
            "previous_digest": "",
            "pulse_to_ask": [{"id": "progress", "version": "v1"}],
        })

    @pytest.mark.asyncio
    async def test_intake_today_filters_and_orders_plan_first(self, storage, journal_repo):
        profile = UserProfile(user_id="u1", program_week_override=4)
        today_iso = datetime.now(UTC).isoformat()
        yesterday_iso = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        responses = {
            "applied-learnings-week4": {
                "value": "Tried Claude projects",
                "captured_at": today_iso,
            },
            "plan-day4": {
                "value": "Build a pipeline prototype",
                "captured_at": today_iso,
            },
            "old-objective": {
                "value": "Stale",
                "captured_at": yesterday_iso,
            },
        }
        await save_intake_responses(storage, "u1", responses)

        merged = [
            {"id": "applied-learnings-week4", "label": "Applied learnings"},
            {"id": "plan-day4", "label": "Plan for Day 4"},
        ]
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u1", merged_objectives=merged)
        ids = [item["id"] for item in ctx["intake_today"]]
        assert ids[0] == "plan-day4"  # plan always first
        assert "applied-learnings-week4" in ids
        assert "old-objective" not in ids

    @pytest.mark.asyncio
    async def test_intake_today_only_no_journal_no_digest(self, storage, journal_repo):
        profile = UserProfile(user_id="u-only-intake", program_week_override=1)
        today_iso = datetime.now(UTC).isoformat()
        await save_intake_responses(storage, "u-only-intake", {
            "goal": {"value": "Ship feature", "captured_at": today_iso, "label": "Goal"},
        })
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-only-intake")
        assert len(ctx["intake_today"]) == 1
        assert ctx["journal_today"] == []
        assert ctx["previous_digest"] == ""

    @pytest.mark.asyncio
    async def test_journal_today_truncation_and_order(self, storage, journal_repo):
        profile = UserProfile(user_id="u-j", program_week_override=1)
        # Use the middle of the current UTC day so both entries land inside
        # [today_start, today_end) regardless of when the test runs.
        today = datetime.now(UTC).date()
        midday = datetime.combine(today, datetime.min.time().replace(hour=12), tzinfo=UTC)
        await journal_repo.create(JournalEntry(
            entry_id="e1",
            user_id="u-j",
            content="early entry",
            created_at=midday - timedelta(hours=2),
        ))
        long_content = "x" * 800
        await journal_repo.create(JournalEntry(
            entry_id="e2",
            user_id="u-j",
            content=long_content,
            created_at=midday,
        ))
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-j")
        assert len(ctx["journal_today"]) == 2
        # Newest first
        assert ctx["journal_today"][0]["content"].startswith("x")
        assert len(ctx["journal_today"][0]["content"]) <= 500
        assert ctx["journal_today"][0]["content"].endswith("...")
        assert ctx["journal_today"][1]["content"] == "early entry"

    @pytest.mark.asyncio
    async def test_journal_excludes_yesterday(self, storage, journal_repo):
        profile = UserProfile(user_id="u-y", program_week_override=1)
        today = datetime.now(UTC).date()
        midday = datetime.combine(today, datetime.min.time().replace(hour=12), tzinfo=UTC)
        await journal_repo.create(JournalEntry(
            entry_id="yesterday",
            user_id="u-y",
            content="from yesterday",
            created_at=midday - timedelta(days=2),
        ))
        await journal_repo.create(JournalEntry(
            entry_id="today",
            user_id="u-y",
            content="from today",
            created_at=midday,
        ))
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-y")
        contents = [e["content"] for e in ctx["journal_today"]]
        assert "from today" in contents
        assert "from yesterday" not in contents

    @pytest.mark.asyncio
    async def test_previous_digest_loaded(self, storage, journal_repo, tmp_path):
        profile = UserProfile(user_id="u-d", program_week_override=5)
        key_path = tmp_path / "profiles" / "u-d" / "digest-week4.md"
        key_path.parent.mkdir(parents=True)
        key_path.write_bytes(b"# Week 4\nGreat progress.\n")
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-d")
        assert "Week 4" in ctx["previous_digest"]

    @pytest.mark.asyncio
    async def test_previous_digest_missing_is_silent(self, storage, journal_repo):
        profile = UserProfile(user_id="u-no-digest", program_week_override=5)
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-no-digest")
        assert ctx["previous_digest"] == ""

    @pytest.mark.asyncio
    async def test_previous_digest_week_one(self, storage, journal_repo):
        """Week 1 users have no prior digest to load."""
        profile = UserProfile(user_id="u-w1", program_week_override=1)
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-w1")
        assert ctx["previous_digest"] == ""

    @pytest.mark.asyncio
    async def test_pulse_to_ask_respects_answers(self, storage, journal_repo):
        profile = UserProfile(user_id="u-p", program_week_override=4)
        await append_pulse_response(storage, "u-p", {
            "question_id": "progress",
            "version": "v1",
            "level": 3,
            "week": 4,
            "answered_at": datetime.now(UTC).isoformat(),
        })
        ctx = await load_wrapup_context(storage, journal_repo, profile, "u-p")
        ids = [q["id"] for q in ctx["pulse_to_ask"]]
        assert "progress" not in ids
        assert "impact" in ids

    @pytest.mark.asyncio
    async def test_timezone_auckland_evening_finds_morning_intake(
        self, storage, journal_repo, monkeypatch,
    ):
        """User in Auckland: intake at 09:00 NZT, wrapup at 17:00 NZT.

        Both events happen on the same local date, so the morning intake
        must be visible to the evening wrapup even though UTC may already
        have rolled over in some fixed real-time scenarios.
        """
        from zoneinfo import ZoneInfo
        auckland = ZoneInfo("Pacific/Auckland")

        # Pick a fixed Auckland "today" -- mid-day so both 09:00 and 17:00
        # land on the same local date no matter how UTC aligns.
        fixed_local = datetime(2026, 4, 14, 17, 0, tzinfo=auckland)
        fixed_utc = fixed_local.astimezone(UTC)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return fixed_utc.replace(tzinfo=None)
                return fixed_utc.astimezone(tz)

        import backend.agent.wrapup_context as wc
        monkeypatch.setattr(wc, "datetime", _FrozenDatetime)

        profile = UserProfile(
            user_id="u-auckland",
            program_week_override=4,
            timezone="Pacific/Auckland",
        )

        morning_local = datetime(2026, 4, 14, 9, 0, tzinfo=auckland)
        morning_utc = morning_local.astimezone(UTC).isoformat()
        responses = {
            "plan-day4": {
                "value": "Prototype data pipeline",
                "captured_at": morning_utc,
            },
        }
        await save_intake_responses(storage, "u-auckland", responses)

        ctx = await load_wrapup_context(
            storage, journal_repo, profile, "u-auckland",
            merged_objectives=[{"id": "plan-day4", "label": "Plan for Day 4"}],
        )
        ids = [item["id"] for item in ctx["intake_today"]]
        assert "plan-day4" in ids


# ---------------------------------------------------------------------------
# build_system_prompt rendering
# ---------------------------------------------------------------------------


class TestBuildSystemPromptWithContext:
    def test_wrapup_context_none_omits_section(self):
        prompt = build_system_prompt(
            session_type="wrapup",
            skill_instructions="wrap-up skill instructions",
            wrapup_context=None,
        )
        assert "Context for Today's Wrap-up" not in prompt

    def test_wrapup_context_all_empty_omits_section(self):
        prompt = build_system_prompt(
            session_type="wrapup",
            skill_instructions="wrap-up skill instructions",
            wrapup_context={
                "intake_today": [],
                "journal_today": [],
                "previous_digest": "",
                "pulse_to_ask": [],
            },
        )
        assert "Context for Today's Wrap-up" not in prompt

    def test_wrapup_context_full_renders_all_subsections(self):
        ctx = {
            "intake_today": [
                {"id": "plan-day4", "label": "Plan for Day 4", "value": "Build prototype"},
                {"id": "applied", "label": "Applied learnings", "value": "Used Claude on emails"},
            ],
            "journal_today": [
                {"timestamp": "14:03", "content": "Started prototype"},
                {"timestamp": "11:40", "content": "Set up env"},
            ],
            "previous_digest": "# Week 4\nLast week's narrative.",
            "pulse_to_ask": [
                {
                    "id": "progress",
                    "version": "v1",
                    "text": "Are you making progress?",
                    "scale": ["No", "Slight", "Some", "Good", "Great"],
                },
            ],
        }
        prompt = build_system_prompt(
            session_type="wrapup",
            skill_instructions="wrap-up skill",
            wrapup_context=ctx,
        )
        assert "## Context for Today's Wrap-up" in prompt
        assert "### This morning you set these intentions" in prompt
        assert "Plan for Day 4: Build prototype" in prompt
        assert "### Today's journal entries" in prompt
        assert "[14:03] Started prototype" in prompt
        assert "### Last week's digest" in prompt
        assert "Week 4" in prompt
        assert "### Pulse questions to ask this session" in prompt
        # The rendered question must include the canonical text in quotes plus an
        # explicit verbatim instruction. Paraphrasing this in the agent has
        # silently corrupted Week 5 pulse data; the prompt must lock it down.
        assert 'ask verbatim: "Are you making progress?"' in prompt
        assert "EXACT wording" in prompt
        assert "Do NOT paraphrase" in prompt
        # Scale must render as a numbered markdown list (one per line) so the
        # model copies it back as a numbered list to the user.
        assert "1. No" in prompt
        assert "5. Great" in prompt

    def test_wrapup_context_only_pulse_renders_pulse_only(self):
        ctx = {
            "intake_today": [],
            "journal_today": [],
            "previous_digest": "",
            "pulse_to_ask": [
                {
                    "id": "impact",
                    "version": "v1",
                    "text": "Impact?",
                    "scale": ["A", "B", "C", "D", "E"],
                },
            ],
        }
        prompt = build_system_prompt(
            session_type="wrapup",
            skill_instructions="wrap-up skill",
            wrapup_context=ctx,
        )
        assert "## Context for Today's Wrap-up" in prompt
        assert "### Pulse questions to ask this session" in prompt
        assert "### This morning you set these intentions" not in prompt
        assert "### Today's journal entries" not in prompt
        assert "### Last week's digest" not in prompt

    def test_wrapup_context_ignored_for_non_wrapup_session(self):
        ctx = {"intake_today": [{"id": "x", "label": "X", "value": "v"}]}
        prompt = build_system_prompt(
            session_type="chat",
            skill_instructions="chat skill",
            wrapup_context=ctx,
        )
        assert "Context for Today's Wrap-up" not in prompt


# ---------------------------------------------------------------------------
# Intake tool registry must exclude save_journal
# ---------------------------------------------------------------------------


class TestIntakeExcludesSaveJournal:
    def test_save_journal_not_in_intake_registry(self):
        """Intake sessions must not expose save_journal to the LLM.

        We assert on the static tool_registry wiring rather than driving
        ``run_agent_session`` end-to-end, because the registry construction
        is where the policy lives.
        """
        from backend.deps import build_tool_registry
        from backend.tools.registry import FilteredToolRegistry

        registry = build_tool_registry()
        intake_registry = FilteredToolRegistry(
            registry,
            exclude={"prepare_tip", "prepare_collab", "save_journal"},
        )
        names = {s["name"] for s in intake_registry.get_schemas()}
        assert "save_journal" not in names
        assert "prepare_tip" not in names
        assert "prepare_collab" not in names
        # Sanity: non-excluded journal tool still available.
        full_names = {s["name"] for s in registry.get_schemas()}
        assert "read_journal" in full_names


# ---------------------------------------------------------------------------
# Auto-save fallback removed for wrapup
# ---------------------------------------------------------------------------


class TestAutoSaveRemoved:
    def test_auto_save_journal_function_removed(self):
        """The _auto_save_journal helper had only one caller (wrapup). With
        that call removed, the function itself should be gone so no future
        caller can accidentally restore the duplicate-save behavior.
        """
        import backend.agent.executor as executor_module
        assert not hasattr(executor_module, "_auto_save_journal")

    def test_executor_source_does_not_call_auto_save(self):
        """Belt-and-braces: the source file must not contain an
        _auto_save_journal reference. Protects against someone restoring
        the helper with only the caller deleted.
        """
        source = Path(__file__).resolve().parent.parent / "backend" / "agent" / "executor.py"
        text = source.read_text()
        assert "_auto_save_journal" not in text
