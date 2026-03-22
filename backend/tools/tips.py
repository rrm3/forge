"""Tips & Tricks tools: publish tips to share with colleagues."""

import logging
import uuid

from backend.models import Tip
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

PUBLISH_TIP_SCHEMA = {
    "name": "publish_tip",
    "description": "Publish a tip or trick to share with colleagues across Digital Science",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short, descriptive title for the tip",
            },
            "content": {
                "type": "string",
                "description": "The full tip content - what was learned, how to do it, why it matters",
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


async def publish_tip(
    title: str,
    content: str,
    context: ToolContext,
    tags: list[str] | None = None,
    department: str | None = None,
) -> str:
    repo = context.repos.get("tips")
    if repo is None:
        return "Tips repository not available."

    # Get author name and department from profile
    author_name = ""
    author_department = department or "Everyone"
    profile_repo = context.repos.get("profiles")
    if profile_repo is not None:
        profile = await profile_repo.get(context.user_id)
        if profile is not None:
            author_name = profile.name
            if not department:
                author_department = profile.department or "Everyone"

    tip_id = str(uuid.uuid4())
    tip = Tip(
        tip_id=tip_id,
        author_id=context.user_id,
        author_name=author_name,
        department=author_department,
        title=title,
        content=content,
        tags=tags or [],
    )
    await repo.create(tip)

    return f"Tip '{title}' published to {author_department} (ID: {tip_id})."


def register_tips_tools(registry) -> None:
    registry.register(PUBLISH_TIP_SCHEMA, publish_tip)
