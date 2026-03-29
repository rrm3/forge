"""Tests for tool registry and tool implementations using in-memory repositories."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.models import Idea, JournalEntry, UserProfile
from backend.repository.ideas import MemoryIdeaRepository
from backend.repository.journal import MemoryJournalRepository
from backend.repository.profiles import MemoryProfileRepository
from backend.tools.ideas import list_ideas, propose_idea
from backend.tools.journal import read_journal, save_journal
from backend.tools.profile import read_profile, search_profiles, update_profile
from backend.tools.registry import ToolContext, ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def profile_repo():
    return MemoryProfileRepository()


@pytest.fixture
def journal_repo():
    return MemoryJournalRepository()


@pytest.fixture
def idea_repo():
    return MemoryIdeaRepository()


@pytest.fixture
def ctx(profile_repo, journal_repo, idea_repo):
    return ToolContext(
        user_id="user-1",
        session_id="sess-1",
        repos={
            "profiles": profile_repo,
            "journal": journal_repo,
            "ideas": idea_repo,
        },
    )


@pytest.fixture
def alice_profile():
    return UserProfile(
        user_id="user-1",
        email="alice@example.com",
        name="Alice",
        title="Engineer",
        department="Platform",
        team="AI",
        ai_experience_level="intermediate",
        interests=["machine learning", "Python"],
        tools_used=["Claude", "LangChain"],
        goals=["Learn more about RAG"],
    )


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get_schemas(self):
        registry = ToolRegistry()
        schema = {
            "name": "my_tool",
            "description": "Does something",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }

        async def handler(**kwargs):
            return "ok"

        registry.register(schema, handler)
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "my_tool"

    @pytest.mark.asyncio
    async def test_execute_known_tool(self):
        registry = ToolRegistry()
        schema = {
            "name": "echo",
            "description": "Echoes input",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }

        async def echo(text: str, context: ToolContext) -> str:
            return f"echo: {text}"

        registry.register(schema, echo)

        ctx = ToolContext(user_id="u1", session_id="s1")
        result = await registry.execute("echo", {"text": "hello"}, ctx)
        assert result == "echo: hello"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        ctx = ToolContext(user_id="u1", session_id="s1")
        result = await registry.execute("nonexistent", {}, ctx)
        assert "Unknown tool" in result

    def test_get_schemas_returns_copy(self):
        registry = ToolRegistry()
        schemas1 = registry.get_schemas()
        schemas1.append({"name": "injected"})
        schemas2 = registry.get_schemas()
        assert len(schemas2) == 0  # original not mutated


# ---------------------------------------------------------------------------
# Profile tools
# ---------------------------------------------------------------------------


class TestReadProfile:
    @pytest.mark.asyncio
    async def test_read_existing_profile(self, ctx, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)
        result = await read_profile(context=ctx)

        assert "Alice" in result
        assert "Engineer" in result
        assert "intermediate" in result
        assert "machine learning" in result

    @pytest.mark.asyncio
    async def test_read_missing_profile(self, ctx):
        result = await read_profile(context=ctx)
        assert "No profile found" in result

    @pytest.mark.asyncio
    async def test_read_profile_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await read_profile(context=ctx)
        assert "not available" in result


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_update_existing_profile(self, ctx, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)

        with patch("backend.tools.profile.index_document", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = {"error": None}
            result = await update_profile(
                fields={"title": "Senior Engineer", "team": "Infrastructure"},
                context=ctx,
            )

        assert "updated successfully" in result
        assert "title" in result

        updated = await profile_repo.get("user-1")
        assert updated.title == "Senior Engineer"
        assert updated.team == "Infrastructure"
        # Unchanged fields preserved
        assert updated.name == "Alice"

    @pytest.mark.asyncio
    async def test_update_missing_profile(self, ctx):
        result = await update_profile(fields={"title": "Eng"}, context=ctx)
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_update_no_valid_fields(self, ctx, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)
        result = await update_profile(fields={"nonsense": "value"}, context=ctx)
        assert "No updatable fields provided" in result

    @pytest.mark.asyncio
    async def test_update_empty_fields(self, ctx, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)
        result = await update_profile(fields={}, context=ctx)
        assert "No fields" in result

    @pytest.mark.asyncio
    async def test_update_indexing_failure_is_swallowed(self, ctx, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)

        with patch("backend.tools.profile.index_document", side_effect=RuntimeError("lance down")):
            result = await update_profile(fields={"team": "NewTeam"}, context=ctx)

        # Should still report success; indexing failure is non-fatal
        assert "updated successfully" in result

    @pytest.mark.asyncio
    async def test_update_profile_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await update_profile(fields={"title": "Eng"}, context=ctx)
        assert "not available" in result


class TestSearchProfiles:
    @pytest.mark.asyncio
    async def test_search_profiles_no_results(self, ctx):
        with patch("backend.tools.profile.search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "error": None}
            result = await search_profiles(query="machine learning", context=ctx)

        assert "No profiles found" in result

    @pytest.mark.asyncio
    async def test_search_profiles_with_results(self, ctx):
        with patch("backend.tools.profile.search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "results": [
                    {
                        "score": 0.9,
                        "metadata": {"name": "Bob", "user_id": "user-2"},
                        "match_context": "Expert in machine learning and Python",
                    }
                ],
                "error": None,
            }
            result = await search_profiles(query="machine learning", context=ctx)

        assert "Bob" in result
        assert "machine learning" in result

    @pytest.mark.asyncio
    async def test_search_profiles_error(self, ctx):
        with patch("backend.tools.profile.search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": [], "error": "lance connection failed"}
            result = await search_profiles(query="AI", context=ctx)

        assert "Search failed" in result


# ---------------------------------------------------------------------------
# Journal tools
# ---------------------------------------------------------------------------


class TestSaveJournal:
    @pytest.mark.asyncio
    async def test_save_creates_entry(self, ctx, journal_repo):
        result = await save_journal(content="Learned about RAG today.", context=ctx)

        assert "saved" in result
        assert "ID:" in result

        entries = await journal_repo.list("user-1")
        assert len(entries) == 1
        assert entries[0].content == "Learned about RAG today."
        assert entries[0].user_id == "user-1"

    @pytest.mark.asyncio
    async def test_save_with_tags(self, ctx, journal_repo):
        result = await save_journal(content="Tried prompt chaining.", tags=["prompting", "llm"], context=ctx)

        assert "Tags: prompting, llm" in result

        entries = await journal_repo.list("user-1")
        assert entries[0].tags == ["prompting", "llm"]

    @pytest.mark.asyncio
    async def test_save_without_tags(self, ctx, journal_repo):
        result = await save_journal(content="Quick note.", context=ctx)
        assert "Tags" not in result

        entries = await journal_repo.list("user-1")
        assert entries[0].tags == []

    @pytest.mark.asyncio
    async def test_save_journal_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await save_journal(content="note", context=ctx)
        assert "not available" in result


class TestReadJournal:
    @pytest.mark.asyncio
    async def test_read_empty(self, ctx):
        result = await read_journal(context=ctx)
        assert "No journal entries" in result

    @pytest.mark.asyncio
    async def test_read_entries(self, ctx, journal_repo):
        entry = JournalEntry(entry_id="e1", user_id="user-1", content="Day one notes.", tags=["work"])
        await journal_repo.create(entry)

        result = await read_journal(context=ctx)
        assert "Day one notes." in result
        assert "work" in result

    @pytest.mark.asyncio
    async def test_read_with_limit(self, ctx, journal_repo):
        for i in range(5):
            await journal_repo.create(
                JournalEntry(entry_id=f"e{i}", user_id="user-1", content=f"Entry {i}")
            )

        result = await read_journal(context=ctx, limit=2)
        # Just confirm it ran without error and returned content
        assert "entry" in result.lower()

    @pytest.mark.asyncio
    async def test_read_invalid_date(self, ctx):
        result = await read_journal(context=ctx, date_from="not-a-date")
        assert "Invalid date_from" in result

    @pytest.mark.asyncio
    async def test_read_journal_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await read_journal(context=ctx)
        assert "not available" in result


# ---------------------------------------------------------------------------
# Ideas tools
# ---------------------------------------------------------------------------


class TestProposeIdea:
    @pytest.mark.asyncio
    async def test_propose_creates_idea(self, ctx, idea_repo):
        result = await propose_idea(
            title="AI Code Review Bot",
            description="Automate code reviews using Claude.",
            context=ctx,
        )

        assert "submitted" in result
        assert "AI Code Review Bot" in result
        assert "ID:" in result

        ideas = await idea_repo.list()
        assert len(ideas) == 1
        assert ideas[0].title == "AI Code Review Bot"
        assert ideas[0].proposed_by == "user-1"
        assert ideas[0].status == "open"

    @pytest.mark.asyncio
    async def test_propose_with_skills(self, ctx, idea_repo):
        result = await propose_idea(
            title="Semantic Search",
            description="Add vector search to our docs.",
            required_skills=["Python", "LanceDB"],
            context=ctx,
        )

        assert "Python" in result or "LanceDB" in result

        ideas = await idea_repo.list()
        assert ideas[0].required_skills == ["Python", "LanceDB"]

    @pytest.mark.asyncio
    async def test_propose_pulls_proposer_name_from_profile(self, ctx, idea_repo, profile_repo, alice_profile):
        await profile_repo.create(alice_profile)

        await propose_idea(title="Cool Idea", description="desc", context=ctx)

        ideas = await idea_repo.list()
        assert ideas[0].proposed_by_name == "Alice"

    @pytest.mark.asyncio
    async def test_propose_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await propose_idea(title="t", description="d", context=ctx)
        assert "not available" in result


class TestListIdeas:
    @pytest.mark.asyncio
    async def test_list_empty(self, ctx):
        result = await list_ideas(context=ctx)
        assert "No ideas found" in result

    @pytest.mark.asyncio
    async def test_list_all_ideas(self, ctx, idea_repo):
        for i, status in enumerate(["open", "open", "in_progress"]):
            await idea_repo.create(
                Idea(
                    idea_id=f"i{i}",
                    title=f"Idea {i}",
                    description="A cool project",
                    proposed_by="user-1",
                    status=status,
                )
            )

        result = await list_ideas(context=ctx)
        assert "3 idea" in result
        assert "OPEN" in result
        assert "IN_PROGRESS" in result

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, ctx, idea_repo):
        await idea_repo.create(
            Idea(idea_id="i1", title="Open Idea", description="d", proposed_by="u1", status="open")
        )
        await idea_repo.create(
            Idea(idea_id="i2", title="Done Idea", description="d", proposed_by="u1", status="completed")
        )

        result = await list_ideas(context=ctx, status="open")
        assert "Open Idea" in result
        assert "Done Idea" not in result

    @pytest.mark.asyncio
    async def test_list_shows_required_skills(self, ctx, idea_repo):
        await idea_repo.create(
            Idea(
                idea_id="i1",
                title="ML Pipeline",
                description="Build it",
                proposed_by="u1",
                required_skills=["PyTorch", "AWS"],
            )
        )

        result = await list_ideas(context=ctx)
        assert "PyTorch" in result
        assert "AWS" in result

    @pytest.mark.asyncio
    async def test_list_no_repo(self):
        ctx = ToolContext(user_id="u1", session_id="s1", repos={})
        result = await list_ideas(context=ctx)
        assert "not available" in result
