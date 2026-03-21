from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
