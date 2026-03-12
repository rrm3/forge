"""Profile tools: read, update, and search user profiles."""

import logging

from backend.lance.indexing import index_document
from backend.lance.search import search
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

READ_PROFILE_SCHEMA = {
    "name": "read_profile",
    "description": "Read your profile including role, skills, interests, and AI experience level",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

UPDATE_PROFILE_SCHEMA = {
    "name": "update_profile",
    "description": "Update your profile with new information",
    "input_schema": {
        "type": "object",
        "properties": {
            "fields": {
                "type": "object",
                "description": "Profile fields to update",
                "properties": {
                    "title": {"type": "string"},
                    "department": {"type": "string"},
                    "team": {"type": "string"},
                    "ai_experience_level": {"type": "string"},
                    "interests": {"type": "array", "items": {"type": "string"}},
                    "tools_used": {"type": "array", "items": {"type": "string"}},
                    "goals": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "required": ["fields"],
    },
}

SEARCH_PROFILES_SCHEMA = {
    "name": "search_profiles",
    "description": "Search across all user profiles to find people with specific expertise, roles, or interests",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query describing the expertise or role to find",
            },
        },
        "required": ["query"],
    },
}


async def read_profile(context: ToolContext) -> str:
    repo = context.repos.get("profiles")
    if repo is None:
        return "Profile repository not available."

    profile = await repo.get(context.user_id)
    if profile is None:
        return "No profile found. You can update your profile to get started."

    lines = [f"Profile for {profile.name or profile.user_id}"]
    if profile.email:
        lines.append(f"Email: {profile.email}")
    if profile.title:
        lines.append(f"Title: {profile.title}")
    if profile.department:
        lines.append(f"Department: {profile.department}")
    if profile.team:
        lines.append(f"Team: {profile.team}")
    if profile.manager:
        lines.append(f"Manager: {profile.manager}")
    if profile.ai_experience_level:
        lines.append(f"AI experience level: {profile.ai_experience_level}")
    if profile.interests:
        lines.append(f"Interests: {', '.join(profile.interests)}")
    if profile.tools_used:
        lines.append(f"Tools used: {', '.join(profile.tools_used)}")
    if profile.goals:
        lines.append("Goals:")
        for goal in profile.goals:
            lines.append(f"  * {goal}")

    return "\n".join(lines)


async def update_profile(fields: dict, context: ToolContext) -> str:
    repo = context.repos.get("profiles")
    if repo is None:
        return "Profile repository not available."

    if not fields:
        return "No fields provided to update."

    # Strip unknown keys
    allowed = {"title", "department", "team", "ai_experience_level", "interests", "tools_used", "goals"}
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return f"No valid fields to update. Allowed fields: {', '.join(sorted(allowed))}"

    profile = await repo.get(context.user_id)
    if profile is None:
        return "Profile not found. Cannot update a profile that doesn't exist."

    await repo.update(context.user_id, filtered)

    # Re-index into LanceDB
    try:
        updated = await repo.get(context.user_id)
        content_parts = []
        if updated.name:
            content_parts.append(f"Name: {updated.name}")
        if updated.title:
            content_parts.append(f"Title: {updated.title}")
        if updated.department:
            content_parts.append(f"Department: {updated.department}")
        if updated.team:
            content_parts.append(f"Team: {updated.team}")
        if updated.ai_experience_level:
            content_parts.append(f"AI experience: {updated.ai_experience_level}")
        if updated.interests:
            content_parts.append(f"Interests: {', '.join(updated.interests)}")
        if updated.tools_used:
            content_parts.append(f"Tools: {', '.join(updated.tools_used)}")
        if updated.goals:
            content_parts.append(f"Goals: {', '.join(updated.goals)}")

        content = "\n".join(content_parts)
        await index_document(
            collection="profiles",
            content=content,
            scope_path="profiles",
            document_id=context.user_id,
            extra_fields={"user_id": context.user_id},
        )
    except Exception:
        logger.warning("Profile re-indexing failed for user %s", context.user_id, exc_info=True)

    updated_keys = ", ".join(sorted(filtered.keys()))
    return f"Profile updated successfully. Fields changed: {updated_keys}"


async def search_profiles(query: str, context: ToolContext) -> str:
    result = await search(
        query=query,
        scope_path="profiles",
        collection="profiles",
    )

    if result.get("error"):
        return f"Search failed: {result['error']}"

    results = result.get("results", [])
    if not results:
        return f"No profiles found matching '{query}'."

    lines = [f"Found {len(results)} person/people matching '{query}':\n"]
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        name = meta.get("name", "")
        user_id = meta.get("user_id", "")
        context_text = r.get("match_context", r.get("content", ""))[:200]
        label = name or user_id or f"User {i}"
        lines.append(f"{i}. {label}")
        lines.append(f"   {context_text}")
        lines.append("")

    return "\n".join(lines)


def register_profile_tools(registry) -> None:
    registry.register(READ_PROFILE_SCHEMA, read_profile)
    registry.register(UPDATE_PROFILE_SCHEMA, update_profile)
    registry.register(SEARCH_PROFILES_SCHEMA, search_profiles)
