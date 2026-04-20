"""Tests for in-memory repository implementations."""

import pytest
from datetime import datetime, timezone

from backend.models import Idea, JournalEntry, Session, UserProfile
from backend.repository.ideas import MemoryIdeaRepository
from backend.repository.journal import MemoryJournalRepository
from backend.repository.profiles import MemoryProfileRepository
from backend.repository.sessions import MemorySessionRepository


# --- Session repository ---


@pytest.fixture
def session_repo():
    return MemorySessionRepository()


@pytest.fixture
def sample_session():
    return Session(
        session_id="sess-1",
        user_id="user-1",
        title="Test Session",
        message_count=3,
        summary="A summary",
    )


@pytest.mark.asyncio
async def test_session_create_and_get(session_repo, sample_session):
    await session_repo.create(sample_session)
    result = await session_repo.get("user-1", "sess-1")
    assert result is not None
    assert result.session_id == "sess-1"
    assert result.title == "Test Session"


@pytest.mark.asyncio
async def test_session_get_missing(session_repo):
    result = await session_repo.get("user-1", "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_session_list(session_repo):
    s1 = Session(session_id="sess-1", user_id="user-1", title="First")
    s2 = Session(session_id="sess-2", user_id="user-1", title="Second")
    s3 = Session(session_id="sess-3", user_id="user-2", title="Other user")
    for s in [s1, s2, s3]:
        await session_repo.create(s)

    results = await session_repo.list("user-1")
    assert len(results) == 2
    ids = {r.session_id for r in results}
    assert ids == {"sess-1", "sess-2"}


@pytest.mark.asyncio
async def test_session_list_empty(session_repo):
    results = await session_repo.list("nobody")
    assert results == []


@pytest.mark.asyncio
async def test_session_update(session_repo, sample_session):
    await session_repo.create(sample_session)
    sample_session.title = "Updated Title"
    sample_session.message_count = 10
    await session_repo.update(sample_session)

    result = await session_repo.get("user-1", "sess-1")
    assert result.title == "Updated Title"
    assert result.message_count == 10


@pytest.mark.asyncio
async def test_session_update_sets_updated_at(session_repo, sample_session):
    await session_repo.create(sample_session)
    await session_repo.update(sample_session)

    result = await session_repo.get("user-1", "sess-1")
    # updated_at is set to datetime.now(UTC) on update; just verify it's a datetime
    assert isinstance(result.updated_at, datetime)


@pytest.mark.asyncio
async def test_session_delete(session_repo, sample_session):
    await session_repo.create(sample_session)
    await session_repo.delete("user-1", "sess-1")
    result = await session_repo.get("user-1", "sess-1")
    assert result is None


@pytest.mark.asyncio
async def test_session_delete_nonexistent(session_repo):
    # Should not raise
    await session_repo.delete("user-1", "nonexistent")


# --- Profile repository ---


@pytest.fixture
def profile_repo():
    return MemoryProfileRepository()


@pytest.fixture
def sample_profile():
    return UserProfile(
        user_id="user-1",
        email="alice@example.com",
        name="Alice",
        title="Engineer",
        interests=["AI", "Python"],
    )


@pytest.mark.asyncio
async def test_profile_create_and_get(profile_repo, sample_profile):
    await profile_repo.create(sample_profile)
    result = await profile_repo.get("user-1")
    assert result is not None
    assert result.name == "Alice"
    assert result.email == "alice@example.com"


@pytest.mark.asyncio
async def test_profile_get_missing(profile_repo):
    result = await profile_repo.get("nobody")
    assert result is None


@pytest.mark.asyncio
async def test_profile_update(profile_repo, sample_profile):
    await profile_repo.create(sample_profile)
    await profile_repo.update("user-1", {"title": "Senior Engineer", "team": "Platform"})

    result = await profile_repo.get("user-1")
    assert result.title == "Senior Engineer"
    assert result.team == "Platform"
    # Unchanged fields preserved
    assert result.name == "Alice"
    assert result.email == "alice@example.com"


@pytest.mark.asyncio
async def test_profile_update_sets_updated_at(profile_repo, sample_profile):
    await profile_repo.create(sample_profile)
    await profile_repo.update("user-1", {"title": "New Title"})

    result = await profile_repo.get("user-1")
    # updated_at is set to datetime.now(UTC) on update; just verify it's a datetime
    assert isinstance(result.updated_at, datetime)


@pytest.mark.asyncio
async def test_profile_update_missing_is_noop(profile_repo):
    # Should not raise
    await profile_repo.update("nobody", {"title": "Doesn't matter"})


@pytest.mark.asyncio
async def test_profile_delete(profile_repo, sample_profile):
    await profile_repo.create(sample_profile)
    await profile_repo.delete("user-1")
    result = await profile_repo.get("user-1")
    assert result is None


@pytest.mark.asyncio
async def test_profile_delete_nonexistent(profile_repo):
    # Should not raise
    await profile_repo.delete("nobody")


# --- Journal repository ---


@pytest.fixture
def journal_repo():
    return MemoryJournalRepository()


def make_entry(entry_id: str, user_id: str = "user-1", content: str = "note", tags=None, created_at=None):
    kwargs = {"entry_id": entry_id, "user_id": user_id, "content": content}
    if tags:
        kwargs["tags"] = tags
    if created_at:
        kwargs["created_at"] = created_at
    return JournalEntry(**kwargs)


@pytest.mark.asyncio
async def test_journal_create_and_list(journal_repo):
    entry = make_entry("e1", tags=["work"])
    await journal_repo.create(entry)

    results = await journal_repo.list("user-1")
    assert len(results) == 1
    assert results[0].entry_id == "e1"
    assert results[0].tags == ["work"]


@pytest.mark.asyncio
async def test_journal_list_empty(journal_repo):
    results = await journal_repo.list("nobody")
    assert results == []


@pytest.mark.asyncio
async def test_journal_list_only_own_entries(journal_repo):
    await journal_repo.create(make_entry("e1", user_id="user-1"))
    await journal_repo.create(make_entry("e2", user_id="user-2"))

    results = await journal_repo.list("user-1")
    assert len(results) == 1
    assert results[0].entry_id == "e1"


@pytest.mark.asyncio
async def test_journal_list_date_filter(journal_repo):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    t3 = datetime(2026, 3, 1, tzinfo=timezone.utc)

    await journal_repo.create(make_entry("e1", created_at=t1))
    await journal_repo.create(make_entry("e2", created_at=t2))
    await journal_repo.create(make_entry("e3", created_at=t3))

    results = await journal_repo.list("user-1", date_from=t1, date_to=t2)
    ids = {r.entry_id for r in results}
    assert ids == {"e1", "e2"}


@pytest.mark.asyncio
async def test_journal_list_date_from_only(journal_repo):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, tzinfo=timezone.utc)

    await journal_repo.create(make_entry("e1", created_at=t1))
    await journal_repo.create(make_entry("e2", created_at=t2))

    cutoff = datetime(2026, 2, 1, tzinfo=timezone.utc)
    results = await journal_repo.list("user-1", date_from=cutoff)
    assert len(results) == 1
    assert results[0].entry_id == "e2"


@pytest.mark.asyncio
async def test_journal_list_limit(journal_repo):
    for i in range(10):
        await journal_repo.create(make_entry(f"e{i}"))

    results = await journal_repo.list("user-1", limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_journal_list_newest_first(journal_repo):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 1, tzinfo=timezone.utc)

    await journal_repo.create(make_entry("e1", created_at=t1))
    await journal_repo.create(make_entry("e2", created_at=t2))

    results = await journal_repo.list("user-1")
    assert results[0].entry_id == "e2"
    assert results[1].entry_id == "e1"


@pytest.mark.asyncio
async def test_journal_delete(journal_repo):
    entry = make_entry("e1")
    await journal_repo.create(entry)
    await journal_repo.delete("user-1", "e1")

    results = await journal_repo.list("user-1")
    assert results == []


@pytest.mark.asyncio
async def test_journal_delete_nonexistent(journal_repo):
    # Should not raise
    await journal_repo.delete("user-1", "nonexistent")


@pytest.mark.asyncio
async def test_dynamodb_journal_list_does_not_pass_limit_with_date_filter():
    """REGRESSION GUARD.

    DynamoDB `Limit` applies to rows examined BEFORE the FilterExpression.
    If we pass Limit=N alongside a date FilterExpression, DynamoDB reads
    exactly N rows in sort-key order and THEN filters by date. For a journal
    table whose sort key is random entry_id, this means "today's entries"
    can come back empty even when they exist.

    Verify that `list(date_from=..., date_to=...)` does NOT include Limit
    in the underlying query kwargs. And that `list()` with no date filter
    DOES include Limit (the cheap path when we just want N latest).
    """
    from unittest.mock import MagicMock, patch

    from backend.repository.journal import DynamoDBJournalRepository

    mock_table = MagicMock()
    mock_table.query = MagicMock(return_value={"Items": []})

    with patch("backend.repository.journal.boto3.resource"):
        repo = DynamoDBJournalRepository.__new__(DynamoDBJournalRepository)
        repo.table = mock_table

        await repo.list(
            "user-1",
            date_from=datetime(2026, 4, 14, tzinfo=timezone.utc),
            date_to=datetime(2026, 4, 15, tzinfo=timezone.utc),
            limit=10,
        )
        call_kwargs = mock_table.query.call_args.kwargs
        assert "Limit" not in call_kwargs, (
            "Do not pass Limit to DynamoDB query when a date FilterExpression "
            "is present — DynamoDB applies Limit before the filter, which can "
            "cause today's entries to be missed. Paginate and filter in code."
        )
        assert "FilterExpression" in call_kwargs

        # Reset and verify the no-filter path still sets Limit (cheap path)
        mock_table.query.reset_mock()
        mock_table.query = MagicMock(return_value={"Items": []})
        await repo.list("user-1", limit=10)
        call_kwargs = mock_table.query.call_args.kwargs
        assert call_kwargs.get("Limit") == 10


# --- Idea repository ---


@pytest.fixture
def idea_repo():
    return MemoryIdeaRepository()


def make_idea(idea_id: str, status: str = "open", proposed_by: str = "user-1"):
    return Idea(
        idea_id=idea_id,
        title=f"Idea {idea_id}",
        description="A great idea",
        proposed_by=proposed_by,
        status=status,
    )


@pytest.mark.asyncio
async def test_idea_create_and_get(idea_repo):
    idea = make_idea("idea-1")
    await idea_repo.create(idea)

    result = await idea_repo.get("idea-1")
    assert result is not None
    assert result.idea_id == "idea-1"
    assert result.title == "Idea idea-1"
    assert result.status == "open"


@pytest.mark.asyncio
async def test_idea_get_missing(idea_repo):
    result = await idea_repo.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_idea_list_all(idea_repo):
    await idea_repo.create(make_idea("i1", status="open"))
    await idea_repo.create(make_idea("i2", status="in_progress"))
    await idea_repo.create(make_idea("i3", status="open"))

    results = await idea_repo.list()
    assert len(results) == 3


@pytest.mark.asyncio
async def test_idea_list_status_filter(idea_repo):
    await idea_repo.create(make_idea("i1", status="open"))
    await idea_repo.create(make_idea("i2", status="in_progress"))
    await idea_repo.create(make_idea("i3", status="open"))

    results = await idea_repo.list(status_filter="open")
    assert len(results) == 2
    for r in results:
        assert r.status == "open"


@pytest.mark.asyncio
async def test_idea_list_empty(idea_repo):
    results = await idea_repo.list()
    assert results == []


@pytest.mark.asyncio
async def test_idea_list_limit(idea_repo):
    for i in range(10):
        await idea_repo.create(make_idea(f"i{i}"))

    results = await idea_repo.list(limit=4)
    assert len(results) == 4


@pytest.mark.asyncio
async def test_idea_update(idea_repo):
    idea = make_idea("idea-1")
    await idea_repo.create(idea)
    await idea_repo.update("idea-1", {"status": "in_progress", "proposed_by_name": "Alice"})

    result = await idea_repo.get("idea-1")
    assert result.status == "in_progress"
    assert result.proposed_by_name == "Alice"
    # Other fields unchanged
    assert result.title == "Idea idea-1"


@pytest.mark.asyncio
async def test_idea_update_interested_users(idea_repo):
    idea = make_idea("idea-1")
    await idea_repo.create(idea)
    await idea_repo.update("idea-1", {"interested_users": ["user-2", "user-3"]})

    result = await idea_repo.get("idea-1")
    assert result.interested_users == ["user-2", "user-3"]


@pytest.mark.asyncio
async def test_idea_update_missing_is_noop(idea_repo):
    # Should not raise
    await idea_repo.update("nonexistent", {"status": "archived"})
