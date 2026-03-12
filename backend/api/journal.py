"""Journal endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])

_journal_repo = None


def set_journal_deps(journal_repo):
    global _journal_repo
    _journal_repo = journal_repo


@router.get("")
async def list_journal(
    user: AuthUser,
    date_from: str | None = Query(None, description="Start date (ISO 8601)"),
    date_to: str | None = Query(None, description="End date (ISO 8601)"),
    limit: int = Query(50, ge=1, le=200),
):
    """List journal entries for the current user."""
    dt_from: datetime | None = None
    dt_to: datetime | None = None

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        except ValueError:
            dt_from = None

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
        except ValueError:
            dt_to = None

    entries = await _journal_repo.list(
        user_id=user.user_id,
        date_from=dt_from,
        date_to=dt_to,
        limit=limit,
    )
    return [e.model_dump(mode="json") for e in entries]
