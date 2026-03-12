"""Ideas Exchange tools: propose and list project ideas."""

import logging
import uuid

from backend.models import Idea
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

PROPOSE_IDEA_SCHEMA = {
    "name": "propose_idea",
    "description": "Submit a project idea or opportunity to the Ideas Exchange",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title for the idea",
            },
            "description": {
                "type": "string",
                "description": "Full description of the idea and its potential impact",
            },
            "required_skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skills or expertise needed to work on this idea",
            },
        },
        "required": ["title", "description"],
    },
}

LIST_IDEAS_SCHEMA = {
    "name": "list_ideas",
    "description": "Browse project ideas and opportunities in the Ideas Exchange",
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by status: open, in_progress, completed, archived",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of ideas to return (default 20)",
                "default": 20,
            },
        },
        "required": [],
    },
}


async def propose_idea(
    title: str,
    description: str,
    context: ToolContext,
    required_skills: list[str] | None = None,
) -> str:
    repo = context.repos.get("ideas")
    if repo is None:
        return "Ideas repository not available."

    # Get proposer name from profile if available
    proposer_name = ""
    profile_repo = context.repos.get("profiles")
    if profile_repo is not None:
        profile = await profile_repo.get(context.user_id)
        if profile is not None:
            proposer_name = profile.name

    idea_id = str(uuid.uuid4())
    idea = Idea(
        idea_id=idea_id,
        title=title,
        description=description,
        required_skills=required_skills or [],
        proposed_by=context.user_id,
        proposed_by_name=proposer_name,
        status="open",
    )
    await repo.create(idea)

    skills_info = f" Required skills: {', '.join(required_skills)}." if required_skills else ""
    return f"Idea '{title}' submitted to the Ideas Exchange (ID: {idea_id}).{skills_info}"


async def list_ideas(
    context: ToolContext,
    status: str | None = None,
    limit: int = 20,
) -> str:
    repo = context.repos.get("ideas")
    if repo is None:
        return "Ideas repository not available."

    ideas = await repo.list(status_filter=status, limit=limit)

    if not ideas:
        filter_note = f" with status '{status}'" if status else ""
        return f"No ideas found{filter_note}."

    status_header = f" (status: {status})" if status else ""
    lines = [f"{len(ideas)} idea(s) in the Ideas Exchange{status_header}:\n"]

    for i, idea in enumerate(ideas, 1):
        date_str = idea.created_at.strftime("%Y-%m-%d")
        proposer = idea.proposed_by_name or idea.proposed_by
        skills_str = f"  Skills needed: {', '.join(idea.required_skills)}" if idea.required_skills else ""
        lines.append(f"{i}. [{idea.status.upper()}] {idea.title} (ID: {idea.idea_id})")
        lines.append(f"   Proposed by: {proposer} on {date_str}")
        lines.append(f"   {idea.description}")
        if skills_str:
            lines.append(f"   {skills_str}")
        if idea.interested_users:
            lines.append(f"   Interested: {len(idea.interested_users)} person/people")
        lines.append("")

    return "\n".join(lines)


def register_ideas_tools(registry) -> None:
    registry.register(PROPOSE_IDEA_SCHEMA, propose_idea)
    registry.register(LIST_IDEAS_SCHEMA, list_ideas)
