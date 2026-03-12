"""Profile endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_profiles_repo = None


def set_profile_deps(profiles_repo):
    global _profiles_repo
    _profiles_repo = profiles_repo


@router.get("")
async def get_profile(user: AuthUser):
    """Get the current user's profile."""
    profile = await _profiles_repo.get(user.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.model_dump(mode="json")


@router.put("")
async def update_profile(body: dict, user: AuthUser):
    """Update profile fields (partial update)."""
    if not body:
        raise HTTPException(status_code=400, detail="No fields provided")

    profile = await _profiles_repo.get(user.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    await _profiles_repo.update(user.user_id, body)
    updated = await _profiles_repo.get(user.user_id)
    return updated.model_dump(mode="json")
