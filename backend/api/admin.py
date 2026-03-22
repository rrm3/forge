"""Admin panel endpoints - department config management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_dept_config_repo = None


def set_admin_deps(dept_config_repo):
    global _dept_config_repo
    _dept_config_repo = dept_config_repo


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
    """Assert the user is an admin, optionally for a specific department.

    Returns the resolved list of manageable department slugs.
    Raises 403 if the user is not authorized.
    """
    departments = await _get_admin_departments(email)
    if departments is None:
        raise HTTPException(status_code=403, detail="Not an admin")
    if department is not None and department not in departments:
        raise HTTPException(status_code=403, detail="Not authorized for this department")
    return departments


@router.get("/access")
async def check_access(user: AuthUser):
    """Check if the current user is an admin and which departments they can manage."""
    logger.warning("Admin access check: email='%s' user_id='%s'", user.email, user.user_id)
    departments = await _get_admin_departments(user.email)
    if departments is None:
        return {"is_admin": False, "departments": []}
    return {"is_admin": True, "departments": departments}


@router.get("/departments")
async def list_departments(user: AuthUser):
    """List all departments the user can manage."""
    departments = await _require_admin(user.email)
    return departments


@router.get("/departments/{department}")
async def get_department_config(department: str, user: AuthUser):
    """Get a department's config (prompt + objectives)."""
    await _require_admin(user.email, department)
    config = await _dept_config_repo.get_department_config(department)
    if config is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return config


@router.put("/departments/{department}")
async def update_department_config(department: str, config: dict, user: AuthUser):
    """Update a department's config."""
    await _require_admin(user.email, department)
    await _dept_config_repo.save_department_config(department, config)
    return {"status": "updated"}
