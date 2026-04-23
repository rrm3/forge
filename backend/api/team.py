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
    so the frontend can use adjacency for collapse/expand. Each entry
    includes the person's email from the org chart so callers can join
    to user profiles without relying on name matching.
    """
    result = []
    visited: set[str] = set()

    def _visit(name: str, depth: int):
        key = name.lower()
        if key in visited:
            return
        visited.add(key)
        person = orgchart.lookup_by_name(name)
        result.append({
            "name": name,
            "title": person["title"] if person else "",
            "email": (person["email"] or "") if person else "",
            "depth": depth,
        })
        for report_name in orgchart.find_direct_reports(name):
            _visit(report_name, depth + 1)

    for dr in orgchart.find_direct_reports(root_name):
        _visit(dr, 1)

    return result


def _is_in_subtree(orgchart, admin_name: str, target_name: str) -> bool:
    """Check if target is in admin's org subtree by walking up the manager chain.

    Uses the orgchart's reports_to chain rather than name matching,
    so name collisions between different people cannot bypass access checks.
    """
    current = target_name
    visited: set[str] = set()
    while current:
        key = current.lower()
        if key in visited:
            return False
        visited.add(key)
        if key == admin_name.lower():
            return True
        person = orgchart.lookup_by_name(current)
        if not person:
            return False
        current = person["reports_to"]
    return False


async def _get_viewable_tree(user: AuthUser, profile) -> list[dict] | None:
    """Determine who this user is allowed to view.

    Returns:
        None: full admin, can see everyone
        list[dict]: specific people (name/title/depth), may be empty
    """
    # Full admins see everyone
    if await _is_full_admin(user.email):
        return None

    # Department admins: full subtree via org chart.
    # Locate the admin in the org chart by email (not name) so nickname/full-name
    # differences between systems don't produce an empty tree.
    if profile.is_department_admin:
        if not _orgchart:
            logger.warning("Orgchart not available for dept admin %s, denying team access", profile.email)
            return []
        admin_row = _orgchart.lookup_by_email(profile.email) if profile.email else None
        if not admin_row:
            logger.warning("Dept admin %s (%s) not found in orgchart by email, denying team access", profile.name, profile.email)
            return []
        tree = _dfs_tree(_orgchart, admin_row["name"])
        logger.info("Team tree for %s: %d people", admin_row["name"], len(tree))
        return tree

    # Not an admin of any kind - no access
    return []


async def _build_member_entry(entry: dict, profile_cache: dict | None = None) -> dict:
    """Build a member entry for the team response, looking up profile and report.

    Joins orgchart -> profile strictly by email (case-insensitive). Nickname
    or full-name divergence between systems (e.g. "Steve" vs "Stephen") must
    not drop a user from the view.
    """
    name = entry["name"]
    email = (entry.get("email") or "").lower()

    dr_profile = None
    if email:
        dr_profile = profile_cache.get(email) if profile_cache else await _profiles_repo.find_by_email(email)

    if dr_profile is None:
        return {
            "name": name,
            "title": entry.get("title", ""),
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
            "title": dr_profile.title or entry.get("title", ""),
            "department": dr_profile.department,
            "team": dr_profile.team,
            "avatar_url": dr_profile.avatar_url,
            "has_report": False,
            "has_profile": True,
            "weeks": {},
        }

    report["has_report"] = True
    report["has_profile"] = True
    # Display the orgchart name so the team tree stays internally consistent
    # (e.g. Steve Leicht in orgchart, even if the profile has "Stephen Leicht").
    report["name"] = name
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
            root_name = _orgchart.find_root()
            if root_name:
                tree = _dfs_tree(_orgchart, root_name)
            else:
                tree = [{"name": p.name, "title": "", "email": p.email or "", "depth": 1} for p in all_profiles if p.user_id != profile.user_id]
        else:
            tree = [{"name": p.name, "title": "", "email": p.email or "", "depth": 1} for p in all_profiles if p.user_id != profile.user_id]
    else:
        all_profiles = await _profiles_repo.list_all()
        tree = viewable

    # Build an email->profile cache (case-insensitive) so we don't re-scan for every member.
    # Joining by email is the single source of truth — name mismatches like "Steve" vs
    # "Stephen" must not drop users from the view.
    profile_cache = {p.email.lower(): p for p in all_profiles if p.email}

    # Load reports in parallel with concurrency limit
    sem = asyncio.Semaphore(20)

    async def _load(tree_entry: dict) -> dict:
        async with sem:
            member = await _build_member_entry(tree_entry, profile_cache=profile_cache)
            member["depth"] = tree_entry.get("depth", 1)
            return member

    members = await asyncio.gather(*[_load(e) for e in tree])

    return {"members": list(members), "team_size": len(tree)}


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

    # Check access: full admins see anyone, dept admins must have target in subtree.
    # Look up both admin and target in the orgchart by email so subtree walking
    # uses the orgchart's canonical names (not the profile names, which may diverge).
    if not await _is_full_admin(user.email):
        if not profile.is_department_admin or not _orgchart or not profile.email:
            raise HTTPException(status_code=403, detail="Access denied")
        admin_row = _orgchart.lookup_by_email(profile.email)
        target_row = _orgchart.lookup_by_email(target_profile.email) if target_profile.email else None
        if not admin_row or not target_row:
            raise HTTPException(status_code=403, detail="Access denied")
        if not _is_in_subtree(_orgchart, admin_row["name"], target_row["name"]):
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
