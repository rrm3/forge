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
    "description": "Update the user's profile with new information captured during conversation",
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
                    "products": {"type": "array", "items": {"type": "string"}},
                    "daily_tasks": {"type": "string"},
                    "work_summary": {"type": "string", "description": "User's own description of their day-to-day work"},
                    "core_skills": {"type": "array", "items": {"type": "string"}},
                    "learning_goals": {"type": "array", "items": {"type": "string"}},
                    "ai_tools_used": {"type": "array", "items": {"type": "string"}},
                    "ai_superpower": {"type": "string"},
                    "ai_proficiency": {
                        "type": "object",
                        "properties": {
                            "level": {"type": "integer", "minimum": 1, "maximum": 5, "description": "AI proficiency level 1-5"},
                            "rationale": {"type": "string", "description": "Brief explanation of why this level was assigned"},
                        },
                    },
                    "intake_summary": {"type": "string"},
                    "intake_completed_at": {"type": "string", "description": "ISO 8601 datetime when intake was completed"},
                    "onboarding_complete": {"type": "boolean"},
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


async def update_profile(context: ToolContext, fields: dict | None = None, **kwargs) -> str:
    repo = context.repos.get("profiles")
    if repo is None:
        return "Profile repository not available."

    # Handle both {"fields": {...}} and flat {"daily_tasks": "..."} formats
    # LLMs sometimes flatten the schema
    if not fields and kwargs:
        fields = kwargs
    if not fields:
        return "No fields provided to update."

    # Strip unknown keys.
    # intake_completed_at and onboarding_complete are managed by _check_intake_completion,
    # not by the agent. Silently drop them to prevent a race condition where the agent
    # sets intake_completed_at before the completion check runs, causing it to skip
    # idea creation.
    allowed = {
        "title", "department", "team", "ai_experience_level", "interests",
        "tools_used", "goals", "products", "daily_tasks", "work_summary",
        "core_skills", "learning_goals", "ai_tools_used", "ai_superpower",
        "ai_proficiency", "intake_summary", "intake_fields_captured",
    }
    filtered = {k: v for k, v in fields.items() if k in allowed}
    if not filtered:
        return "Profile updated successfully."

    # Coerce list→string for fields that expect strings (LLMs sometimes send lists)
    _string_fields = {
        "title", "department", "team", "ai_experience_level", "daily_tasks",
        "work_summary", "ai_superpower", "intake_summary", "intake_completed_at",
    }
    for key in _string_fields:
        if key in filtered and isinstance(filtered[key], list):
            filtered[key] = "; ".join(str(v) for v in filtered[key])

    # Coerce string→list for fields that expect lists (LLMs sometimes send strings)
    _list_fields = {
        "interests", "tools_used", "goals", "products", "core_skills",
        "learning_goals", "ai_tools_used", "intake_fields_captured",
    }
    for key in _list_fields:
        if key in filtered and isinstance(filtered[key], str):
            # Split on semicolons first (our canonical delimiter), fall back to commas
            val = filtered[key]
            parts = val.split(";") if ";" in val else val.split(",")
            filtered[key] = [v.strip() for v in parts if v.strip()]

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
