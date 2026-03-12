"""Chat endpoint - SSE streaming via the ReAct loop."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.context import build_system_prompt
from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.agent.loop import react_loop
from backend.agent.skills import detect_active_skill, load_skill
from backend.agent.sse import format_sse
from backend.auth import AuthUser
from backend.config import settings
from backend.llm import call_llm
from backend.models import Message, Session
from backend.storage import load_memory, load_transcript, save_transcript
from backend.tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Module-level state, set during app assembly
_sessions_repo = None
_profiles_repo = None
_journal_repo = None
_ideas_repo = None
_storage = None
_tool_registry = None

# Cancellation events keyed by session_id
_cancel_events: dict[str, asyncio.Event] = {}


def set_chat_deps(sessions_repo, profiles_repo, journal_repo, ideas_repo, storage, tool_registry):
    global _sessions_repo, _profiles_repo, _journal_repo, _ideas_repo, _storage, _tool_registry
    _sessions_repo = sessions_repo
    _profiles_repo = profiles_repo
    _journal_repo = journal_repo
    _ideas_repo = ideas_repo
    _storage = storage
    _tool_registry = tool_registry


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class CancelRequest(BaseModel):
    session_id: str


@router.post("")
async def chat(body: ChatRequest, user: AuthUser):
    """SSE streaming chat endpoint."""
    return StreamingResponse(
        _chat_stream(body, user),
        media_type="text/event-stream",
    )


@router.post("/cancel")
async def cancel_chat(body: CancelRequest, user: AuthUser):
    """Signal cancellation for an in-progress chat."""
    event = _cancel_events.get(body.session_id)
    if event is not None:
        event.set()
        return {"status": "cancelled"}
    return {"status": "no_active_session"}


async def _chat_stream(body: ChatRequest, user: AuthUser) -> AsyncGenerator[str, None]:
    """Async generator that runs the ReAct loop and yields SSE events."""
    try:
        # 1. Resolve or create session
        session_id = body.session_id or str(uuid.uuid4())
        is_new_session = body.session_id is None

        session = None
        transcript: list[Message] = []

        if not is_new_session:
            session = await _sessions_repo.get(user.user_id, session_id)
            if session is None:
                yield format_sse("error", {"error": "Session not found"})
                return
            loaded = await load_transcript(_storage, user.user_id, session_id)
            if loaded:
                transcript = loaded

        if session is None:
            session = Session(
                session_id=session_id,
                user_id=user.user_id,
                title="",
            )
            await _sessions_repo.create(session)

        # 2. Load profile and memory
        profile = await _profiles_repo.get(user.user_id)
        memory = await load_memory(_storage, user.user_id)

        # 3. Detect active skill
        skill_name = detect_active_skill(profile, len(transcript))
        skill_instructions = None
        if skill_name:
            skill_instructions = load_skill(skill_name)

        # 4. Build system prompt
        system_prompt = build_system_prompt(
            profile=profile,
            memory=memory,
            skill_instructions=skill_instructions,
        )

        # 5. Build tool context
        context = ToolContext(
            user_id=user.user_id,
            session_id=session_id,
            repos={
                "sessions": _sessions_repo,
                "profiles": _profiles_repo,
                "journal": _journal_repo,
                "ideas": _ideas_repo,
            },
            storage=_storage,
            config=settings,
        )

        # 6. Convert transcript to LLM message format
        llm_messages = _transcript_to_llm_messages(transcript)

        # 7. Set up cancellation
        cancel_event = asyncio.Event()
        _cancel_events[session_id] = cancel_event

        # 8. Run the loop and stream events
        first_assistant_text = []
        try:
            async for event in react_loop(
                user_message=body.message,
                messages=llm_messages,
                system_prompt=system_prompt,
                tools=_tool_registry,
                context=context,
                cancel_event=cancel_event,
            ):
                if isinstance(event, TextEvent):
                    first_assistant_text.append(event.text)
                    yield format_sse("text", {"text": event.text})
                elif isinstance(event, ToolCallEvent):
                    yield format_sse("tool_call", {
                        "tool_name": event.tool_name,
                        "tool_call_id": event.tool_call_id,
                        "arguments": event.arguments,
                    })
                elif isinstance(event, ToolResultEvent):
                    yield format_sse("tool_result", {
                        "tool_call_id": event.tool_call_id,
                        "result": event.result,
                    })
                elif isinstance(event, DoneEvent):
                    usage_data = None
                    if event.usage:
                        usage_data = event.usage.model_dump()
                    yield format_sse("done", {"usage": usage_data})
                elif isinstance(event, ErrorEvent):
                    yield format_sse("error", {"error": event.error})
        finally:
            _cancel_events.pop(session_id, None)

        # 9. Append user + assistant messages to transcript
        now = datetime.now(UTC)
        transcript.append(Message(
            role="user",
            content=body.message,
            timestamp=now,
        ))
        assistant_text = "".join(first_assistant_text)
        if assistant_text:
            transcript.append(Message(
                role="assistant",
                content=assistant_text,
                timestamp=now,
            ))

        # 10. Save transcript and update session
        await save_transcript(_storage, user.user_id, session_id, transcript)
        session.message_count = len(transcript)
        session.updated_at = datetime.now(UTC)
        await _sessions_repo.update(session)

        # 11. Generate title for new sessions
        if is_new_session and assistant_text:
            try:
                title = await _generate_title(body.message, assistant_text)
                session.title = title
                await _sessions_repo.update(session)
            except Exception:
                logger.warning("Failed to generate session title", exc_info=True)

    except Exception:
        logger.exception("Chat stream error")
        yield format_sse("error", {"error": "Internal error processing message."})


def _transcript_to_llm_messages(transcript: list[Message]) -> list[dict]:
    """Convert stored Message objects to the LLM's message format."""
    messages = []
    for msg in transcript:
        if msg.role in ("user", "assistant", "system"):
            messages.append({"role": msg.role, "content": msg.content})
    return messages


async def _generate_title(user_msg: str, assistant_msg: str) -> str:
    """Call the LLM to generate a short session title."""
    prompt_messages = [
        {"role": "system", "content": "Generate a short title (max 6 words) for this conversation. Return only the title, no quotes or punctuation."},
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": assistant_msg},
        {"role": "user", "content": "Generate a short title for this conversation."},
    ]
    response = await call_llm(prompt_messages)
    title = (response.content or "New Chat").strip().strip('"').strip("'")
    return title[:100]
