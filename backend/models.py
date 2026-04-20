from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# AI Tuesdays 12-week program: first Tuesday is March 24, 2026
PROGRAM_START_DATE = date(2026, 3, 24)
PROGRAM_WEEKS = 12


def get_program_week(as_of: date | None = None, timezone: str | None = None) -> int:
    """Return the current program week (1-12), clamped to valid range.

    If timezone is provided (IANA string like 'Pacific/Auckland'), computes
    today's date in that timezone rather than UTC. This ensures users see
    the correct week based on their local date.
    """
    if as_of:
        d = as_of
    elif timezone:
        from zoneinfo import ZoneInfo
        try:
            d = datetime.now(ZoneInfo(timezone)).date()
        except (KeyError, Exception):
            d = date.today()
    else:
        d = date.today()
    days_elapsed = (d - PROGRAM_START_DATE).days
    week = max(1, (days_elapsed // 7) + 1)
    return min(week, PROGRAM_WEEKS)


PLAN_OBJECTIVE_DESCRIPTION = (
    "The user must state what they plan to work on in today's AI Tuesday session. "
    "A vague acknowledgment of last week is not enough. You need a concrete answer to: "
    "what are you going to do today? This could be continuing a project, trying a new tool, "
    "brainstorming an idea, or exploring something specific. "
    "If the plan sounds too ambitious for a single session (e.g. building a full integration, "
    "shipping a product), gently help them scope it to something achievable today: "
    "'That's a great goal - what's the first concrete step you could make progress on today?' "
    "A good plan is a 2-4 hour chunk: research a specific question, prototype one piece, "
    "map out requirements, or test an approach. NOT complete until the user has stated a plan."
)

# Simpler description used by the evaluator (extraction.py). The full
# PLAN_OBJECTIVE_DESCRIPTION contains coaching instructions for the
# conversational AI that conflict with the evaluator's "low bar" policy.
PLAN_EVAL_DESCRIPTION = (
    "The user has stated what they plan to work on today. "
    "Any concrete mention of a task, project, tool, or activity counts."
)


def make_plan_objective(week: int) -> dict:
    """Build the synthetic plan-for-today objective injected for Week 2+."""
    return {
        "id": f"plan-day{week}",
        "label": f"Plan for Day {week}",
        "description": PLAN_OBJECTIVE_DESCRIPTION,
        "eval_description": PLAN_EVAL_DESCRIPTION,
    }


def effective_program_week(profile: "UserProfile", timezone: str | None = None) -> int:
    """Return the program week for a user, respecting per-user override for testing.

    Uses the user's stored timezone (from their browser) to determine today's date,
    so users in early timezones (e.g., New Zealand) see the correct week.
    """
    if profile.program_week_override and profile.program_week_override > 0:
        return min(profile.program_week_override, PROGRAM_WEEKS)
    tz = timezone or profile.timezone or None
    return get_program_week(timezone=tz)


def intake_title(week: int | None = None) -> str:
    """Session title for the intake of a given program week."""
    w = week if week is not None else get_program_week()
    return f"Day {w} Getting Started" if w <= 1 else f"Day {w} Plan"


def wrapup_title(week: int | None = None) -> str:
    """Session title for the wrapup of a given program week."""
    w = week if week is not None else get_program_week()
    return f"Day {w} Wrap-up"


def _now() -> datetime:
    return datetime.now(UTC)


class Session(BaseModel):
    session_id: str
    user_id: str
    title: str = ""
    type: str = "chat"  # chat, tip, stuck, brainstorm, wrapup, intake, collab
    program_week: int = 0  # Set for intake/wrapup sessions to identify which week
    idea_id: str = ""  # Linked idea for idea-focused chats
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    message_count: int = 0
    summary: str = ""


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool_call", "tool_result"]
    content: str
    timestamp: datetime = Field(default_factory=_now)
    tool_name: str | None = None
    tool_call_id: str | None = None


class AIProficiency(BaseModel):
    """AI proficiency level (1-5) with rationale, scored by the AI during intake."""
    level: int = 0  # 1-5 scale
    rationale: str = ""  # Why this score was given


class UserProfile(BaseModel):
    user_id: str
    email: str = ""
    name: str = ""
    title: str = ""
    department: str = ""
    manager: str = ""
    direct_reports: list[str] = Field(default_factory=list)
    team: str = ""
    ai_experience_level: str = ""
    interests: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    avatar_url: str = ""
    location: str = ""
    timezone: str = ""  # IANA timezone from browser (e.g., "Pacific/Auckland")
    start_date: str = ""
    work_summary: str = ""
    onboarding_complete: bool = False
    # v2 intake fields
    products: list[str] = Field(default_factory=list)
    daily_tasks: str = ""
    core_skills: list[str] = Field(default_factory=list)
    learning_goals: list[str] = Field(default_factory=list)
    ai_tools_used: list[str] = Field(default_factory=list)
    ai_superpower: str = ""
    ai_proficiency: AIProficiency | None = None
    intake_summary: str = ""
    intake_fields_captured: list[str] = Field(default_factory=list)  # fields set during intake conversation
    intake_completed_at: datetime | None = None
    intake_skipped: bool = False
    intake_objectives_done: int = 0
    intake_objectives_total: int = 0
    intake_weeks: dict = Field(default_factory=dict)  # {"1": "ISO datetime", "2": "ISO datetime", ...}
    # Written only by `_enrich_profile_async` when identity-field enrichment
    # succeeds for the first time. Used as the gate signal for W4-03 so that
    # weekly check-ins don't re-run enrichment and clobber user corrections.
    # See docs/designs/2026-04-19-weekly-enrichment-overwrite.md.
    intake_enrichment_completed_at: datetime | None = None
    program_week_override: int = 0  # If set (>0), overrides clock-based week for testing
    is_department_admin: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class JournalEntry(BaseModel):
    entry_id: str
    user_id: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class Idea(BaseModel):
    idea_id: str
    title: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    proposed_by: str
    proposed_by_name: str = ""
    status: str = "open"  # e.g. "open", "in_progress", "completed", "archived"
    interested_users: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class Tip(BaseModel):
    tip_id: str
    author_id: str
    department: str = ""
    title: str = ""
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    category: str = "tip"  # tip, gem, skill
    artifact: str = ""  # gem instructions or skill definition (markdown)
    vote_count: int = 0
    comment_count: int = 0
    source_session_id: str = ""  # Session that produced this tip via prepare_tip
    source_tool_call_id: str = ""  # tool_call_id of the prepare_tip invocation
    created_at: datetime = Field(default_factory=_now)


class TipVote(BaseModel):
    tip_id: str
    user_id: str
    created_at: datetime = Field(default_factory=_now)


class TipComment(BaseModel):
    tip_id: str
    comment_id: str
    author_id: str
    content: str
    created_at: datetime = Field(default_factory=_now)


class Collaboration(BaseModel):
    collab_id: str
    author_id: str
    department: str = ""
    title: str
    problem: str
    needed_skills: list[str] = Field(default_factory=list)
    time_commitment: str = ""
    status: str = "open"  # open | building | done | archived
    interested_count: int = 0
    comment_count: int = 0
    business_value: str = ""
    tags: list[str] = Field(default_factory=list)
    source_session_id: str = ""  # Session that produced this collab via prepare_collab
    source_tool_call_id: str = ""  # tool_call_id of the prepare_collab invocation
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CollabInterest(BaseModel):
    collab_id: str
    user_id: str
    message: str = ""
    created_at: datetime = Field(default_factory=_now)


class CollabComment(BaseModel):
    collab_id: str
    comment_id: str
    author_id: str
    content: str
    created_at: datetime = Field(default_factory=_now)


class UserIdea(BaseModel):
    user_id: str
    idea_id: str
    title: str = ""
    description: str = ""
    source: str = "manual"  # intake, brainstorm, chat, manual
    source_session_id: str = ""
    source_tool_call_id: str = ""  # tool_call_id of the prepare_idea invocation when created via that path
    linked_sessions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "new"  # new, exploring, done
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
