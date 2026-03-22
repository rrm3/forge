"""User Ideas tools: prepare and update personal ideas."""

import logging
from datetime import UTC, datetime

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

PREPARE_IDEA_SCHEMA = {
    "name": "prepare_idea",
    "description": "Prepare an idea for the user to review before saving to their Ideas list. The user will see an editable preview card.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for the idea",
            },
            "description": {
                "type": "string",
                "description": "Description of the AI opportunity in markdown",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories",
            },
        },
        "required": ["title", "description"],
    },
}

UPDATE_IDEA_SCHEMA = {
    "name": "update_idea",
    "description": "Update an existing idea's description, status, or tags based on the conversation",
    "input_schema": {
        "type": "object",
        "properties": {
            "idea_id": {
                "type": "string",
                "description": "The idea ID to update",
            },
            "description": {
                "type": "string",
                "description": "Updated description",
            },
            "status": {
                "type": "string",
                "enum": ["new", "exploring", "done"],
                "description": "New status",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Updated tags",
            },
        },
        "required": ["idea_id"],
    },
}


async def prepare_idea(
    title: str,
    description: str,
    context: ToolContext,
    tags: list[str] | None = None,
) -> str:
    """Prepare an idea for user review. Does NOT save - returns data for frontend preview card."""
    # Get user department from profile for context
    department = ""
    profile_repo = context.repos.get("profiles")
    if profile_repo is not None:
        profile = await profile_repo.get(context.user_id)
        if profile is not None and profile.department:
            department = profile.department

    return (
        f"Idea prepared for review. The user will see an editable preview card with:\n"
        f"Title: {title}\n"
        f"Tags: {', '.join(tags or [])}\n"
        f"Department context: {department or 'not set'}\n"
        f"They can edit it before saving to their Ideas list."
    )


async def update_idea(
    idea_id: str,
    context: ToolContext,
    description: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Update an existing idea and link the current session."""
    user_ideas_repo = context.repos.get("user_ideas")
    if user_ideas_repo is None:
        return "Error: User ideas repository not available."

    idea = await user_ideas_repo.get(context.user_id, idea_id)
    if idea is None:
        return f"Error: Idea '{idea_id}' not found."

    fields = {}
    if description is not None:
        fields["description"] = description
    if status is not None:
        fields["status"] = status
    if tags is not None:
        fields["tags"] = tags

    if fields:
        fields["updated_at"] = datetime.now(UTC).isoformat()
        await user_ideas_repo.update(context.user_id, idea_id, fields)

    # Link current session automatically
    await user_ideas_repo.link_session(context.user_id, idea_id, context.session_id)

    updated_fields = ", ".join(fields.keys()) if fields else "no fields"
    return f"Idea '{idea.title}' updated ({updated_fields}). Session linked."


def register_user_ideas_tools(registry) -> None:
    registry.register(PREPARE_IDEA_SCHEMA, prepare_idea)
    registry.register(UPDATE_IDEA_SCHEMA, update_idea)
