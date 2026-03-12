"""Skill loading and auto-detection for the Forge agent."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from backend.models import UserProfile

logger = logging.getLogger(__name__)

# Project root: two levels up from this file (backend/agent/skills.py -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_skill(skill_name: str) -> str | None:
    """Load a skill's markdown content by name.

    Reads from skills/{skill_name}.md relative to the project root.

    Args:
        skill_name: Name of the skill (without .md extension).

    Returns:
        The markdown content, or None if the file doesn't exist.
    """
    path = _PROJECT_ROOT / "skills" / f"{skill_name}.md"
    if not path.is_file():
        logger.debug("Skill file not found: %s", path)
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        logger.exception("Failed to read skill file: %s", path)
        return None


def detect_active_skill(
    profile: UserProfile | None,
    session_message_count: int,
    current_date: date | None = None,
) -> str | None:
    """Detect which skill should be active based on context.

    Args:
        profile: User profile (None means unauthenticated/new user).
        session_message_count: Number of messages already in this session.
        current_date: Override for today's date (for testing).

    Returns:
        Skill name to activate, or None for no forced skill.
    """
    # New or incomplete profile -> onboarding
    if profile is None or not profile.onboarding_complete:
        return "onboarding"

    # Tuesday check-in on new sessions
    today = current_date or date.today()
    if today.weekday() == 1 and session_message_count == 0:
        return "tuesday_checkin"

    return None
