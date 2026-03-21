"""Profile endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.auth import AuthUser
from backend.models import UserProfile
from backend.orgchart import OrgChart, enrich_profile_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_profiles_repo = None
_orgchart: OrgChart | None = None


def set_profile_deps(profiles_repo, orgchart=None):
    global _profiles_repo, _orgchart
    _profiles_repo = profiles_repo
    _orgchart = orgchart


async def _get_or_create_profile(user: AuthUser) -> UserProfile:
    """Get profile, auto-creating from OIDC claims + org chart on first access."""
    profile = await _profiles_repo.get(user.user_id)
    if profile is not None:
        return profile

    logger.info("Creating profile for new user %s (%s)", user.user_id, user.email)

    kwargs: dict = dict(user_id=user.user_id, email=user.email, name=user.name)

    if _orgchart and user.email:
        try:
            enrichment = enrich_profile_kwargs(_orgchart, user.email)
            kwargs.update(enrichment)
        except Exception:
            logger.warning("Org chart lookup failed for %s", user.email, exc_info=True)

    profile = UserProfile(**kwargs)
    await _profiles_repo.create(profile)
    return profile


@router.get("")
async def get_profile(user: AuthUser):
    """Get the current user's profile, creating it on first access."""
    profile = await _get_or_create_profile(user)
    return profile.model_dump(mode="json")


@router.put("")
async def update_profile(body: dict, user: AuthUser):
    """Update profile fields (partial update)."""
    if not body:
        raise HTTPException(status_code=400, detail="No fields provided")

    await _get_or_create_profile(user)
    await _profiles_repo.update(user.user_id, body)
    updated = await _profiles_repo.get(user.user_id)
    return updated.model_dump(mode="json")
