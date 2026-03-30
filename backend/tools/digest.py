"""Digest tool: fetch the previous week's digest for the current user."""

import logging

from backend.tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

GET_DIGEST_SCHEMA = {
    "name": "get_previous_digest",
    "description": (
        "Fetch the most recent weekly digest for the current user. "
        "The digest is a narrative summary of what the user did in a previous week: "
        "projects worked on, tools explored, ideas created, reflections, and suggested "
        "follow-ups. Use this at the start of Week 2+ intake conversations to pick up "
        "where the user left off. Returns the digest markdown text, or a message if "
        "no digest is available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


async def get_previous_digest(*, context: ToolContext) -> str:
    """Find and return the most recent digest for the user.

    Scans backwards from current_week - 1 to find the latest digest file.
    E.g., in Week 5, checks digest-week4.md, then digest-week3.md, etc.
    """
    if not context.storage:
        return "No digest available."

    # Get the user's effective program week
    from backend.models import effective_program_week
    profile = None
    if "profiles" in context.repos:
        profile = await context.repos["profiles"].get(context.user_id)

    if not profile:
        return "No digest available."

    current_week = effective_program_week(profile)
    if current_week <= 1:
        return "No previous week digest available (this is Week 1)."

    # Scan backwards from current_week - 1
    for week in range(current_week - 1, 0, -1):
        key = f"profiles/{context.user_id}/digest-week{week}.md"
        data = await context.storage.read(key)
        if data is not None:
            logger.info("Loaded digest-week%d for user=%s", week, context.user_id)
            return data.decode()

    return "No previous week digest found. This may be the user's first week back, or digests haven't been generated yet."


def register_digest_tools(registry: ToolRegistry):
    """Register digest tools."""
    registry.register(GET_DIGEST_SCHEMA, get_previous_digest)
