"""Tips & Tricks endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import AuthUser
from backend.models import TipComment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tips", tags=["tips"])

_tips_repo = None

HAIKU_MODEL = "bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0"


def set_tips_deps(tips_repo):
    global _tips_repo
    _tips_repo = tips_repo


async def _generate_summary(title: str, content: str) -> str:
    """Generate a 2-3 sentence plain-text summary using Haiku."""
    try:
        from backend.llm import call_llm
        resp = await call_llm(
            messages=[
                {
                    "role": "system",
                    "content": "You write ultra-short summaries. One sentence, under 20 words. No exceptions.",
                },
                {
                    "role": "user",
                    "content": f"Summarize in ONE short sentence:\n\n{title}\n\n{content}",
                }
            ],
            model=HAIKU_MODEL,
            max_tokens=40,
        )
        return (resp.content or "").strip()
    except Exception:
        logger.warning("Failed to generate tip summary", exc_info=True)
        return ""


class CreateTipRequest(BaseModel):
    title: str = Field(max_length=200)
    content: str = Field(max_length=10000)
    tags: list[str] = []
    department: str = "Everyone"


@router.post("")
async def create_tip(body: CreateTipRequest, user: AuthUser):
    """Create and publish a tip from the frontend preview card."""
    from backend.models import Tip

    summary = await _generate_summary(body.title, body.content)
    tip = Tip(
        tip_id=str(uuid.uuid4()),
        author_id=user.user_id,
        department=body.department,
        title=body.title,
        content=body.content,
        summary=summary,
        tags=body.tags,
    )
    await _tips_repo.create(tip)
    d = tip.model_dump(mode="json")
    d["user_has_voted"] = False
    return d


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


class UpdateTipRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    content: str | None = Field(None, max_length=10000)
    tags: list[str] | None = None
    department: str | None = None


@router.patch("/{tip_id}")
async def update_tip(
    tip_id: str,
    body: UpdateTipRequest,
    user: AuthUser,
):
    """Update a tip. Only the author can edit their own tip."""
    tip = await _tips_repo.get(tip_id)
    if tip is None:
        raise HTTPException(status_code=404, detail="Tip not found")
    if tip.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own tips")

    fields = body.model_dump(exclude_none=True)
    if not fields:
        d = tip.model_dump(mode="json")
        d["user_has_voted"] = False
        return d

    # Regenerate summary if title or content changed
    if "title" in fields or "content" in fields:
        new_title = fields.get("title", tip.title)
        new_content = fields.get("content", tip.content)
        fields["summary"] = await _generate_summary(new_title, new_content)

    updated = await _tips_repo.update(tip_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Tip not found")

    user_votes = await _tips_repo.get_user_votes(user.user_id, [tip_id])
    d = updated.model_dump(mode="json")
    d["user_has_voted"] = tip_id in user_votes
    return d


@router.delete("/{tip_id}")
async def delete_tip(
    tip_id: str,
    user: AuthUser,
):
    """Delete a tip. Only the author can delete their own tip."""
    tip = await _tips_repo.get(tip_id)
    if tip is None:
        raise HTTPException(status_code=404, detail="Tip not found")
    if tip.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own tips")

    await _tips_repo.delete(tip_id)
    return {"status": "deleted"}


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
    comment = TipComment(
        tip_id=tip_id,
        comment_id=str(uuid.uuid4()),
        author_id=user.user_id,
        content=body.content,
    )
    await _tips_repo.add_comment(comment)
    return comment.model_dump(mode="json")
