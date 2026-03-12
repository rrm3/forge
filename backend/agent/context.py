"""System prompt builder for the Forge agent."""

from __future__ import annotations

from backend.models import UserProfile

_BASE_PROMPT = (
    "You are an AI assistant for Digital Science's AI Tuesdays program. "
    "You help employees learn to use AI in their daily work.\n\n"
    "You have access to tools that let you search the knowledge base, "
    "manage journal entries, track ideas, and update user memory. "
    "Use them when appropriate to help users effectively."
)


def build_system_prompt(
    profile: UserProfile | None = None,
    memory: str | None = None,
    skill_instructions: str | None = None,
) -> str:
    """Build a system prompt with optional profile, memory, and skill content.

    Args:
        profile: User profile to personalize the prompt.
        memory: Persistent user/project memory to include.
        skill_instructions: Markdown content of an active skill.

    Returns:
        The assembled system prompt string.
    """
    parts = [_BASE_PROMPT]

    if profile:
        lines = []
        if profile.name:
            lines.append(f"Name: {profile.name}")
        if profile.email:
            lines.append(f"Email: {profile.email}")
        if profile.title:
            lines.append(f"Title: {profile.title}")
        if profile.department:
            lines.append(f"Department: {profile.department}")
        if profile.team:
            lines.append(f"Team: {profile.team}")
        if profile.ai_experience_level:
            lines.append(f"AI experience: {profile.ai_experience_level}")
        if profile.interests:
            lines.append(f"Interests: {', '.join(profile.interests)}")
        if profile.goals:
            lines.append(f"Goals: {', '.join(profile.goals)}")
        if lines:
            parts.append("## About the User\n" + "\n".join(lines))

    if memory:
        parts.append(f"## Memory\n{memory}")

    if skill_instructions:
        parts.append(skill_instructions)

    return "\n\n".join(parts)
