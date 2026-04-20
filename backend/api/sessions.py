"""Session CRUD endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.auth import AuthUser
from backend.models import Message, Session
from backend.storage import load_transcript

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_sessions_repo = None
_storage = None
_tips_repo = None
_collabs_repo = None
_user_ideas_repo = None


def set_sessions_deps(sessions_repo, storage, tips_repo=None, collabs_repo=None, user_ideas_repo=None):
    global _sessions_repo, _storage, _tips_repo, _collabs_repo, _user_ideas_repo
    _sessions_repo = sessions_repo
    _storage = storage
    _tips_repo = tips_repo
    _collabs_repo = collabs_repo
    _user_ideas_repo = user_ideas_repo


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


_PREPARE_TOOLS = {"prepare_tip", "prepare_idea", "prepare_collab"}


def _find_latest_prepare_call(transcript: list[Message]) -> Message | None:
    """Walk the transcript in reverse and return the latest prepare_* tool_call message.

    Returns None if no prepare_* call exists. Superseded drafts are ignored —
    only the most recent call wins.
    """
    for msg in reversed(transcript):
        if msg.role == "tool_call" and msg.tool_name in _PREPARE_TOOLS:
            return msg
    return None


async def _compute_active_preview(user_id: str, session_id: str, transcript: list[Message]) -> dict | None:
    """Return the active preview for a session, or None.

    Scans the transcript for the latest `prepare_tip` / `prepare_idea` /
    `prepare_collab` tool_call. If a matching record exists in the target repo
    (user_id + source_session_id + source_tool_call_id), returns a "published"
    shape so the frontend can render the post-publish confirmation card on
    reload. Otherwise returns the editable preview built from the tool_call's
    args. Returns None only when there's no prepare call at all (or it can't
    be tracked / parsed).

    Fail-closed: any exception — malformed transcript, repo hiccup, missing
    repo dep — returns None. A single bad session must not break session load.
    """
    try:
        latest = _find_latest_prepare_call(transcript)
        if latest is None:
            return None

        tool_call_id = latest.tool_call_id or ""
        if not tool_call_id:
            # No way to track provenance without a tool_call_id — skip.
            return None

        try:
            args = json.loads(latest.content) if isinstance(latest.content, str) else (latest.content or {})
        except (ValueError, TypeError):
            return None
        if not isinstance(args, dict):
            return None

        tool_name = latest.tool_name

        if tool_name == "prepare_tip":
            if _tips_repo is None:
                return None
            existing = await _tips_repo.find_by_source(user_id, session_id, tool_call_id)
            if existing is not None:
                # Direct attribute access — if a future repo bug returns a
                # record without tip_id, the outer try/except returns None
                # rather than rendering a published-confirmation pointing at
                # an empty string.
                return {
                    "type": "tip",
                    "status": "published",
                    "tool_call_id": tool_call_id,
                    "record_id": existing.tip_id,
                }
            dept = args.get("department", "Everyone")
            if not isinstance(dept, str) or dept.lower() in ("all", ""):
                dept = "Everyone"
            return {
                "type": "tip",
                "tool_call_id": tool_call_id,
                "title": args.get("title", "") or "",
                "content": args.get("content", "") or "",
                "tags": list(args.get("tags") or []),
                "department": dept,
            }

        if tool_name == "prepare_collab":
            if _collabs_repo is None:
                return None
            existing = await _collabs_repo.find_by_source(user_id, session_id, tool_call_id)
            if existing is not None:
                return {
                    "type": "collab",
                    "status": "published",
                    "tool_call_id": tool_call_id,
                    "record_id": existing.collab_id,
                }
            dept = args.get("department", "Everyone")
            if not isinstance(dept, str) or dept.lower() in ("all", ""):
                dept = "Everyone"
            return {
                "type": "collab",
                "tool_call_id": tool_call_id,
                "title": args.get("title", "") or "",
                "problem": args.get("problem", "") or "",
                "needed_skills": list(args.get("needed_skills") or []),
                "time_commitment": args.get("time_commitment", "") or "",
                "tags": list(args.get("tags") or []),
                "department": dept,
            }

        if tool_name == "prepare_idea":
            if _user_ideas_repo is None:
                return None
            # UserIdeaRepository is user-scoped already — list + filter in memory.
            ideas = await _user_ideas_repo.list(user_id)
            for idea in ideas:
                if (
                    getattr(idea, "source_session_id", "") == session_id
                    and getattr(idea, "source_tool_call_id", "") == tool_call_id
                ):
                    return {
                        "type": "idea",
                        "status": "published",
                        "tool_call_id": tool_call_id,
                        "record_id": idea.idea_id,
                    }
            return {
                "type": "idea",
                "tool_call_id": tool_call_id,
                "title": args.get("title", "") or "",
                "description": args.get("description", "") or "",
                "tags": list(args.get("tags") or []),
            }

        return None
    except Exception:
        logger.warning(
            "Failed to compute active preview user=%s session=%s",
            user_id, session_id, exc_info=True,
        )
        return None


@router.get("/{session_id}")
async def get_session(session_id: str, user: AuthUser):
    """Get session metadata and transcript."""
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = await load_transcript(_storage, user.user_id, session_id)
    result = session.model_dump(mode="json")
    result["transcript"] = [m.model_dump(mode="json") for m in transcript] if transcript else []

    # Compute the active (unpublished) preview, if any. Never 500 on failure.
    try:
        active_preview = await _compute_active_preview(user.user_id, session_id, transcript or [])
    except Exception:
        logger.warning(
            "active_preview computation raised for user=%s session=%s",
            user.user_id, session_id, exc_info=True,
        )
        active_preview = None
    result["active_preview"] = active_preview
    return result


@router.delete("/{session_id}")
async def delete_session(session_id: str, user: AuthUser):
    """Delete session metadata and transcript."""
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Intake sessions must be reset via /api/profile/reset-intake, not deleted directly
    if session.type == "intake":
        raise HTTPException(status_code=403, detail="Use the reset option to delete your intake session")

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
