"""User Ideas endpoints - personal "Ideas to Explore" list."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.auth import AuthUser
from backend.models import UserIdea

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-ideas", tags=["user-ideas"])

_user_ideas_repo = None


def set_user_ideas_deps(user_ideas_repo):
    global _user_ideas_repo
    _user_ideas_repo = user_ideas_repo


class CreateUserIdeaRequest(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(max_length=10000)
    tags: list[str] = []
    source: str = "manual"
    source_session_id: str = ""


class UpdateUserIdeaRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=10000)
    tags: list[str] | None = None
    status: str | None = None


class LinkSessionRequest(BaseModel):
    session_id: str


@router.get("")
async def list_user_ideas(user: AuthUser):
    """List the user's ideas, sorted by updated_at desc."""
    ideas = await _user_ideas_repo.list(user.user_id)
    return [idea.model_dump(mode="json") for idea in ideas]


@router.post("")
async def create_user_idea(body: CreateUserIdeaRequest, user: AuthUser):
    """Create a new idea."""
    idea = UserIdea(
        user_id=user.user_id,
        idea_id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        tags=body.tags,
        source=body.source,
        source_session_id=body.source_session_id,
    )
    await _user_ideas_repo.create(idea)
    return idea.model_dump(mode="json")


@router.get("/{idea_id}")
async def get_user_idea(idea_id: str, user: AuthUser):
    """Get a single idea by ID."""
    idea = await _user_ideas_repo.get(user.user_id, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea.model_dump(mode="json")


@router.put("/{idea_id}")
async def update_user_idea(idea_id: str, body: UpdateUserIdeaRequest, user: AuthUser):
    """Update an idea (partial update)."""
    idea = await _user_ideas_repo.get(user.user_id, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")

    fields = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.description is not None:
        fields["description"] = body.description
    if body.tags is not None:
        fields["tags"] = body.tags
    if body.status is not None:
        if body.status not in ("new", "exploring", "done"):
            raise HTTPException(status_code=400, detail="Invalid status. Must be: new, exploring, or done")
        fields["status"] = body.status

    if fields:
        fields["updated_at"] = datetime.now(UTC).isoformat()
        await _user_ideas_repo.update(user.user_id, idea_id, fields)

    updated = await _user_ideas_repo.get(user.user_id, idea_id)
    return updated.model_dump(mode="json")


@router.delete("/{idea_id}")
async def delete_user_idea(idea_id: str, user: AuthUser):
    """Delete an idea."""
    idea = await _user_ideas_repo.get(user.user_id, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    await _user_ideas_repo.delete(user.user_id, idea_id)
    return {"status": "deleted"}


@router.post("/{idea_id}/link-session")
async def link_session(idea_id: str, body: LinkSessionRequest, user: AuthUser):
    """Link a session to an idea."""
    idea = await _user_ideas_repo.get(user.user_id, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    await _user_ideas_repo.link_session(user.user_id, idea_id, body.session_id)
    updated = await _user_ideas_repo.get(user.user_id, idea_id)
    return updated.model_dump(mode="json")
