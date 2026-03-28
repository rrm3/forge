"""System prompt builder for the Forge agent."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.models import UserIdea, UserProfile

_BASE_PROMPT = (
    "You are an AI assistant for Digital Science's AI Tuesdays program. "
    "You help employees learn to use AI in their daily work.\n\n"
    "You have access to tools that let you search internal knowledge bases "
    "(department resources, Gong calls, Dovetail research, roadmap, competitive intelligence) "
    "and the public web, manage journal entries, track ideas, and update user profiles. "
    "Use them when appropriate to help users effectively.\n\n"
    "For internal Digital Science information, use 'search_internal' and choose tables "
    "relevant to the user's question: 'department_resources' for department guidance, "
    "'gong_turns' or 'gong_calls' for customer conversations, 'dovetail_highlights' "
    "for user research, 'klue_battlecards' for competitive intelligence. "
    "For current events, public information, or anything external, use 'search_web'.\n\n"
    "Tools work behind the scenes. Don't mention tool names, describe tool calls, "
    "or share technical details about how you found information. If a tool call "
    "fails, continue the conversation naturally without drawing attention to it."
)


def build_system_prompt(
    profile: UserProfile | None = None,
    memory: str | None = None,
    skill_instructions: str | None = None,
    session_type: str = "chat",
    department_config: dict | None = None,
    intake_responses: dict | None = None,
    idea: UserIdea | None = None,
    company_prompt: str | None = None,
) -> str:
    """Build a system prompt with optional profile, memory, and skill content.

    Args:
        profile: User profile to personalize the prompt.
        memory: Persistent user/project memory to include.
        skill_instructions: Markdown content of an active skill.
        session_type: Session type (chat, intake, tip, stuck, etc.)
        department_config: Department config with prompt and objectives.
        intake_responses: Current intake responses (objective_id -> {value, captured_at}).
        idea: Optional idea for idea-focused coaching chats.
        company_prompt: Company-wide context injected into all sessions.

    Returns:
        The assembled system prompt string.
    """
    parts = [_BASE_PROMPT]

    # Current date
    parts.append(f"Today's date is {datetime.now(UTC).strftime('%A, %B %d, %Y').replace(' 0', ' ')}.")

    # Company context - shared across all sessions
    if company_prompt and company_prompt.strip():
        parts.append(
            "## Company Context\n"
            "The following context is provided by program administrators. "
            "Use it to tailor your advice to the user's organization.\n\n"
            f"{company_prompt.strip()}"
        )

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

    # Department context - injected for all session types
    if department_config is not None:
        dept_ctx = _build_department_context(department_config)
        if dept_ctx:
            parts.append(dept_ctx)

    # Intake-specific: objectives and progress tracking
    if session_type == "intake":
        if department_config is not None:
            objectives_section = _build_intake_objectives(department_config)
            if objectives_section:
                parts.append(objectives_section)

            progress_section = _build_intake_progress(department_config, intake_responses)
            if progress_section:
                parts.append(progress_section)
        elif profile:
            # Fallback: no department config available, use legacy checklist
            parts.append(_build_intake_checklist(profile))

    # Idea context for idea-focused chats
    if idea:
        idea_section = _build_idea_context(idea)
        if idea_section:
            parts.append(idea_section)

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Idea context
# ---------------------------------------------------------------------------

def _build_idea_context(idea: UserIdea) -> str:
    """Build a system prompt section for idea-focused coaching chats."""
    lines = [
        "## Idea Context",
        f"The user wants to explore this idea: **{idea.title}**",
    ]
    if idea.description:
        lines.append(f"\n{idea.description}")
    if idea.tags:
        lines.append(f"\nTags: {', '.join(idea.tags)}")
    lines.append(f"Status: {idea.status}")
    lines.append(f"Idea ID: {idea.idea_id}")
    lines.append("")
    lines.append(
        "Your role is to coach them on this idea. Help them refine it, break it into "
        "actionable steps, identify what they'd need to build or learn, and think through "
        "how it connects to their actual work. Be specific and practical."
    )
    lines.append(
        "When the idea evolves during conversation, call `update_idea` with the idea_id "
        "above to update the description, status, or tags. This keeps the idea record "
        "in sync with what you discuss."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 2: Department context
# ---------------------------------------------------------------------------

def _build_department_context(department_config: dict) -> str | None:
    """Return the department prompt as a section, or None if empty."""
    prompt = department_config.get("prompt", "")
    if not prompt or not prompt.strip():
        return None
    return (
        "## Department Context\n"
        "The following context is provided by the user's department administrators. "
        "Use it to tailor your advice to their team's priorities and tools.\n\n"
        f"{prompt.strip()}"
    )


# ---------------------------------------------------------------------------
# Layer 3: Intake objectives
# ---------------------------------------------------------------------------

def _build_intake_objectives(department_config: dict) -> str | None:
    """Return objectives formatted as instructions for the AI."""
    objectives = department_config.get("objectives", [])
    if not objectives:
        return None
    lines = ["## Intake Objectives", "Cover these topics during the conversation:"]
    for obj in objectives:
        label = obj.get("label", "")
        description = obj.get("description", "")
        lines.append(f"- **{label}**: {description}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Layer 4: Turn progress
# ---------------------------------------------------------------------------

def _build_intake_progress(
    department_config: dict,
    intake_responses: dict | None,
) -> str | None:
    """Return done/remaining status built from intake responses."""
    objectives = department_config.get("objectives", [])
    if not objectives:
        return None

    responses = intake_responses or {}
    done = []
    remaining = []

    for obj in objectives:
        obj_id = obj.get("id", "")
        label = obj.get("label", "")
        description = obj.get("description", "")

        if obj_id in responses:
            value = responses[obj_id].get("value", "")
            summary = _truncate(value, 120)
            done.append(f"  [x] {label}: {summary}")
        else:
            remaining.append((label, description))

    lines = ["## Intake Progress"]

    if not remaining:
        # All objectives complete
        lines.append("")
        lines.append("**ALL OBJECTIVES COMPLETE. THE INTAKE IS DONE.**")
        lines.append("This is your FINAL message. The conversation ends immediately after it and the user CANNOT reply.")
        lines.append("Do NOT ask any questions or end any sentence with a question mark - they will go unanswered.")
        lines.append("Give a brief, warm wrap-up acknowledging what you learned about them,")
        lines.append("then give 2-3 personalized suggestions for their first AI Tuesday.")
        lines.append("Ideas are automatically saved from your suggestions.")
        return "\n".join(lines)

    if done:
        lines.append("**Completed:**")
        lines.extend(done)

    if len(remaining) <= 2:
        # Almost done
        lines.append("")
        lines.append(f"**Almost done - only {len(remaining)} item(s) left:**")
        for label, description in remaining:
            lines.append(f"  [ ] {label}: {description}")
        lines.append("")
        lines.append("Ask about the remaining topic(s), then wrap up. Do not keep going after these.")
    else:
        lines.append("**Remaining (steer the conversation toward these):**")
        for label, description in remaining:
            lines.append(f"  [ ] {label}: {description}")

    return "\n".join(lines)


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ---------------------------------------------------------------------------
# Intake checklist (structured data for debug UI)
# ---------------------------------------------------------------------------

def get_intake_checklist(
    department_config: dict | None,
    intake_responses: dict | None,
    profile: UserProfile | None = None,
) -> list[dict]:
    """Return the intake checklist as structured data for the debug UI.

    Uses department_config objectives when available, falls back to
    legacy _INTAKE_FIELDS + profile.intake_fields_captured.
    """
    if department_config is not None:
        return _get_intake_checklist_from_config(department_config, intake_responses)

    # Fallback: legacy behavior
    if profile is not None:
        return _get_intake_checklist_legacy(profile)

    return []


def _get_intake_checklist_from_config(
    department_config: dict,
    intake_responses: dict | None,
) -> list[dict]:
    """Build checklist from department config objectives."""
    responses = intake_responses or {}
    objectives = department_config.get("objectives", [])
    items = []
    for obj in objectives:
        obj_id = obj.get("id", "")
        label = obj.get("label", "")
        done = obj_id in responses
        value_str = ""
        if done:
            value = responses[obj_id].get("value", "")
            value_str = _truncate(str(value), 150)
        items.append({
            "field": obj_id,
            "label": label,
            "done": done,
            "value": value_str,
        })
    return items


def _get_intake_checklist_legacy(profile: UserProfile) -> list[dict]:
    """Legacy checklist using _INTAKE_FIELDS and profile.intake_fields_captured."""
    captured = set(profile.intake_fields_captured) if profile.intake_fields_captured else set()
    items = []
    for field_name, label in _INTAKE_FIELDS:
        done = field_name in captured
        value = getattr(profile, field_name, None) if done else None
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


# ---------------------------------------------------------------------------
# Legacy constants and helpers (kept as fallback)
# ---------------------------------------------------------------------------

# Required fields for intake completion, with human-readable labels
_INTAKE_FIELDS = [
    ("work_summary", "What they work on day-to-day"),
    ("daily_tasks", "Their daily tasks and responsibilities"),
    ("ai_tools_used", "AI tools they've tried"),
    ("core_skills", "Their core skills"),
    ("learning_goals", "What they want to learn"),
    ("goals", "Goals for the 12 weeks"),
]


def _build_intake_checklist(profile: UserProfile) -> str:
    """Build a live checklist showing which intake fields are filled vs empty.
    Only counts fields that were captured during the intake conversation,
    not fields pre-filled from the org chart.

    Legacy fallback - used when no department_config is available.
    """
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
        lines.append("**ALL FIELDS CAPTURED. THE INTAKE IS COMPLETE.**")
        lines.append("This is your FINAL message. The conversation ends immediately after it and the user CANNOT reply.")
        lines.append("Do NOT ask any questions or end any sentence with a question mark - they will go unanswered.")
        lines.append("Give a brief, warm wrap-up acknowledging what you learned about them,")
        lines.append("then give 2-3 personalized suggestions for their first AI Tuesday.")
        lines.append("Ideas are automatically saved from your suggestions.")
    elif len(remaining) <= 2:
        # Almost done - be very directive
        lines.append("")
        lines.append(f"**Almost done - only {len(remaining)} item(s) left:**")
        lines.extend(remaining)
        lines.append("")
        lines.append("Ask about the remaining topic(s), then wrap up. Do not keep going after these.")
    else:
        lines.append("**Still needed (steer the conversation toward these):**")
        lines.extend(remaining)

    return "\n".join(lines)
