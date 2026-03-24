"""Tips & Tricks endpoints.

Covers General Tips, Gemini Gems, and Claude Skills - all stored as Tip
records with a `category` field and an optional `artifact` for gem/skill
definitions.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import AuthUser
from backend.models import Tip as TipModel, TipComment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tips", tags=["tips"])

_tips_repo = None

HAIKU_MODEL = "bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0"
LANCE_SCOPE = "tips"
LANCE_COLLECTION = "tips"


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


async def _index_tip_to_lance(tip: TipModel) -> None:
    """Index a tip into LanceDB for similarity search."""
    from backend.lance.indexing import index_document
    from backend.lance.schemas import TIPS_SCHEMA

    # Combine title + description + artifact for searchable content
    parts = [tip.title, tip.content]
    if tip.artifact:
        parts.append(tip.artifact)
    content = "\n\n".join(parts)

    metadata = {
        "tip_id": tip.tip_id,
        "author_id": tip.author_id,
        "category": tip.category,
        "department": tip.department,
    }

    await index_document(
        collection=LANCE_COLLECTION,
        content=content,
        scope_path=LANCE_SCOPE,
        metadata=metadata,
        document_id=tip.tip_id,
        extra_fields={
            "tip_id": tip.tip_id,
            "category": tip.category,
            "title": tip.title,
        },
        schema=TIPS_SCHEMA,
    )


async def _delete_tip_from_lance(tip_id: str) -> None:
    """Remove a tip from the LanceDB index."""
    import asyncio
    from backend.lance.connection import get_lance_connection

    try:
        db = get_lance_connection(LANCE_SCOPE)
        existing = db.table_names()
        if LANCE_COLLECTION not in existing:
            return
        table = db.open_table(LANCE_COLLECTION)
        safe_id = tip_id.replace("\\", "\\\\").replace('"', '\\"')
        await asyncio.to_thread(table.delete, f'tip_id = "{safe_id}"')
    except Exception:
        logger.warning("Failed to delete tip %s from LanceDB", tip_id, exc_info=True)


_DUPLICATE_CHECK_PROMPT = """\
You are checking whether a new submission to a knowledge base is a duplicate of an existing one.

New submission:
Title: {new_title}
Description: {new_description}

Existing item:
Title: {existing_title}
Description: {existing_content}

Determine:
1. Is the new submission substantively the same as the existing item? (Not just topically related, but covering the same core insight, workflow, or technique.)
2. If they are similar but the new one adds something, what is the new/different information?

Return JSON only:
{{"is_duplicate": true/false, "confidence": 0.0-1.0, "explanation": "one sentence why", "new_info": "what the new submission adds (empty string if nothing new)"}}"""


TipCategoryType = Literal["tip", "gem", "skill"]


class CheckSimilarRequest(BaseModel):
    title: str = Field(max_length=200)
    content: str = Field(max_length=10000)
    artifact: str = Field("", max_length=50000)


@router.post("/check-similar")
async def check_similar(body: CheckSimilarRequest, user: AuthUser):
    """Check for similar existing tips before publishing.

    Uses LanceDB hybrid search to find candidates, then Haiku to judge
    whether they are true duplicates. Returns matches with explanations
    and suggested comments.
    """
    from backend.lance.search import search as lance_search

    query_text = f"{body.title} {body.content}"
    if body.artifact:
        query_text += f" {body.artifact[:500]}"

    # Search LanceDB for similar tips
    try:
        search_result = await lance_search(
            query=query_text,
            scope_path=LANCE_SCOPE,
            collection=LANCE_COLLECTION,
            limit=5,
            rerank=True,
            min_score=0.3,
        )
        candidates = search_result.get("results", [])
    except Exception:
        logger.warning("LanceDB similarity search failed", exc_info=True)
        return {"matches": []}

    if not candidates:
        return {"matches": []}

    # Get full tip data for top candidates
    candidate_tip_ids = []
    for c in candidates[:5]:
        meta = c.get("metadata", {})
        tid = meta.get("tip_id", "")
        if tid and tid not in candidate_tip_ids:
            candidate_tip_ids.append(tid)

    if not candidate_tip_ids:
        return {"matches": []}

    # Run Haiku duplicate check on each candidate
    from backend.llm import call_llm

    matches = []
    for tid in candidate_tip_ids[:3]:
        existing_tip = await _tips_repo.get(tid)
        if existing_tip is None:
            continue

        prompt = _DUPLICATE_CHECK_PROMPT.format(
            new_title=body.title,
            new_description=body.content[:2000],
            existing_title=existing_tip.title,
            existing_content=existing_tip.content[:2000],
        )

        try:
            resp = await call_llm(
                messages=[{"role": "user", "content": prompt}],
                model=HAIKU_MODEL,
                max_tokens=300,
            )
            text = (resp.content or "").strip()
            # Strip code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)
            if result.get("is_duplicate") and result.get("confidence", 0) >= 0.6:
                tip_data = existing_tip.model_dump(mode="json")
                matches.append({
                    "tip": tip_data,
                    "explanation": result.get("explanation", ""),
                    "suggested_comment": result.get("new_info", ""),
                    "confidence": result.get("confidence", 0),
                })
        except (json.JSONDecodeError, ValueError):
            logger.debug("Haiku duplicate check returned invalid JSON for tip %s", tid)
        except Exception:
            logger.warning("Haiku duplicate check failed for tip %s", tid, exc_info=True)

    return {"matches": matches}


class CreateTipRequest(BaseModel):
    title: str = Field(max_length=200)
    content: str = Field(max_length=10000)
    tags: list[str] = []
    department: str = "Everyone"
    category: TipCategoryType = "tip"
    artifact: str = Field("", max_length=50000)


@router.post("")
async def create_tip(body: CreateTipRequest, user: AuthUser):
    """Create and publish a tip/gem/skill from the frontend."""
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
        category=body.category,
        artifact=body.artifact,
    )
    await _tips_repo.create(tip)

    # Index into LanceDB for similarity search (fire-and-forget)
    try:
        await _index_tip_to_lance(tip)
    except Exception:
        logger.warning("Failed to index tip %s to LanceDB", tip.tip_id, exc_info=True)

    d = tip.model_dump(mode="json")
    d["user_has_voted"] = False
    return d


@router.get("")
async def list_tips(
    user: AuthUser,
    department: str | None = Query(None, description="Filter by department"),
    sort_by: str = Query("recent", description="Sort by: recent or popular"),
    category: TipCategoryType | None = Query(None, description="Filter by category: tip, gem, skill"),
    limit: int = Query(50, ge=1, le=200),
):
    """List tips, optionally filtered by department and/or category."""
    tips = await _tips_repo.list(department=department, sort_by=sort_by, limit=limit, category=category)
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
    category: TipCategoryType | None = None
    artifact: str | None = Field(None, max_length=50000)


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

    # Re-index in LanceDB if content changed
    if any(k in fields for k in ("title", "content", "artifact")):
        try:
            await _index_tip_to_lance(updated)
        except Exception:
            logger.warning("Failed to re-index tip %s to LanceDB", tip_id, exc_info=True)

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

    try:
        await _delete_tip_from_lance(tip_id)
    except Exception:
        logger.warning("Failed to delete tip %s from LanceDB", tip_id, exc_info=True)

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


class UpdateCommentRequest(BaseModel):
    content: str


@router.patch("/{tip_id}/comments/{comment_id}")
async def update_comment(
    tip_id: str,
    comment_id: str,
    body: UpdateCommentRequest,
    user: AuthUser,
):
    """Update a comment. Only the author can edit their own comment."""
    comments = await _tips_repo.list_comments(tip_id)
    existing = next((c for c in comments if c.comment_id == comment_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if existing.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")

    updated = await _tips_repo.update_comment(tip_id, comment_id, body.content)
    if updated is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return updated.model_dump(mode="json")


@router.delete("/{tip_id}/comments/{comment_id}")
async def delete_comment(
    tip_id: str,
    comment_id: str,
    user: AuthUser,
):
    """Delete a comment. Only the author can delete their own comment."""
    comments = await _tips_repo.list_comments(tip_id)
    existing = next((c for c in comments if c.comment_id == comment_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if existing.author_id != user.user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    await _tips_repo.delete_comment(tip_id, comment_id)
    return {"status": "deleted"}
