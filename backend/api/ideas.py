"""Ideas endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ideas", tags=["ideas"])

_ideas_repo = None


def set_ideas_deps(ideas_repo):
    global _ideas_repo
    _ideas_repo = ideas_repo


@router.get("")
async def list_ideas(
    user: AuthUser,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
):
    """List ideas, optionally filtered by status."""
    ideas = await _ideas_repo.list(status_filter=status, limit=limit)
    return [i.model_dump(mode="json") for i in ideas]
