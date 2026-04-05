"""Profile endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from backend.auth import AuthUser
from backend.models import UserProfile
from backend.orgchart import OrgChart, enrich_profile_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_profiles_repo = None
_sessions_repo = None
_storage = None
_orgchart: OrgChart | None = None
_user_ideas_repo = None


def set_profile_deps(profiles_repo, orgchart=None, sessions_repo=None, storage=None, user_ideas_repo=None):
    global _profiles_repo, _orgchart, _sessions_repo, _storage, _user_ideas_repo
    _profiles_repo = profiles_repo
    _orgchart = orgchart
    _sessions_repo = sessions_repo
    _storage = storage
    _user_ideas_repo = user_ideas_repo


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
async def get_profile(user: AuthUser, request: Request = None):
    """Get the current user's profile, creating it on first access.

    Includes computed `program_week` field (clock-based, or per-user override).
    Accepts X-Timezone header (IANA string) to compute week in user's local time.
    """
    from backend.models import effective_program_week
    profile = await _get_or_create_profile(user)

    # Store timezone from client if provided and changed
    tz = None
    if request:
        tz = request.headers.get("X-Timezone")
        if tz and tz != profile.timezone:
            await _profiles_repo.update(user.user_id, {"timezone": tz})
            profile.timezone = tz

    data = profile.model_dump(mode="json")
    data["program_week"] = effective_program_week(profile, timezone=tz or profile.timezone or None)
    return data


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
    """Reset intake state for the current week.

    Week 1: full reset (clear all profile fields, delete all intake sessions).
    Week 2+: only remove the current week from intake_weeks and delete
    the current week's intake session. Previous weeks' data is preserved.

    Available to any authenticated user (resets their own data only).
    Also used by the admin TopBar reset button.
    """
    profile = await _get_or_create_profile(user)
    from backend.models import effective_program_week
    current_week = effective_program_week(profile)
    current_week_str = str(current_week)

    if current_week > 1:
        # Week 2+: only reset the current week
        current_weeks = dict(profile.intake_weeks or {})
        current_weeks.pop(current_week_str, None)
        await _profiles_repo.update(user.user_id, {
            "intake_weeks": current_weeks,
        })

        # Delete only the current week's intake session
        if _sessions_repo:
            sessions = await _sessions_repo.list(user.user_id)
            for s in sessions:
                if s.type == "intake" and s.program_week == current_week:
                    if _storage:
                        key = f"sessions/{user.user_id}/{s.session_id}.json"
                        try:
                            await _storage.delete(key)
                        except Exception:
                            logger.warning("Failed to delete intake transcript %s", key)
                    await _sessions_repo.delete(user.user_id, s.session_id)
                    logger.info("Deleted intake session %s (Week %d) for user %s", s.session_id, current_week, user.user_id)

        # Remove plan-dayN and any Week N objective responses, keep everything else
        if _storage:
            from backend.storage import load_intake_responses, save_intake_responses
            from backend.repository.department_config import DepartmentConfigRepository
            responses = await load_intake_responses(_storage, user.user_id)
            plan_key = f"plan-day{current_week}"
            keys_to_remove = {plan_key}
            # Also remove objectives introduced in the current week
            dept_repo = DepartmentConfigRepository(_storage)
            company_config = await dept_repo.get_company_config()
            for obj in (company_config or {}).get("objectives", []):
                if obj.get("week_introduced", 1) == current_week and "id" in obj:
                    keys_to_remove.add(obj["id"])
            if profile.department:
                dept_slug = profile.department.lower().replace(" ", "-")
                dept_config = await dept_repo.get_department_config(dept_slug)
                for obj in (dept_config or {}).get("objectives", []):
                    if obj.get("week_introduced", 1) == current_week and "id" in obj:
                        keys_to_remove.add(obj["id"])
            removed = {k for k in keys_to_remove if k in responses}
            if removed:
                for k in removed:
                    del responses[k]
                await save_intake_responses(_storage, user.user_id, responses)

        logger.info("Reset Week %d intake for user %s (%s)", current_week, user.user_id, user.email)
        return {"status": "reset", "week": current_week}

    # Week 1: full reset (original behavior)
    await _profiles_repo.update(user.user_id, {
        "intake_completed_at": None,
        "onboarding_complete": False,
        "intake_skipped": False,
        "work_summary": "",
        "ai_experience_level": "",
        "interests": [],
        "tools_used": [],
        "goals": [],
        "products": [],
        "daily_tasks": "",
        "core_skills": [],
        "learning_goals": [],
        "ai_tools_used": [],
        "ai_superpower": "",
        "ai_proficiency": None,
        "intake_summary": "",
        "intake_fields_captured": [],
        "intake_objectives_done": 0,
        "intake_objectives_total": 0,
        "intake_weeks": {},
    })

    # Find and delete all intake sessions
    if _sessions_repo:
        sessions = await _sessions_repo.list(user.user_id)
        for s in sessions:
            if s.type == "intake":
                if _storage:
                    key = f"sessions/{user.user_id}/{s.session_id}.json"
                    try:
                        await _storage.delete(key)
                    except Exception:
                        logger.warning("Failed to delete intake transcript %s", key)
                if _storage:
                    responses_key = f"profiles/{user.user_id}/intake-responses.json"
                    try:
                        await _storage.delete(responses_key)
                    except Exception:
                        logger.warning("Failed to delete intake responses %s", responses_key)
                await _sessions_repo.delete(user.user_id, s.session_id)
                logger.info("Deleted intake session %s for user %s", s.session_id, user.user_id)

    # Delete ideas that were captured during intake
    deleted_ideas = 0
    if _user_ideas_repo:
        ideas = await _user_ideas_repo.list(user.user_id)
        for idea in ideas:
            if idea.source == "intake":
                await _user_ideas_repo.delete(user.user_id, idea.idea_id)
                deleted_ideas += 1
        if deleted_ideas:
            logger.info("Deleted %d intake ideas for user %s", deleted_ideas, user.user_id)

    logger.info("Reset intake for user %s (%s)", user.user_id, user.email)
    return {"status": "reset"}


@router.post("/reevaluate-intake")
async def reevaluate_intake(user: AuthUser):
    """Re-run objective evaluation against the existing intake transcript.

    Called on page reload when a user has an incomplete intake with messages.
    Uses the current department config and evaluation logic to retroactively
    detect objectives that were already covered.

    Returns:
        completed: bool - whether intake is now complete
        newly_completed: int - number of objectives newly detected
    """
    profile = await _profiles_repo.get(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    from backend.models import effective_program_week
    current_week_str = str(effective_program_week(profile))
    if current_week_str in (profile.intake_weeks or {}):
        return {"completed": True, "newly_completed": 0}

    # Find the intake session
    if not _sessions_repo or not _storage:
        raise HTTPException(status_code=500, detail="Dependencies not configured")

    from backend.models import effective_program_week
    week = effective_program_week(profile)
    sessions = await _sessions_repo.list(user.user_id)
    # Find the current week's intake session
    intake_session = next((s for s in sessions if s.type == "intake" and s.program_week == week), None)
    if not intake_session:
        return {"completed": False, "newly_completed": 0}

    # Load transcript
    from backend.storage import load_transcript, load_intake_responses, save_intake_responses
    transcript = await load_transcript(_storage, user.user_id, intake_session.session_id)
    if not transcript or len(transcript) < 5:
        return {"completed": False, "newly_completed": 0}

    # Load merged objectives (company + department)
    from backend.repository.department_config import DepartmentConfigRepository
    from backend.models import effective_program_week
    dept_config_repo = DepartmentConfigRepository(_storage)
    week = effective_program_week(profile)
    merged_objectives: list[dict] = []
    if profile.department:
        dept_slug = profile.department.lower().replace(" ", "-")
        merged_objectives = await dept_config_repo.get_merged_objectives(dept_slug, program_week=week)
    else:
        # No department — still load company-wide objectives
        company_config = await dept_config_repo.get_company_config()
        all_co = (company_config or {}).get("objectives", [])
        merged_objectives = [o for o in all_co if o.get("week_introduced", 1) <= week and week <= o.get("week_max", 99)]

    if not merged_objectives:
        return {"completed": False, "newly_completed": 0}

    # Inject the synthetic plan-dayN objective for Week 2+, matching executor.py
    if week > 1:
        from backend.models import make_plan_objective
        merged_objectives = list(merged_objectives) + [make_plan_objective(week)]

    # Convert transcript to LLM messages
    from backend.agent.executor import _transcript_to_llm_messages
    llm_messages = _transcript_to_llm_messages(transcript)

    # Load current responses and evaluate
    intake_responses = await load_intake_responses(_storage, user.user_id)

    # Clear stale responses for recurring objectives (same logic as executor.py)
    if week > 1:
        from backend.models import PROGRAM_START_DATE
        from datetime import timedelta
        week_start = PROGRAM_START_DATE + timedelta(weeks=week - 1)
        recurring_ids = {o["id"] for o in merged_objectives if o.get("recurring")}
        for obj_id in recurring_ids:
            resp = intake_responses.get(obj_id)
            if resp and isinstance(resp, dict) and resp.get("captured_at"):
                captured = resp["captured_at"][:10]
                if captured < week_start.isoformat():
                    del intake_responses[obj_id]

    from backend.agent.extraction import evaluate_objectives
    newly_completed = await evaluate_objectives(llm_messages, merged_objectives, intake_responses)

    if newly_completed:
        intake_responses.update(newly_completed)
        await save_intake_responses(_storage, user.user_id, intake_responses)
        logger.info(
            "Reevaluation completed %d objectives for user=%s",
            len(newly_completed), user.user_id,
        )

    # Update progress counts on profile for dashboard.
    # Never mark intake as complete here - that's the executor's job via
    # _check_intake_completion, which runs after the AI responds. The reevaluate
    # endpoint only backfills objective detection for the progress UI.
    objective_ids = {obj["id"] for obj in merged_objectives if "id" in obj}
    completed_ids = set(intake_responses.keys())
    all_complete = objective_ids.issubset(completed_ids)

    await _profiles_repo.update(user.user_id, {
        "intake_objectives_done": len(completed_ids & objective_ids),
        "intake_objectives_total": len(objective_ids),
    })

    return {"completed": all_complete, "newly_completed": len(newly_completed)}


@router.post("/skip-intake")
async def skip_intake(user: AuthUser):
    """Skip remaining intake objectives and mark intake as complete.

    Escape valve for users who've had a substantial conversation but
    haven't triggered all objective completions.
    """
    profile = await _profiles_repo.get(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    from backend.models import effective_program_week
    week_str = str(effective_program_week(profile))

    # Check if this week's intake is already done (not just any past week)
    if week_str in (profile.intake_weeks or {}):
        return {"status": "already_complete"}

    now_iso = datetime.now(UTC).isoformat()
    current_weeks = dict(profile.intake_weeks or {})
    current_weeks[week_str] = now_iso
    await _profiles_repo.update(user.user_id, {
        "intake_completed_at": now_iso,
        "onboarding_complete": True,
        "intake_skipped": True,
        "intake_weeks": current_weeks,
    })
    logger.info("Intake skipped for user=%s (%s)", user.user_id, user.email)
    return {"status": "skipped"}
