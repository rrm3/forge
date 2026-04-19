"""Tests for _compute_active_preview helper and repo provenance round-trips.

Covers the Week 5 Phase 2 preview-card-hydration design:
docs/designs/2026-04-19-preview-card-hydration.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from backend.api import sessions as sessions_api
from backend.models import Collaboration, Message, Tip, UserIdea
from backend.repository.collabs import MemoryCollabRepository
from backend.repository.tips import MemoryTipRepository
from backend.repository.user_ideas import MemoryUserIdeaRepository


# ---------------------------------------------------------------------------
# Repository round-trip tests — new provenance fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tip_repo_roundtrip_with_source_fields():
    repo = MemoryTipRepository()
    tip = Tip(
        tip_id="tip-1",
        author_id="alice",
        content="Body",
        source_session_id="sess-A",
        source_tool_call_id="tc-1",
    )
    await repo.create(tip)

    got = await repo.get("tip-1")
    assert got is not None
    assert got.source_session_id == "sess-A"
    assert got.source_tool_call_id == "tc-1"


@pytest.mark.asyncio
async def test_tip_repo_roundtrip_without_source_fields_defaults_to_empty():
    repo = MemoryTipRepository()
    tip = Tip(tip_id="tip-legacy", author_id="alice", content="Body")
    await repo.create(tip)

    got = await repo.get("tip-legacy")
    assert got is not None
    assert got.source_session_id == ""
    assert got.source_tool_call_id == ""


@pytest.mark.asyncio
async def test_tip_repo_dynamodb_serialize_deserialize_legacy():
    """Ensure a DynamoDB-style dict missing source_* deserializes cleanly."""
    from backend.repository.tips import DynamoDBTipRepository

    tip = Tip(
        tip_id="tip-2",
        author_id="bob",
        content="hello",
        source_session_id="sess-B",
        source_tool_call_id="tc-2",
    )
    # Call the unbound helpers directly (both are self-contained — they don't
    # touch self.* state, just transform dicts).
    serialized = DynamoDBTipRepository._serialize_tip(None, tip)  # type: ignore[arg-type]
    assert serialized["source_session_id"] == "sess-B"
    assert serialized["source_tool_call_id"] == "tc-2"

    # Deserialize a legacy item (pre-W5-P2) missing the new attrs.
    legacy = {
        "tip_id": "tip-old",
        "author_id": "carol",
        "content": "body",
        "created_at": datetime.now(UTC).isoformat(),
    }
    out = DynamoDBTipRepository._deserialize_tip(None, legacy)  # type: ignore[arg-type]
    assert out.source_session_id == ""
    assert out.source_tool_call_id == ""


@pytest.mark.asyncio
async def test_tip_find_by_source_memory():
    repo = MemoryTipRepository()
    t1 = Tip(tip_id="t1", author_id="u1", content="A",
             source_session_id="s1", source_tool_call_id="tc-1")
    t2 = Tip(tip_id="t2", author_id="u1", content="B",
             source_session_id="s1", source_tool_call_id="tc-2")
    t3 = Tip(tip_id="t3", author_id="u2", content="C",
             source_session_id="s1", source_tool_call_id="tc-1")
    await repo.create(t1)
    await repo.create(t2)
    await repo.create(t3)

    hit = await repo.find_by_source("u1", "s1", "tc-1")
    assert hit is not None and hit.tip_id == "t1"

    # Wrong user_id — doesn't match despite matching session+tool
    assert (await repo.find_by_source("u3", "s1", "tc-1")) is None

    # Missing tool_call — no match
    assert (await repo.find_by_source("u1", "s1", "tc-99")) is None

    # Empty inputs fail closed
    assert (await repo.find_by_source("u1", "", "tc-1")) is None
    assert (await repo.find_by_source("u1", "s1", "")) is None
    assert (await repo.find_by_source("", "s1", "tc-1")) is None


@pytest.mark.asyncio
async def test_collab_repo_roundtrip_with_source_fields():
    repo = MemoryCollabRepository()
    c = Collaboration(
        collab_id="c1",
        author_id="alice",
        title="T",
        problem="P",
        source_session_id="sess-A",
        source_tool_call_id="tc-9",
    )
    await repo.create(c)
    got = await repo.get("c1")
    assert got is not None
    assert got.source_session_id == "sess-A"
    assert got.source_tool_call_id == "tc-9"


@pytest.mark.asyncio
async def test_collab_repo_dynamodb_legacy_deserialize():
    from backend.repository.collabs import DynamoDBCollabRepository

    legacy = {
        "collab_id": "c-old",
        "author_id": "alice",
        "title": "T",
        "problem": "P",
        "created_at": datetime.now(UTC).isoformat(),
    }
    out = DynamoDBCollabRepository._deserialize_collab(None, legacy)  # type: ignore[arg-type]
    assert out.source_session_id == ""
    assert out.source_tool_call_id == ""


@pytest.mark.asyncio
async def test_collab_find_by_source_memory():
    repo = MemoryCollabRepository()
    c = Collaboration(
        collab_id="c1",
        author_id="u1",
        title="T",
        problem="P",
        source_session_id="s1",
        source_tool_call_id="tc-7",
    )
    await repo.create(c)

    assert (await repo.find_by_source("u1", "s1", "tc-7")).collab_id == "c1"
    assert (await repo.find_by_source("u2", "s1", "tc-7")) is None
    assert (await repo.find_by_source("u1", "s2", "tc-7")) is None


@pytest.mark.asyncio
async def test_user_idea_roundtrip_with_source_tool_call_id():
    repo = MemoryUserIdeaRepository()
    idea = UserIdea(
        user_id="u1",
        idea_id="i1",
        title="T",
        description="D",
        source="brainstorm",
        source_session_id="s1",
        source_tool_call_id="tc-5",
    )
    await repo.create(idea)
    got = await repo.get("u1", "i1")
    assert got is not None
    assert got.source_tool_call_id == "tc-5"
    assert got.source_session_id == "s1"


@pytest.mark.asyncio
async def test_user_idea_legacy_has_empty_tool_call_id():
    """UserIdea created without the new field defaults to empty string."""
    idea = UserIdea(
        user_id="u1",
        idea_id="legacy",
        title="T",
        description="D",
    )
    assert idea.source_tool_call_id == ""


# ---------------------------------------------------------------------------
# _compute_active_preview tests
# ---------------------------------------------------------------------------


def _mk_tool_call(tool_name: str, tool_call_id: str, args: dict) -> Message:
    return Message(
        role="tool_call",
        content=json.dumps(args),
        tool_name=tool_name,
        tool_call_id=tool_call_id,
    )


def _wire_repos(tips=None, collabs=None, user_ideas=None):
    """Temporarily swap the module-level repos used by _compute_active_preview."""
    sessions_api._tips_repo = tips or MemoryTipRepository()
    sessions_api._collabs_repo = collabs or MemoryCollabRepository()
    sessions_api._user_ideas_repo = user_ideas or MemoryUserIdeaRepository()


@pytest.fixture(autouse=True)
def _reset_sessions_module_repos():
    # Save and restore around each test so we don't leak between tests.
    saved = (
        sessions_api._tips_repo,
        sessions_api._collabs_repo,
        sessions_api._user_ideas_repo,
    )
    yield
    (
        sessions_api._tips_repo,
        sessions_api._collabs_repo,
        sessions_api._user_ideas_repo,
    ) = saved


@pytest.mark.asyncio
async def test_active_preview_empty_transcript_returns_none():
    _wire_repos()
    result = await sessions_api._compute_active_preview("u1", "s1", [])
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_no_prepare_call_returns_none():
    _wire_repos()
    transcript = [
        Message(role="user", content="hi"),
        _mk_tool_call("save_journal", "tc-x", {"content": "log"}),
        Message(role="assistant", content="done"),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_unpublished_tip_returns_preview():
    _wire_repos()
    transcript = [
        _mk_tool_call(
            "prepare_tip",
            "tc-1",
            {"title": "My Tip", "content": "Body", "tags": ["a"], "department": "Sales"},
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is not None
    assert result["type"] == "tip"
    assert result["tool_call_id"] == "tc-1"
    assert result["title"] == "My Tip"
    assert result["department"] == "Sales"
    assert result["tags"] == ["a"]


@pytest.mark.asyncio
async def test_active_preview_published_tip_returns_none():
    tips = MemoryTipRepository()
    await tips.create(
        Tip(
            tip_id="t-1",
            author_id="u1",
            content="Body",
            source_session_id="s1",
            source_tool_call_id="tc-1",
        )
    )
    _wire_repos(tips=tips)
    transcript = [
        _mk_tool_call(
            "prepare_tip",
            "tc-1",
            {"title": "My Tip", "content": "Body", "department": "Sales"},
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_superseded_draft_returns_only_latest():
    """Two prepare calls in a session — only the latest is considered."""
    tips = MemoryTipRepository()
    await tips.create(
        Tip(
            tip_id="t-published",
            author_id="u1",
            content="Second draft",
            source_session_id="s1",
            source_tool_call_id="tc-2",
        )
    )
    _wire_repos(tips=tips)
    transcript = [
        _mk_tool_call("prepare_tip", "tc-1", {"title": "Draft A", "content": "A"}),
        _mk_tool_call("prepare_tip", "tc-2", {"title": "Draft B", "content": "B"}),
    ]
    # tc-2 is published — should be None, NOT resurrected tc-1.
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_latest_unpublished_after_older_published():
    """Older draft published, newer draft not yet — should show the newer one."""
    tips = MemoryTipRepository()
    await tips.create(
        Tip(
            tip_id="t-old",
            author_id="u1",
            content="Old",
            source_session_id="s1",
            source_tool_call_id="tc-1",
        )
    )
    _wire_repos(tips=tips)
    transcript = [
        _mk_tool_call("prepare_tip", "tc-1", {"title": "Old draft", "content": "Old"}),
        _mk_tool_call("prepare_tip", "tc-2", {"title": "New draft", "content": "New"}),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is not None
    assert result["tool_call_id"] == "tc-2"
    assert result["title"] == "New draft"


@pytest.mark.asyncio
async def test_active_preview_idea_unpublished():
    _wire_repos()
    transcript = [
        _mk_tool_call(
            "prepare_idea",
            "tc-ia",
            {"title": "An idea", "description": "Desc", "tags": ["x"]},
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is not None
    assert result["type"] == "idea"
    assert result["tool_call_id"] == "tc-ia"


@pytest.mark.asyncio
async def test_active_preview_idea_published_returns_none():
    ideas = MemoryUserIdeaRepository()
    await ideas.create(
        UserIdea(
            user_id="u1",
            idea_id="idea-1",
            title="T",
            description="D",
            source_session_id="s1",
            source_tool_call_id="tc-ia",
        )
    )
    _wire_repos(user_ideas=ideas)
    transcript = [
        _mk_tool_call("prepare_idea", "tc-ia", {"title": "T", "description": "D"}),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_collab_unpublished():
    _wire_repos()
    transcript = [
        _mk_tool_call(
            "prepare_collab",
            "tc-c",
            {
                "title": "Build X",
                "problem": "Solve Y",
                "needed_skills": ["python"],
                "time_commitment": "A few hours",
                "tags": ["infra"],
            },
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is not None
    assert result["type"] == "collab"
    assert result["tool_call_id"] == "tc-c"
    assert result["needed_skills"] == ["python"]


@pytest.mark.asyncio
async def test_active_preview_collab_published_returns_none():
    collabs = MemoryCollabRepository()
    await collabs.create(
        Collaboration(
            collab_id="c-1",
            author_id="u1",
            title="T",
            problem="P",
            source_session_id="s1",
            source_tool_call_id="tc-c",
        )
    )
    _wire_repos(collabs=collabs)
    transcript = [
        _mk_tool_call("prepare_collab", "tc-c", {"title": "T", "problem": "P"}),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_malformed_args_returns_none():
    """Malformed tool_call.content should fail closed to None, not raise."""
    _wire_repos()
    transcript = [
        Message(
            role="tool_call",
            content="{not json",
            tool_name="prepare_tip",
            tool_call_id="tc-bad",
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_missing_tool_call_id_returns_none():
    """A prepare_tip row with no tool_call_id cannot be tracked — return None."""
    _wire_repos()
    transcript = [
        Message(
            role="tool_call",
            content=json.dumps({"title": "T", "content": "B"}),
            tool_name="prepare_tip",
            tool_call_id=None,
        ),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None


@pytest.mark.asyncio
async def test_active_preview_repo_exception_fails_closed(monkeypatch):
    """If the repo lookup raises, return None (never 500)."""
    class BoomRepo(MemoryTipRepository):
        async def find_by_source(self, *a, **kw):
            raise RuntimeError("boom")

    _wire_repos(tips=BoomRepo())
    transcript = [
        _mk_tool_call("prepare_tip", "tc-1", {"title": "x", "content": "y"}),
    ]
    result = await sessions_api._compute_active_preview("u1", "s1", transcript)
    assert result is None
