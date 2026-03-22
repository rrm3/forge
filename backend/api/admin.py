"""Admin panel endpoints - department config management and user dashboard."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_dept_config_repo = None
_profiles_repo = None
_sessions_repo = None
_tips_repo = None
_storage = None


def set_admin_deps(dept_config_repo, profiles_repo=None, sessions_repo=None, tips_repo=None, storage=None):
    global _dept_config_repo, _profiles_repo, _sessions_repo, _tips_repo, _storage
    _dept_config_repo = dept_config_repo
    _profiles_repo = profiles_repo
    _sessions_repo = sessions_repo
    _tips_repo = tips_repo
    _storage = storage


async def _get_admin_departments(email: str) -> list[str] | None:
    """Return the list of departments this user can manage, or None if not an admin.

    A value of ``["*"]`` in admin-access.json means all departments.
    """
    access = await _dept_config_repo.get_admin_access()
    departments = access.get(email)
    if departments is None:
        return None
    if "*" in departments:
        return await _dept_config_repo.list_departments()
    return departments


async def _require_admin(email: str, department: str | None = None) -> list[str]:
    """Assert the user is a full admin, optionally for a specific department.

    Returns the resolved list of manageable department slugs.
    Raises 403 if the user is not authorized.
    """
    departments = await _get_admin_departments(email)
    if departments is None:
        raise HTTPException(status_code=403, detail="Not an admin")
    if department is not None and department not in departments:
        raise HTTPException(status_code=403, detail="Not authorized for this department")
    return departments


async def _require_any_admin(user: AuthUser, department: str | None = None) -> list[str]:
    """Assert the user is either a full admin or a department admin.

    Department admins can only manage their own department.
    Returns the resolved list of manageable department slugs.
    """
    # Check full admin first
    departments = await _get_admin_departments(user.email)
    if departments is not None:
        if department is not None and department not in departments:
            raise HTTPException(status_code=403, detail="Not authorized for this department")
        return departments

    # Check department admin via profile
    if _profiles_repo:
        profile = await _profiles_repo.get(user.user_id)
        if profile and profile.is_department_admin and profile.department:
            dept_list = [profile.department]
            if department is not None and department not in dept_list:
                raise HTTPException(status_code=403, detail="Not authorized for this department")
            return dept_list

    raise HTTPException(status_code=403, detail="Not an admin")


@router.get("/access")
async def check_access(user: AuthUser):
    """Check if the current user is an admin and which departments they can manage.

    Returns three access levels:
    - is_admin: full admin (from admin-access.json) - sees everything
    - is_department_admin: department admin (from profile flag) - sees department settings only
    - departments: list of departments the user can manage
    """
    logger.warning("Admin access check: email='%s' user_id='%s'", user.email, user.user_id)
    departments = await _get_admin_departments(user.email)
    if departments is not None:
        return {"is_admin": True, "is_department_admin": False, "departments": departments}

    # Check if user is a department admin via profile flag
    if _profiles_repo:
        profile = await _profiles_repo.get(user.user_id)
        if profile and profile.is_department_admin and profile.department:
            return {"is_admin": False, "is_department_admin": True, "departments": [profile.department]}

    return {"is_admin": False, "is_department_admin": False, "departments": []}


@router.get("/departments")
async def list_departments(user: AuthUser):
    """List all departments the user can manage."""
    departments = await _require_any_admin(user)
    return departments


@router.get("/departments/{department}")
async def get_department_config(department: str, user: AuthUser):
    """Get a department's config (prompt + objectives)."""
    await _require_any_admin(user, department)
    config = await _dept_config_repo.get_department_config(department)
    if config is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return config


@router.put("/departments/{department}")
async def update_department_config(department: str, config: dict, user: AuthUser):
    """Update a department's config."""
    await _require_any_admin(user, department)
    await _dept_config_repo.save_department_config(department, config)
    return {"status": "updated"}


@router.get("/users")
async def list_users(user: AuthUser):
    """List all users with session/tip stats. Admin only."""
    departments = await _require_admin(user.email)

    profiles = await _profiles_repo.list_all()

    # Filter to departments the admin can manage
    dept_set = {d.lower() for d in departments}
    profiles = [p for p in profiles if p.department.lower() in dept_set or not p.department]

    user_ids = [p.user_id for p in profiles]

    # Load admin access map to flag full admins in the response
    admin_access = await _dept_config_repo.get_admin_access()
    admin_emails = {e.lower() for e in admin_access}

    # Compute tip counts in one scan
    tip_counts = await _tips_repo.count_by_authors(user_ids) if _tips_repo else {}

    # Compute session counts and last_active in parallel
    sem = asyncio.Semaphore(50)

    async def _count(uid: str) -> tuple[str, int]:
        async with sem:
            return uid, await _sessions_repo.count_by_user(uid)

    async def _last(uid: str) -> tuple[str, str | None]:
        async with sem:
            return uid, await _sessions_repo.last_active(uid)

    count_results = await asyncio.gather(*[_count(uid) for uid in user_ids])
    last_results = await asyncio.gather(*[_last(uid) for uid in user_ids])

    session_counts = dict(count_results)
    last_actives = dict(last_results)

    result = []
    for p in profiles:
        result.append({
            "user_id": p.user_id,
            "email": p.email,
            "name": p.name,
            "title": p.title,
            "department": p.department,
            "team": p.team,
            "avatar_url": p.avatar_url,
            "intake_completed_at": p.intake_completed_at.isoformat() if p.intake_completed_at else None,
            "ai_proficiency": p.ai_proficiency.model_dump() if p.ai_proficiency else None,
            "is_department_admin": p.is_department_admin,
            "is_admin": p.email.lower() in admin_emails,
            "session_count": session_counts.get(p.user_id, 0),
            "tip_count": tip_counts.get(p.user_id, 0),
            "last_active": last_actives.get(p.user_id),
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        })

    return result


@router.put("/users/{user_id}/role")
async def set_user_role(user_id: str, body: dict, user: AuthUser):
    """Toggle department admin role for a user. Full admin only."""
    await _require_admin(user.email)

    is_dept_admin = bool(body.get("is_department_admin", False))
    await _profiles_repo.update(user_id, {"is_department_admin": is_dept_admin})
    return {"status": "updated", "is_department_admin": is_dept_admin}


@router.put("/users/{user_id}/admin")
async def set_user_admin(user_id: str, body: dict, user: AuthUser):
    """Grant or revoke full admin access for a user. Full admin only."""
    await _require_admin(user.email)

    is_admin = bool(body.get("is_admin", False))

    # Look up the target user's email from their profile
    profile = await _profiles_repo.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")

    target_email = profile.email
    admin_access = await _dept_config_repo.get_admin_access()

    if is_admin:
        # Grant full admin with wildcard access
        admin_access[target_email] = ["*"]
    else:
        # Prevent removing yourself as admin
        if target_email.lower() == user.email.lower():
            raise HTTPException(status_code=400, detail="Cannot remove your own admin access")
        admin_access.pop(target_email, None)

    await _dept_config_repo.save_admin_access(admin_access)
    return {"status": "updated", "is_admin": is_admin}


@router.get("/users/{user_id}/intake")
async def get_user_intake(user_id: str, user: AuthUser):
    """Get a user's full profile and intake responses. Admin only."""
    await _require_admin(user.email)

    profile = await _profiles_repo.get(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")

    from backend.storage import load_intake_responses
    intake_responses = await load_intake_responses(_storage, user_id) if _storage else {}

    # Resolve objective UUIDs to human-readable labels
    if intake_responses and profile.department:
        from backend.repository.department_config import DepartmentConfigRepository
        dept_repo = DepartmentConfigRepository(_storage)
        dept_config = await dept_repo.get_department_config(
            profile.department.lower().replace(" ", "-")
        )
        if dept_config:
            label_map = {o["id"]: o["label"] for o in dept_config.get("objectives", [])}
            intake_responses = {
                label_map.get(k, k): v
                for k, v in intake_responses.items()
            }

    return {
        "profile": profile.model_dump(mode="json"),
        "intake_responses": intake_responses,
    }
