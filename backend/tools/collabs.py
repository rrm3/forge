"""Collab tools: prepare collaboration requests for user review before publishing."""

import logging

from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

PREPARE_COLLAB_SCHEMA = {
    "name": "prepare_collab",
    "description": "Prepare a collaboration request for the user to review and edit before publishing. The user will see an editable preview card and can modify the content before sharing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short, descriptive title for the collaboration (e.g., 'Automate weekly finance reporting')",
            },
            "problem": {
                "type": "string",
                "description": "Clear description of the problem to solve and what a collaborator would help with. 3-5 sentences.",
            },
            "needed_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills needed from a collaborator (e.g., 'Python', 'Excel', 'Salesforce')",
            },
            "time_commitment": {
                "type": "string",
                "description": "Expected time commitment (e.g., 'A few hours', 'Half a day', 'Multiple AI Tuesdays')",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Discovery tags (e.g., 'automation', 'reporting', 'integration')",
            },
            "department": {
                "type": "string",
                "description": "Author's department",
            },
        },
        "required": ["title", "problem", "needed_skills"],
    },
}


async def prepare_collab(
    title: str,
    problem: str,
    needed_skills: list[str],
    context: ToolContext,
    time_commitment: str | None = None,
    tags: list[str] | None = None,
    department: str | None = None,
) -> str:
    # Get default department from profile if not specified
    author_department = department
    profile_repo = context.repos.get("profiles")
    if profile_repo is not None and not department:
        profile = await profile_repo.get(context.user_id)
        if profile is not None and profile.department:
            author_department = profile.department

    # Don't save - just return the data for the user to review
    return (
        f"Collab prepared for review. The user will see an editable preview card with:\n"
        f"Title: {title}\n"
        f"Problem: {problem}\n"
        f"Needed skills: {', '.join(needed_skills)}\n"
        f"Time commitment: {time_commitment or 'Not specified'}\n"
        f"Department: {author_department or 'Not specified'}\n"
        f"Tags: {', '.join(tags or [])}\n"
        f"They can edit it before publishing."
    )


def register_collab_tools(registry) -> None:
    registry.register(PREPARE_COLLAB_SCHEMA, prepare_collab)
