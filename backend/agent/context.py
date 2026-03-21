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
    session_type: str = "chat",
) -> str:
    """Build a system prompt with optional profile, memory, and skill content.

    Args:
        profile: User profile to personalize the prompt.
        memory: Persistent user/project memory to include.
        skill_instructions: Markdown content of an active skill.
        session_type: Session type (chat, intake, tip, stuck, etc.)

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

    # For intake sessions, inject a live checklist of what's been captured vs what's missing
    if session_type == "intake" and profile:
        parts.append(_build_intake_checklist(profile))

    return "\n\n".join(parts)


# Required fields for intake completion, with human-readable labels
_INTAKE_FIELDS = [
    ("work_summary", "What they work on day-to-day"),
    ("daily_tasks", "Their daily tasks and responsibilities"),
    ("ai_tools_used", "AI tools they've tried"),
    ("ai_proficiency", "AI proficiency level (internal, 1-5 score + rationale)"),
    ("core_skills", "Their core skills"),
    ("learning_goals", "What they want to learn"),
    ("goals", "Goals for the 12 weeks"),
]


def get_intake_checklist(profile: UserProfile) -> list[dict]:
    """Return the intake checklist as structured data for the debug UI."""
    captured = set(profile.intake_fields_captured) if profile.intake_fields_captured else set()
    items = []
    for field_name, label in _INTAKE_FIELDS:
        done = field_name in captured
        value = getattr(profile, field_name, None) if done else None
        # Truncate long values for the tooltip
        value_str = ""
        if value:
            if isinstance(value, list):
                value_str = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                value_str = str(value)
            else:
                value_str = str(value)
            if len(value_str) > 150:
                value_str = value_str[:147] + "..."
        items.append({"field": field_name, "label": label, "done": done, "value": value_str})
    return items


def _build_intake_checklist(profile: UserProfile) -> str:
    """Build a live checklist showing which intake fields are filled vs empty.
    Only counts fields that were captured during the intake conversation,
    not fields pre-filled from the org chart."""
    captured = set(profile.intake_fields_captured) if profile.intake_fields_captured else set()
    done = []
    remaining = []
    remaining_fields = []

    for field_name, label in _INTAKE_FIELDS:
        has_value = field_name in captured
        if has_value:
            done.append(f"  [x] {label}")
        else:
            remaining.append(f"  [ ] {label} -> call update_profile with '{field_name}'")
            remaining_fields.append(field_name)

    lines = ["## Intake Progress"]

    if done:
        lines.append("**Already captured:**")
        lines.extend(done)

    if not remaining:
        lines.append("")
        lines.append("**All fields captured! STOP asking questions.**")
        lines.append("Call `search` for department resources, give 2-3 personalized suggestions,")
        lines.append("then call `update_profile` with `intake_completed_at` and `onboarding_complete: true`.")
    elif len(remaining) <= 2:
        # Almost done - be very directive
        lines.append("")
        lines.append(f"**Almost done - only {len(remaining)} item(s) left:**")
        lines.extend(remaining)
        lines.append("")
        # Check if the only remaining items are internal (agent can fill without asking)
        internal_fields = {"ai_proficiency"}
        only_internal = all(f in internal_fields for f in remaining_fields)
        if only_internal:
            lines.append("IMPORTANT: The remaining field(s) are INTERNAL assessments you fill yourself")
            lines.append("based on what the user already told you. DO NOT ask more questions.")
            lines.append("Score them now, call update_profile, then wrap up with suggestions.")
        else:
            lines.append("Ask about the remaining topic(s), then wrap up. Do not keep going after these.")
    else:
        lines.append("**Still needed (steer the conversation toward these):**")
        lines.extend(remaining)

    return "\n".join(lines)
