from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# AI Tuesdays 12-week program: first Tuesday is March 24, 2026
PROGRAM_START_DATE = date(2026, 3, 24)
PROGRAM_WEEKS = 12


def get_program_week(as_of: date | None = None) -> int:
    """Return the current program week (1-12), clamped to valid range."""
    d = as_of or date.today()
    days_elapsed = (d - PROGRAM_START_DATE).days
    week = max(1, (days_elapsed // 7) + 1)
    return min(week, PROGRAM_WEEKS)


def intake_title(week: int | None = None) -> str:
    """Session title for the intake of a given program week."""
    w = week if week is not None else get_program_week()
    return f"Day {w} Getting Started"


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
    type: str = "chat"  # chat, tip, stuck, brainstorm, wrapup, intake
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


class UserIdea(BaseModel):
    user_id: str
    idea_id: str
    title: str = ""
    description: str = ""
    source: str = "manual"  # intake, brainstorm, chat, manual
    source_session_id: str = ""
    linked_sessions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "new"  # new, exploring, done
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
