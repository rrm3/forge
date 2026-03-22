"""Tips & Tricks endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.auth import AuthUser
from backend.models import TipComment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tips", tags=["tips"])

_tips_repo = None


def set_tips_deps(tips_repo):
    global _tips_repo
    _tips_repo = tips_repo


@router.get("")
async def list_tips(
    user: AuthUser,
    department: str | None = Query(None, description="Filter by department"),
    sort_by: str = Query("recent", description="Sort by: recent or popular"),
    limit: int = Query(50, ge=1, le=200),
):
    """List tips, optionally filtered by department."""
    tips = await _tips_repo.list(department=department, sort_by=sort_by, limit=limit)
    tip_ids = [t.tip_id for t in tips]
    user_votes = await _tips_repo.get_user_votes(user.user_id, tip_ids)

    result = []
    for t in tips:
        d = t.model_dump(mode="json")
        d["user_has_voted"] = t.tip_id in user_votes
        result.append(d)
    return result


@router.get("/{tip_id}")
async def get_tip(
    tip_id: str,
    user: AuthUser,
):
    """Get a single tip by ID."""
    tip = await _tips_repo.get(tip_id)
    if tip is None:
        raise HTTPException(status_code=404, detail="Tip not found")

    user_votes = await _tips_repo.get_user_votes(user.user_id, [tip_id])
    d = tip.model_dump(mode="json")
    d["user_has_voted"] = tip_id in user_votes
    return d


@router.post("/{tip_id}/vote")
async def vote_tip(
    tip_id: str,
    user: AuthUser,
):
    """Upvote a tip."""
    is_new = await _tips_repo.upvote(tip_id, user.user_id)
    if is_new:
        return {"status": "voted"}
    return {"status": "already_voted"}


@router.delete("/{tip_id}/vote")
async def remove_vote(
    tip_id: str,
    user: AuthUser,
):
    """Remove a vote from a tip."""
    await _tips_repo.remove_vote(tip_id, user.user_id)
    return {"status": "removed"}


@router.get("/{tip_id}/comments")
async def list_comments(
    tip_id: str,
    user: AuthUser,
):
    """List comments for a tip."""
    comments = await _tips_repo.list_comments(tip_id)
    return [c.model_dump(mode="json") for c in comments]


class AddCommentRequest(BaseModel):
    content: str


@router.post("/{tip_id}/comments")
async def add_comment(
    tip_id: str,
    body: AddCommentRequest,
    user: AuthUser,
):
    """Add a comment to a tip."""
    # Get user name from profile if possible
    comment = TipComment(
        tip_id=tip_id,
        comment_id=str(uuid.uuid4()),
        author_id=user.user_id,
        author_name=user.name,
        content=body.content,
    )
    await _tips_repo.add_comment(comment)
    return comment.model_dump(mode="json")
