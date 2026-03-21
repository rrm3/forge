"""Integration tests for the FastAPI API routes.

Uses the dev_mode config with in-memory repos and local storage.
"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Force dev_mode before importing the app
os.environ["DEV_MODE"] = "true"

from backend.main import app, repos, storage
from backend.models import Idea, JournalEntry, Session, UserProfile
from backend.storage import save_transcript
from backend.models import Message


DEV_HEADERS = {"X-Dev-User-Id": "alice"}


@pytest.fixture(autouse=True)
def _clean_repos():
    """Reset in-memory repos between tests."""
    repos["sessions"]._sessions.clear()
    repos["profiles"]._profiles.clear()
    repos["journal"]._entries.clear()
    repos["ideas"]._ideas.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_no_auth_required(self, client):
        """Health endpoint works without auth headers."""
        resp = client.get("/api/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TestSessions:
    def test_create_session(self, client):
        resp = client.post("/api/sessions", headers=DEV_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["user_id"] == "alice"
        assert data["title"] == ""

    def test_list_sessions_empty(self, client):
        resp = client.get("/api/sessions", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions(self, client):
        # Create two sessions
        client.post("/api/sessions", headers=DEV_HEADERS)
        client.post("/api/sessions", headers=DEV_HEADERS)

        resp = client.get("/api/sessions", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_session(self, client):
        create_resp = client.post("/api/sessions", headers=DEV_HEADERS)
        sid = create_resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{sid}", headers=DEV_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["transcript"] == []

    def test_get_session_not_found(self, client):
        resp = client.get("/api/sessions/nonexistent", headers=DEV_HEADERS)
        assert resp.status_code == 404

    def test_delete_session(self, client):
        create_resp = client.post("/api/sessions", headers=DEV_HEADERS)
        sid = create_resp.json()["session_id"]

        resp = client.delete(f"/api/sessions/{sid}", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify it's gone
        resp = client.get(f"/api/sessions/{sid}", headers=DEV_HEADERS)
        assert resp.status_code == 404

    def test_delete_session_not_found(self, client):
        resp = client.delete("/api/sessions/nonexistent", headers=DEV_HEADERS)
        assert resp.status_code == 404

    def test_rename_session(self, client):
        create_resp = client.post("/api/sessions", headers=DEV_HEADERS)
        sid = create_resp.json()["session_id"]

        resp = client.patch(
            f"/api/sessions/{sid}",
            headers=DEV_HEADERS,
            json={"title": "My Chat"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Chat"

    def test_rename_session_not_found(self, client):
        resp = client.patch(
            "/api/sessions/nonexistent",
            headers=DEV_HEADERS,
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    def test_sessions_sorted_by_updated(self, client):
        """Sessions should be returned newest first."""
        import asyncio
        from datetime import UTC, datetime, timedelta

        loop = asyncio.new_event_loop()

        s1 = Session(session_id="s1", user_id="alice", title="Old")
        s1.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        s2 = Session(session_id="s2", user_id="alice", title="New")
        s2.updated_at = datetime(2026, 3, 1, tzinfo=UTC)

        loop.run_until_complete(repos["sessions"].create(s1))
        loop.run_until_complete(repos["sessions"].create(s2))
        loop.close()

        resp = client.get("/api/sessions", headers=DEV_HEADERS)
        data = resp.json()
        assert len(data) == 2
        assert data[0]["session_id"] == "s2"
        assert data[1]["session_id"] == "s1"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class TestProfile:
    def _seed_profile(self):
        import asyncio
        loop = asyncio.new_event_loop()
        profile = UserProfile(
            user_id="alice",
            email="alice@example.com",
            name="Alice",
            title="Engineer",
            department="R&D",
        )
        loop.run_until_complete(repos["profiles"].create(profile))
        loop.close()

    def test_get_profile(self, client):
        self._seed_profile()
        resp = client.get("/api/profile", headers=DEV_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["department"] == "R&D"

    def test_get_profile_not_found(self, client):
        resp = client.get("/api/profile", headers=DEV_HEADERS)
        assert resp.status_code == 404

    def test_update_profile(self, client):
        self._seed_profile()
        resp = client.put(
            "/api/profile",
            headers=DEV_HEADERS,
            json={"title": "Senior Engineer"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Senior Engineer"

    def test_update_profile_not_found(self, client):
        resp = client.put(
            "/api/profile",
            headers=DEV_HEADERS,
            json={"title": "Nope"},
        )
        assert resp.status_code == 404

    def test_update_profile_empty_body(self, client):
        resp = client.put(
            "/api/profile",
            headers=DEV_HEADERS,
            json={},
        )
        assert resp.status_code == 400

    def test_profile_requires_auth(self, client):
        """Profile endpoint returns 401 without dev header when not in dev mode.
        In dev mode it defaults to alice, so this just verifies the route is callable."""
        resp = client.get("/api/profile")
        # In dev mode, defaults to alice - should be 404 (no profile seeded)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class TestJournal:
    def test_list_journal_empty(self, client):
        resp = client.get("/api/journal", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_journal_with_entries(self, client):
        import asyncio
        loop = asyncio.new_event_loop()
        entry = JournalEntry(
            entry_id="e1",
            user_id="alice",
            content="Learned about embeddings today",
            tags=["ai", "learning"],
        )
        loop.run_until_complete(repos["journal"].create(entry))
        loop.close()

        resp = client.get("/api/journal", headers=DEV_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "Learned about embeddings today"
        assert "ai" in data[0]["tags"]

    def test_list_journal_limit(self, client):
        import asyncio
        loop = asyncio.new_event_loop()
        for i in range(5):
            entry = JournalEntry(
                entry_id=f"e{i}",
                user_id="alice",
                content=f"Entry {i}",
            )
            loop.run_until_complete(repos["journal"].create(entry))
        loop.close()

        resp = client.get("/api/journal?limit=3", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_journal_wrong_user(self, client):
        """Bob's entries shouldn't show up for alice."""
        import asyncio
        loop = asyncio.new_event_loop()
        entry = JournalEntry(
            entry_id="e1",
            user_id="bob",
            content="Bob's entry",
        )
        loop.run_until_complete(repos["journal"].create(entry))
        loop.close()

        resp = client.get("/api/journal", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Ideas
# ---------------------------------------------------------------------------

class TestIdeas:
    def test_list_ideas_empty(self, client):
        resp = client.get("/api/ideas", headers=DEV_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_ideas(self, client):
        import asyncio
        loop = asyncio.new_event_loop()
        idea = Idea(
            idea_id="i1",
            title="AI Code Review",
            description="Use LLMs for code review",
            proposed_by="alice",
            proposed_by_name="Alice",
            status="open",
        )
        loop.run_until_complete(repos["ideas"].create(idea))
        loop.close()

        resp = client.get("/api/ideas", headers=DEV_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "AI Code Review"

    def test_list_ideas_status_filter(self, client):
        import asyncio
        loop = asyncio.new_event_loop()
        open_idea = Idea(
            idea_id="i1",
            title="Open Idea",
            description="An open idea",
            proposed_by="alice",
            status="open",
        )
        closed_idea = Idea(
            idea_id="i2",
            title="Completed Idea",
            description="A completed idea",
            proposed_by="alice",
            status="completed",
        )
        loop.run_until_complete(repos["ideas"].create(open_idea))
        loop.run_until_complete(repos["ideas"].create(closed_idea))
        loop.close()

        resp = client.get("/api/ideas?status=open", headers=DEV_HEADERS)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "open"

    def test_list_ideas_limit(self, client):
        import asyncio
        loop = asyncio.new_event_loop()
        for i in range(5):
            idea = Idea(
                idea_id=f"i{i}",
                title=f"Idea {i}",
                description=f"Description {i}",
                proposed_by="alice",
            )
            loop.run_until_complete(repos["ideas"].create(idea))
        loop.close()

        resp = client.get("/api/ideas?limit=2", headers=DEV_HEADERS)
        assert len(resp.json()) == 2



# Chat cancel endpoint removed in v2 - cancellation is now via WebSocket
