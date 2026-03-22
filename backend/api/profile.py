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
_sessions_repo = None
_storage = None
_orgchart: OrgChart | None = None


def set_profile_deps(profiles_repo, orgchart=None, sessions_repo=None, storage=None):
    global _profiles_repo, _orgchart, _sessions_repo, _storage
    _profiles_repo = profiles_repo
    _orgchart = orgchart
    _sessions_repo = sessions_repo
    _storage = storage


async def _get_or_create_profile(user: AuthUser) -> UserProfile:
    """Get profile, auto-creating from OIDC claims + org chart on first access."""
    profile = await _profiles_repo.get(user.user_id)
    if profile is not None:
        # Sync org chart fields on access, but only write if something actually changed
        if _orgchart and user.email:
            try:
                enrichment = enrich_profile_kwargs(_orgchart, user.email)
                if enrichment:
                    current = profile.model_dump()
                    changed = {k: v for k, v in enrichment.items() if current.get(k) != v}
                    if changed:
                        await _profiles_repo.update(user.user_id, changed)
                        profile = await _profiles_repo.get(user.user_id) or profile
            except Exception:
                logger.warning("Org chart sync failed for %s", user.email, exc_info=True)
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


PUBLIC_FIELDS = {"user_id", "name", "title", "department", "avatar_url", "team"}


@router.get("/{user_id}")
async def get_public_profile(user_id: str, _user: AuthUser):
    """Get another user's public profile fields. Requires authentication."""
    profile = await _profiles_repo.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = profile.model_dump(mode="json")
    return {k: v for k, v in data.items() if k in PUBLIC_FIELDS}


@router.put("")
async def update_profile(body: dict, user: AuthUser):
    """Update profile fields (partial update)."""
    if not body:
        raise HTTPException(status_code=400, detail="No fields provided")

    await _get_or_create_profile(user)
    await _profiles_repo.update(user.user_id, body)
    updated = await _profiles_repo.get(user.user_id)
    return updated.model_dump(mode="json")


@router.post("/reset-intake")
async def reset_intake(user: AuthUser):
    """Reset intake state: clear profile intake fields, delete intake session + transcript.

    Requires admin mode (enforced by checking admin access).
    """
    from backend.api.admin import _get_admin_departments

    departments = await _get_admin_departments(user.email)
    if departments is None:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Clear intake-related profile fields
    await _profiles_repo.update(user.user_id, {
        "intake_completed_at": None,
        "onboarding_complete": False,
        "products": [],
        "daily_tasks": "",
        "core_skills": [],
        "learning_goals": [],
        "ai_tools_used": [],
        "ai_superpower": "",
        "ai_proficiency": None,
        "intake_summary": "",
        "intake_fields_captured": [],
    })

    # Find and delete intake sessions
    if _sessions_repo:
        sessions = await _sessions_repo.list(user.user_id)
        for s in sessions:
            if s.type == "intake":
                # Delete transcript
                if _storage:
                    key = f"sessions/{user.user_id}/{s.session_id}.json"
                    try:
                        await _storage.delete(key)
                    except Exception:
                        logger.warning("Failed to delete intake transcript %s", key)
                # Delete intake responses
                if _storage:
                    responses_key = f"profiles/{user.user_id}/intake-responses.json"
                    try:
                        await _storage.delete(responses_key)
                    except Exception:
                        pass
                # Delete session metadata
                await _sessions_repo.delete(user.user_id, s.session_id)
                logger.info("Deleted intake session %s for user %s", s.session_id, user.user_id)

    logger.info("Reset intake for user %s (%s)", user.user_id, user.email)
    return {"status": "reset"}
