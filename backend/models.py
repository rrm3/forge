from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Session(BaseModel):
    session_id: str
    user_id: str
    title: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0
    summary: str = ""


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool_call", "tool_result"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: str | None = None
    tool_call_id: str | None = None


class UserProfile(BaseModel):
    user_id: str
    email: str = ""
    name: str = ""
    title: str = ""
    department: str = ""
    manager: str = ""
    direct_reports: list[str] = Field(default_factory=list)
    team: str = ""
    ai_experience_level: str = ""  # e.g. "beginner", "intermediate", "advanced"
    interests: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    onboarding_complete: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JournalEntry(BaseModel):
    entry_id: str
    user_id: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Idea(BaseModel):
    idea_id: str
    title: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    proposed_by: str
    proposed_by_name: str = ""
    status: str = "open"  # e.g. "open", "in_progress", "completed", "archived"
    interested_users: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
