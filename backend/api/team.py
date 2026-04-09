"""Team endpoints - activity reports for managers and individual activity logs.

Access levels:
- /team/me: Any authenticated user (own activity log)
- /team/members: Department admins see their full subtree; full admins see everyone
- /team/members/{user_id}: Same access rules as /team/members
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException

from backend.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team", tags=["team"])

_profiles_repo = None
_storage = None
_orgchart = None
_dept_config_repo = None


def set_team_deps(profiles_repo, storage, orgchart=None, dept_config_repo=None):
    global _profiles_repo, _storage, _orgchart, _dept_config_repo
    _profiles_repo = profiles_repo
    _storage = storage
    _orgchart = orgchart
    _dept_config_repo = dept_config_repo


def _report_key(user_id: str) -> str:
    return f"reports/activity/{user_id}.json"


async def _load_report(user_id: str) -> dict | None:
    """Load a pre-generated activity report from storage."""
    data = await _storage.read(_report_key(user_id))
    if data is None:
        return None
    return json.loads(data.decode())


async def _is_full_admin(email: str) -> bool:
    """Check if user is a full admin (has ["*"] in admin-access.json)."""
    if not _dept_config_repo:
        return False
    access = await _dept_config_repo.get_admin_access()
    email_lower = email.lower()
    departments = next(
        (v for k, v in access.items() if k.lower() == email_lower),
        None,
    )
    return departments is not None and "*" in departments


def _dfs_tree(orgchart, root_name: str) -> list[dict]:
    """Return the full subtree under root_name in DFS order.

    Each manager is immediately followed by their reports (recursively),
    so the frontend can use adjacency for collapse/expand.
    """
    result = []

    def _visit(name: str, depth: int):
        person = orgchart.lookup_by_name(name)
        result.append({
            "name": name,
            "title": person["title"] if person else "",
            "depth": depth,
        })
        for report_name in orgchart.find_direct_reports(name):
            _visit(report_name, depth + 1)

    for dr in orgchart.find_direct_reports(root_name):
        _visit(dr, 1)

    return result


async def _get_viewable_tree(user: AuthUser, profile) -> list[dict] | None:
    """Determine who this user is allowed to view.

    Returns:
        None: full admin, can see everyone
        list[dict]: specific people (name/title/depth), may be empty
    """
    # Full admins see everyone
    if await _is_full_admin(user.email):
        return None

    # Department admins: full subtree via org chart
    if profile.is_department_admin:
        if _orgchart and profile.name:
            tree = _dfs_tree(_orgchart, profile.name)
            logger.info("Team tree for %s: %d people", profile.name, len(tree))
            return tree
        # Orgchart not loaded - deny rather than degrade to partial access
        logger.warning("Orgchart not available for dept admin %s, denying team access", profile.name)
        return []

    # Not an admin of any kind - no access
    return []


async def _build_member_entry(name: str, profile_cache: dict | None = None) -> dict:
    """Build a member entry for the team response, looking up profile and report."""
    dr_profile = profile_cache.get(name) if profile_cache else await _profiles_repo.find_by_name(name)
    if dr_profile is None:
        return {
            "name": name,
            "user_id": None,
            "has_report": False,
            "has_profile": False,
            "weeks": {},
        }

    report = await _load_report(dr_profile.user_id)
    if report is None:
        return {
            "name": name,
            "user_id": dr_profile.user_id,
            "title": dr_profile.title,
            "department": dr_profile.department,
            "team": dr_profile.team,
            "avatar_url": dr_profile.avatar_url,
            "has_report": False,
            "has_profile": True,
            "weeks": {},
        }

    report["has_report"] = True
    report["has_profile"] = True
    return report


@router.get("/me")
async def my_activity(user: AuthUser):
    """Return the current user's own activity report (Activity Log)."""
    report = await _load_report(user.user_id)
    if report is None:
        return {"user_id": user.user_id, "weeks": {}, "has_report": False}
    report["has_report"] = True
    return report


@router.get("/members")
async def team_members(user: AuthUser):
    """Return activity reports for people this user can view.

    Full admins see everyone. Department admins see their full org subtree.
    Regular users get 403.
    """
    profile = await _profiles_repo.get(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    viewable = await _get_viewable_tree(user, profile)

    if viewable is not None and not viewable:
        raise HTTPException(status_code=403, detail="No team access")

    # Full admin: full org tree from CEO down
    if viewable is None:
        all_profiles = await _profiles_repo.list_all()
        if _orgchart:
            # Find the CEO (person with no manager) and build full DFS tree
            ceo = _orgchart._db.execute("SELECT name FROM people WHERE reports_to IS NULL OR reports_to = ''").fetchone()
            if ceo:
                tree = _dfs_tree(_orgchart, ceo["name"])
            else:
                tree = [{"name": p.name, "title": "", "depth": 1} for p in all_profiles if p.name != profile.name]
        else:
            tree = [{"name": p.name, "title": "", "depth": 1} for p in all_profiles if p.name != profile.name]
    else:
        all_profiles = await _profiles_repo.list_all()
        tree = viewable

    # Build a name->profile cache so we don't re-scan for every member
    profile_cache = {p.name: p for p in all_profiles}

    # Build a depth lookup by name
    depth_map = {entry["name"]: entry["depth"] for entry in tree}
    names = [entry["name"] for entry in tree]

    # Load reports in parallel with concurrency limit
    sem = asyncio.Semaphore(20)

    async def _load(name: str) -> dict:
        async with sem:
            entry = await _build_member_entry(name, profile_cache=profile_cache)
            entry["depth"] = depth_map.get(name, 1)
            return entry

    members = await asyncio.gather(*[_load(n) for n in names])

    return {"members": list(members), "team_size": len(names)}


@router.get("/members/{user_id}")
async def team_member_detail(user_id: str, user: AuthUser):
    """Return detailed activity report for a specific team member.

    Validates that the requesting user has access to view this person.
    """
    profile = await _profiles_repo.get(user.user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    target_profile = await _profiles_repo.get(user_id)
    if target_profile is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check access: recompute the viewable set and verify target is in it
    viewable = await _get_viewable_tree(user, profile)

    # Full admin can see anyone
    if viewable is None:
        pass
    else:
        viewable_names = {entry["name"] for entry in viewable}
        if target_profile.name not in viewable_names:
            raise HTTPException(status_code=403, detail="Access denied")

    report = await _load_report(user_id)
    if report is None:
        return {
            "user_id": user_id,
            "name": target_profile.name,
            "has_report": False,
            "weeks": {},
        }

    report["has_report"] = True
    return report
