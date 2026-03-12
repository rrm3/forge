"""Event types yielded by the ReAct loop."""

from __future__ import annotations

from dataclasses import dataclass

from backend.models import TokenUsage


@dataclass
class TextEvent:
    text: str


@dataclass
class ToolCallEvent:
    tool_name: str
    tool_call_id: str
    arguments: dict


@dataclass
class ToolResultEvent:
    tool_call_id: str
    result: str


@dataclass
class DoneEvent:
    usage: TokenUsage | None = None


@dataclass
class ErrorEvent:
    error: str


LoopEvent = TextEvent | ToolCallEvent | ToolResultEvent | DoneEvent | ErrorEvent
