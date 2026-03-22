"""Session CRUD endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.auth import AuthUser
from backend.models import Session
from backend.storage import load_transcript

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_sessions_repo = None
_storage = None


def set_sessions_deps(sessions_repo, storage):
    global _sessions_repo, _storage
    _sessions_repo = sessions_repo
    _storage = storage


class RenameRequest(BaseModel):
    title: str


@router.get("")
async def list_sessions(user: AuthUser):
    """List the current user's sessions, sorted by updated_at descending."""
    sessions = await _sessions_repo.list(user.user_id)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return [s.model_dump(mode="json") for s in sessions]


@router.post("")
async def create_session(user: AuthUser):
    """Create a new empty session."""
    session = Session(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        title="",
    )
    await _sessions_repo.create(session)
    return session.model_dump(mode="json")


@router.get("/{session_id}")
async def get_session(session_id: str, user: AuthUser):
    """Get session metadata and transcript."""
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = await load_transcript(_storage, user.user_id, session_id)
    result = session.model_dump(mode="json")
    result["transcript"] = [m.model_dump(mode="json") for m in transcript] if transcript else []
    return result


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: AuthUser):
    """Delete session metadata and transcript."""
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Intake sessions ("Getting Started") cannot be deleted
    if session.type == "intake":
        raise HTTPException(status_code=403, detail="Intake session cannot be deleted")

    # Delete transcript from storage
    key = f"sessions/{user.user_id}/{session_id}.json"
    await _storage.delete(key)

    # Delete session metadata
    await _sessions_repo.delete(user.user_id, session_id)
    return {"status": "deleted"}


@router.patch("/{session_id}")
async def rename_session(session_id: str, body: RenameRequest, user: AuthUser):
    """Rename a session."""
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = body.title
    session.updated_at = datetime.now(UTC)
    await _sessions_repo.update(session)
    return session.model_dump(mode="json")
