"""Admin trends report endpoint — serves trends.json from S3."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_storage = None
_dept_config_repo = None
_orgchart_db = None

_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 60


def set_reports_deps(storage, dept_config_repo, orgchart=None):
    global _storage, _dept_config_repo, _orgchart
    _storage = storage
    _dept_config_repo = dept_config_repo
    _orgchart = orgchart


async def _require_admin(email: str):
    access = await _dept_config_repo.get_admin_access()
    email_lower = email.lower()
    departments = next(
        (v for k, v in access.items() if k.lower() == email_lower),
        None,
    )
    if departments is None:
        raise HTTPException(status_code=403, detail="Not an admin")
    return departments


def _get_orgchart_sizes() -> dict[str, int]:
    """Get department sizes from the in-memory OrgChart for privacy roll-up."""
    if _orgchart is None:
        return {}
    try:
        rows = _orgchart._db.execute(
            "SELECT department, COUNT(*) as cnt FROM people "
            "WHERE department IS NOT NULL GROUP BY department"
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        logger.warning("Failed to read orgchart for dept sizes", exc_info=True)
        return {}


def _strip_named(data: dict) -> dict:
    """Remove the _named block for shareable mode."""
    result = {k: v for k, v in data.items() if k != "_named"}
    return result


def _roll_up_small_departments(data: dict, dept_sizes: dict[str, int], threshold: int = 10) -> dict:
    """Roll departments with fewer than threshold members into 'Other'."""
    small_depts = {d for d, size in dept_sizes.items() if size < threshold}
    if not small_depts:
        return data

    other_label = "Other (fewer than 10 staff)"

    if "departments" in data:
        depts = data["departments"]
        new_active = []
        other_weekly: dict[int, dict] = {}

        for entry in depts.get("active_by_week", []):
            if entry["department"] in small_depts:
                for wd in entry.get("weekly", []):
                    w = wd.get("week", 0)
                    if w not in other_weekly:
                        other_weekly[w] = {"week": w, "active": 0, "signups": 0}
                    other_weekly[w]["active"] += wd.get("active", 0)
                    other_weekly[w]["signups"] += wd.get("signups", 0)
            else:
                new_active.append(entry)

        if other_weekly:
            new_active.append({
                "department": other_label,
                "weekly": sorted(other_weekly.values(), key=lambda x: x["week"]),
            })

        new_momentum = [
            m for m in depts.get("momentum", []) if m["department"] not in small_depts
        ]

        new_list = [d for d in depts.get("list", []) if d not in small_depts]
        if other_weekly:
            new_list.append(other_label)

        data["departments"] = {
            "list": new_list,
            "active_by_week": new_active,
            "momentum": new_momentum,
        }

    if "sentiment" in data:
        data["sentiment"]["by_department_by_week"] = [
            entry for entry in data["sentiment"].get("by_department_by_week", [])
            if entry.get("department") not in small_depts
        ]

    return data


@router.get("/trends")
async def get_trends(
    user: AuthUser,
    mode: str = Query("full", pattern="^(full|shareable)$"),
):
    """Serve the cumulative trends report, optionally sanitised."""
    await _require_admin(user.email)

    cache_key = f"trends:{mode}"
    now = time.time()
    if cache_key in _cache:
        cached_at, cached_data = _cache[cache_key]
        if now - cached_at < CACHE_TTL:
            return JSONResponse(
                content=cached_data,
                headers={"Cache-Control": "no-store"},
            )

    raw = await _storage.read("reports/trends.json")
    if raw is None:
        raise HTTPException(
            status_code=404,
            detail="No trends report uploaded yet. Run /forge-trends to generate.",
        )

    data = json.loads(raw)

    if mode == "shareable":
        data = _strip_named(data)
        dept_sizes = _get_orgchart_sizes()
        if dept_sizes:
            data = _roll_up_small_departments(data, dept_sizes)

    _cache[cache_key] = (now, data)

    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store"},
    )
