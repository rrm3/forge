"""System prompt builder for the Forge agent."""

from __future__ import annotations

from backend.models import UserProfile

_BASE_PROMPT = (
    "You are an AI assistant for Digital Science's AI Tuesdays program. "
    "You help employees learn to use AI in their daily work.\n\n"
    "You have access to tools that let you search the knowledge base "
    "(department resources, Gong calls, Dovetail research, roadmap, competitive intelligence), "
    "manage journal entries, track ideas, and update user profiles. "
    "Use them when appropriate to help users effectively.\n\n"
    "When searching, choose tables relevant to the user's question. "
    "For department-specific guidance, search 'department_resources'. "
    "For customer conversations, search 'gong_turns' or 'gong_calls'. "
    "For user research, search 'dovetail_highlights'. "
    "For competitive intelligence, search 'klue_battlecards'."
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
        if profile.manager:
            lines.append(f"Manager: {profile.manager}")
        if profile.team:
            lines.append(f"Team: {profile.team}")
        if profile.location:
            lines.append(f"Location: {profile.location}")
        if profile.direct_reports:
            lines.append(f"Direct reports: {', '.join(profile.direct_reports)}")
        if profile.start_date:
            lines.append(f"Start date: {profile.start_date}")
        if profile.work_summary:
            lines.append(f"Work: {profile.work_summary}")
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
