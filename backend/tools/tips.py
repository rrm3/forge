"""Tips & Tricks tools: prepare tips for user review before publishing."""

import logging

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

PREPARE_TIP_SCHEMA = {
    "name": "prepare_tip",
    "description": "Prepare a tip for the user to review and edit before publishing. The user will see an editable preview card and can modify the content before sharing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short, descriptive title for the tip",
            },
            "content": {
                "type": "string",
                "description": "The full tip content in markdown - what was learned, how to do it, why it matters. Keep it concise and actionable.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Categories (e.g., 'content creation', 'data analysis')",
            },
            "department": {
                "type": "string",
                "description": "Department to share with, or 'Everyone' for all",
            },
        },
        "required": ["title", "content"],
    },
}


async def prepare_tip(
    title: str,
    content: str,
    context: ToolContext,
    tags: list[str] | None = None,
    department: str | None = None,
) -> str:
    # Get default department from profile if not specified
    author_department = department or "Everyone"
    profile_repo = context.repos.get("profiles")
    if profile_repo is not None and not department:
        profile = await profile_repo.get(context.user_id)
        if profile is not None and profile.department:
            author_department = profile.department

    # Don't save - just return the data for the user to review
    return (
        f"Tip prepared for review. The user will see an editable preview card with:\n"
        f"Title: {title}\n"
        f"Department: {author_department}\n"
        f"Tags: {', '.join(tags or [])}\n"
        f"They can edit it before publishing."
    )


def register_tips_tools(registry) -> None:
    registry.register(PREPARE_TIP_SCHEMA, prepare_tip)
