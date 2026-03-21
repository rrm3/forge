"""Skill/prompt loading for session types."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root: two levels up from this file (backend/agent/skills.py -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_skill(skill_name: str) -> str | None:
    """Load a session-type prompt by name.

    Reads from skills/{skill_name}.md relative to the project root.

    Args:
        skill_name: Name of the session type (e.g., "tip", "stuck", "brainstorm", "wrapup", "intake").

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
