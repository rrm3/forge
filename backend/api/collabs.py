"""Collaboration Board endpoints.

Covers creating collaboration proposals, expressing interest, commenting,
and managing collab status through open -> building -> done lifecycle.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.analytics import track as posthog_track
from backend.auth import AuthUser
from backend.models import Collaboration, CollabComment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collabs", tags=["collabs"])

_collabs_repo = None


def set_collabs_deps(collabs_repo):
    global _collabs_repo
    _collabs_repo = collabs_repo


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateCollabRequest(BaseModel):
    title: str = Field(max_length=200)
    problem: str = Field(max_length=10000)
    needed_skills: list[str] = []
    time_commitment: str = ""
    tags: list[str] = []
    department: str = ""


class UpdateCollabRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    problem: str | None = Field(None, max_length=10000)
    needed_skills: list[str] | None = None
    time_commitment: str | None = None
    tags: list[str] | None = None


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(open|building|done)$")


class ExpressInterestRequest(BaseModel):
    message: str = ""


class AddCommentRequest(BaseModel):
    content: str = Field(max_length=10000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("")
async def create_collab(body: CreateCollabRequest, user: AuthUser):
    """Create a new collaboration proposal."""
    collab = Collaboration(
        collab_id=str(uuid.uuid4()),
        author_id=user.user_id,
        department=body.department,
        title=body.title,
        problem=body.problem,
        needed_skills=body.needed_skills,
        time_commitment=body.time_commitment,
        tags=body.tags,
    )
    await _collabs_repo.create(collab)
    posthog_track(user.user_id, "collab_created", {
        "collab_id": collab.collab_id,
        "department": collab.department,
        "tags": collab.tags,
    })

    d = collab.model_dump(mode="json")
    d["user_has_interest"] = False
    return d


@router.get("")
async def list_collabs(
    user: AuthUser,
    status: str | None = Query(None, description="Filter by status"),
    department: str | None = Query(None, description="Filter by department"),
    limit: int = Query(50, ge=1, le=200),
):
    """List collaborations, optionally filtered by status and/or department.
    Archived collabs are always excluded."""
    collabs = await _collabs_repo.list(status=status, department=department, limit=limit)
    collab_ids = [c.collab_id for c in collabs]

    user_interests = await _collabs_repo.get_user_interests(user.user_id, collab_ids)

    result = []
    for c in collabs:
        d = c.model_dump(mode="json")
        d["user_has_interest"] = c.collab_id in user_interests
        result.append(d)
    return result


@router.get("/{collab_id}")
async def get_collab(
    collab_id: str,
    user: AuthUser,
):
    """Get a single collaboration by ID."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    user_interests = await _collabs_repo.get_user_interests(user.user_id, [collab_id])
    interested_user_ids = await _collabs_repo.get_interested_user_ids(collab_id)

    d = collab.model_dump(mode="json")
    d["user_has_interest"] = collab_id in user_interests
    d["interested_count"] = len(interested_user_ids)
    d["interested_user_ids"] = interested_user_ids
    return d


@router.put("/{collab_id}")
async def update_collab(
    collab_id: str,
    body: UpdateCollabRequest,
    user: AuthUser,
):
    """Update a collaboration. Only the author can edit."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    if collab.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own collaborations")

    fields = body.model_dump(exclude_none=True)
    if not fields:
        d = collab.model_dump(mode="json")
        d["user_has_interest"] = False
        return d

    updated = await _collabs_repo.update(collab_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    user_interests = await _collabs_repo.get_user_interests(user.user_id, [collab_id])
    d = updated.model_dump(mode="json")
    d["user_has_interest"] = collab_id in user_interests
    return d


@router.delete("/{collab_id}")
async def delete_collab(
    collab_id: str,
    user: AuthUser,
):
    """Archive a collaboration. Only the author can archive."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    if collab.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only archive your own collaborations")

    await _collabs_repo.delete(collab_id)
    return {"status": "archived"}


@router.post("/{collab_id}/interest")
async def express_interest(
    collab_id: str,
    body: ExpressInterestRequest,
    user: AuthUser,
):
    """Express interest in a collaboration."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    is_new = await _collabs_repo.express_interest(collab_id, user.user_id, body.message)
    if is_new:
        posthog_track(user.user_id, "collab_interest_expressed", {"collab_id": collab_id})
        return {"status": "interested"}
    return {"status": "already_interested"}


@router.delete("/{collab_id}/interest")
async def withdraw_interest(
    collab_id: str,
    user: AuthUser,
):
    """Withdraw interest from a collaboration."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    await _collabs_repo.withdraw_interest(collab_id, user.user_id)
    return {"status": "withdrawn"}


VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"building"},
    "building": {"done", "open"},
    "done": {"building"},
}


@router.put("/{collab_id}/status")
async def update_status(
    collab_id: str,
    body: UpdateStatusRequest,
    user: AuthUser,
):
    """Update a collaboration's status. Author or anyone who expressed interest can change status."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    is_author = collab.author_id == user.user_id
    user_interests = await _collabs_repo.get_user_interests(user.user_id, [collab_id])
    is_interested = collab_id in user_interests
    if not is_author and not is_interested:
        raise HTTPException(status_code=403, detail="Only the author or interested collaborators can change status")

    allowed = VALID_TRANSITIONS.get(collab.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{collab.status}' to '{body.status}'",
        )

    updated = await _collabs_repo.update(collab_id, {"status": body.status})
    if updated is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    d = updated.model_dump(mode="json")
    d["user_has_interest"] = is_interested
    return d


@router.get("/{collab_id}/comments")
async def list_comments(
    collab_id: str,
    user: AuthUser,
):
    """List comments for a collaboration."""
    comments = await _collabs_repo.list_comments(collab_id)
    return [c.model_dump(mode="json") for c in comments]


@router.post("/{collab_id}/comments")
async def add_comment(
    collab_id: str,
    body: AddCommentRequest,
    user: AuthUser,
):
    """Add a comment to a collaboration."""
    collab = await _collabs_repo.get(collab_id)
    if collab is None:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    comment = CollabComment(
        collab_id=collab_id,
        comment_id=str(uuid.uuid4()),
        author_id=user.user_id,
        content=body.content,
    )
    await _collabs_repo.add_comment(comment)
    posthog_track(user.user_id, "collab_comment_added", {"collab_id": collab_id})
    return comment.model_dump(mode="json")


@router.delete("/{collab_id}/comments/{comment_id}")
async def delete_comment(
    collab_id: str,
    comment_id: str,
    user: AuthUser,
):
    """Delete a comment. Only the comment author can delete."""
    comments = await _collabs_repo.list_comments(collab_id)
    existing = next((c for c in comments if c.comment_id == comment_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if existing.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    await _collabs_repo.delete_comment(collab_id, comment_id)
    return {"status": "deleted"}
