"""Transport-agnostic agent session executor.

Runs the ReAct agent loop and sends results via a MessageSender.
Used by both FastAPI WebSocket (local dev) and Lambda handler (production).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from backend.agent.context import build_system_prompt
from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.agent.loop import react_loop
from backend.agent.skills import load_skill
from backend.api.transport import MessageSender
from backend.config import settings
from backend.deps import AgentDeps
from backend.llm import call_llm
from backend.models import Message
from backend.storage import load_memory, load_transcript, save_transcript
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

# Token batching interval (seconds)
_TOKEN_BATCH_INTERVAL = 0.05  # 50ms

# Tools whose calls/results are shown to the client (others hidden unless dev_mode)
_USER_VISIBLE_TOOLS = {"search", "retrieve_document", "search_profiles"}


async def run_agent_session(
    sender: MessageSender,
    user_id: str,
    user_email: str,
    user_name: str,
    session_id: str,
    user_message: str,
    deps: AgentDeps,
    is_new_session: bool = False,
    session_type: str = "chat",
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """Run the ReAct agent loop for a session, streaming results via sender.

    Args:
        sender: Transport for pushing messages to the client.
        user_id: Authenticated user ID.
        user_email: User's email.
        user_name: User's display name.
        session_id: Session ID.
        user_message: The user's message text (empty for session-initiated).
        deps: Agent dependencies (repos, storage, tools, orgchart).
        is_new_session: Whether this is a new session (triggers title generation).
        session_type: Session type (chat, tip, stuck, brainstorm, wrapup, intake).
        cancel_check: Optional callable that returns True if the session is cancelled.
    """
    # Load session transcript
    transcript: list[Message] = []
    if not is_new_session:
        loaded = await load_transcript(deps.storage, user_id, session_id)
        if loaded:
            transcript = loaded

    # Load profile (auto-create on first access)
    profile = await deps.profiles_repo.get(user_id)
    if profile is None:
        from backend.models import UserProfile
        from backend.orgchart import enrich_profile_kwargs
        kwargs: dict = dict(user_id=user_id, email=user_email, name=user_name)
        if deps.orgchart and user_email:
            try:
                kwargs.update(enrich_profile_kwargs(deps.orgchart, user_email))
            except Exception:
                logger.warning("Org chart lookup failed for %s", user_email, exc_info=True)
        profile = UserProfile(**kwargs)
        await deps.profiles_repo.create(profile)

    memory = await load_memory(deps.storage, user_id)

    # Load session-type prompt
    skill_instructions = None
    if session_type and session_type != "chat":
        skill_instructions = load_skill(session_type)

    # Build system prompt
    system_prompt = build_system_prompt(
        profile=profile,
        memory=memory,
        skill_instructions=skill_instructions,
        session_type=session_type,
    )

    # Build tool context
    context = ToolContext(
        user_id=user_id,
        session_id=session_id,
        repos={
            "sessions": deps.sessions_repo,
            "profiles": deps.profiles_repo,
            "journal": deps.journal_repo,
            "ideas": deps.ideas_repo,
        },
        storage=deps.storage,
        config=settings,
    )

    # For intake: run shadow extraction on the user's message BEFORE the agent responds.
    # This updates profile fields so the system prompt checklist is current.
    # Skip on the first turn (no user message yet - just the AI greeting).
    user_message_count = sum(1 for m in transcript if m.role == "user")
    if session_type == "intake" and user_message.strip() and user_message_count > 0:
        try:
            from backend.agent.extraction import extract_profile_data

            # Build messages including the new user message for extraction
            extraction_messages = _transcript_to_llm_messages(transcript)
            extraction_messages.append({"role": "user", "content": user_message.strip()})

            extracted = await extract_profile_data(extraction_messages, profile)
            if extracted:
                # Track which fields were captured during intake
                existing_captured = list(profile.intake_fields_captured) if profile.intake_fields_captured else []
                new_captured = list(set(existing_captured) | set(extracted.keys()))
                extracted["intake_fields_captured"] = new_captured

                await deps.profiles_repo.update(user_id, extracted)
                # Re-read profile and rebuild system prompt with updated checklist
                profile = await deps.profiles_repo.get(user_id) or profile
                system_prompt = build_system_prompt(
                    profile=profile,
                    memory=memory,
                    skill_instructions=skill_instructions,
                    session_type=session_type,
                )
                logger.info("Shadow extraction updated %d fields for user=%s", len(extracted), user_id)
        except Exception:
            logger.warning("Shadow extraction failed, continuing without it", exc_info=True)

    # Convert transcript to LLM message format
    llm_messages = _transcript_to_llm_messages(transcript)

    # Set up cancellation bridge to asyncio.Event
    cancel_event = asyncio.Event()
    cancel_task = None
    if cancel_check:
        cancel_task = asyncio.create_task(_poll_cancel(cancel_check, cancel_event))

    # Determine the prompt
    llm_prompt = user_message.strip() if user_message else "The user just opened the app. Begin the conversation."
    is_silent_start = not user_message.strip()

    # Token batching state
    token_buffer: list[str] = []
    last_flush_time = time.monotonic()

    async def flush_tokens():
        nonlocal token_buffer, last_flush_time
        if token_buffer:
            combined = "".join(token_buffer)
            await sender.send({
                "type": "token",
                "session_id": session_id,
                "content": combined,
            })
            token_buffer = []
            last_flush_time = time.monotonic()

    # Run the loop
    first_assistant_text: list[str] = []

    try:
        async for event in react_loop(
            user_message=llm_prompt,
            messages=llm_messages,
            system_prompt=system_prompt,
            tools=deps.tool_registry,
            context=context,
            cancel_event=cancel_event,
        ):
            if isinstance(event, TextEvent):
                first_assistant_text.append(event.text)
                token_buffer.append(event.text)
                if time.monotonic() - last_flush_time >= _TOKEN_BATCH_INTERVAL:
                    await flush_tokens()
            elif isinstance(event, ToolCallEvent):
                await flush_tokens()
                # Record in transcript for auditability
                transcript.append(Message(
                    role="tool_call",
                    content=json.dumps(event.arguments),
                    tool_name=event.tool_name,
                    tool_call_id=event.tool_call_id,
                    timestamp=datetime.now(UTC),
                ))
                # Send to client: search tools always visible, others only in dev mode
                if event.tool_name in _USER_VISIBLE_TOOLS or settings.dev_mode:
                    await sender.send({
                        "type": "tool_call",
                        "session_id": session_id,
                        "tool": event.tool_name,
                        "tool_call_id": event.tool_call_id,
                        "args": event.arguments,
                    })
            elif isinstance(event, ToolResultEvent):
                # Record in transcript
                transcript.append(Message(
                    role="tool_result",
                    content=event.result if isinstance(event.result, str) else json.dumps(event.result),
                    tool_call_id=event.tool_call_id,
                    timestamp=datetime.now(UTC),
                ))
                # Only send result to client for user-visible tools or dev mode
                if settings.dev_mode:
                    await sender.send({
                        "type": "tool_result",
                        "session_id": session_id,
                        "tool_call_id": event.tool_call_id,
                        "result": event.result,
                    })
            elif isinstance(event, DoneEvent):
                await flush_tokens()
                usage_data = None
                if event.usage:
                    usage_data = event.usage.model_dump()
                # Send intake checklist state before done (for debug UI)
                if session_type == "intake":
                    try:
                        from backend.agent.context import get_intake_checklist
                        fresh_profile = await deps.profiles_repo.get(user_id)
                        if fresh_profile:
                            await sender.send({
                                "type": "intake_progress",
                                "session_id": session_id,
                                "checklist": get_intake_checklist(fresh_profile),
                            })
                    except Exception:
                        pass

                await sender.send({
                    "type": "done",
                    "session_id": session_id,
                    "usage": usage_data,
                })
            elif isinstance(event, ErrorEvent):
                await flush_tokens()
                await sender.send({
                    "type": "error",
                    "session_id": session_id,
                    "message": event.error,
                })
    finally:
        if cancel_task:
            cancel_task.cancel()

    # Final flush
    await flush_tokens()

    # Append messages to transcript
    now = datetime.now(UTC)
    if not is_silent_start:
        transcript.append(Message(
            role="user",
            content=user_message.strip(),
            timestamp=now,
        ))
    assistant_text = "".join(first_assistant_text)
    if assistant_text:
        transcript.append(Message(
            role="assistant",
            content=assistant_text,
            timestamp=now,
        ))

    # Save transcript and update session
    await save_transcript(deps.storage, user_id, session_id, transcript)
    session = await deps.sessions_repo.get(user_id, session_id)
    if session:
        session.message_count = len(transcript)
        session.updated_at = datetime.now(UTC)
        await deps.sessions_repo.update(session)

    # Intake state machine: check required fields and mark complete when done
    if session_type == "intake":
        await _check_intake_completion(deps, user_id, transcript)

    # Generate title for new sessions
    if is_new_session and assistant_text:
        try:
            title = await _generate_title(user_message or "New conversation", assistant_text)
            if session:
                session.title = title
                await deps.sessions_repo.update(session)
            await sender.send({
                "type": "session_update",
                "session_id": session_id,
                "title": title,
            })
        except Exception:
            logger.warning("Failed to generate session title", exc_info=True)


async def _poll_cancel(cancel_check: Callable[[], bool], cancel_event: asyncio.Event):
    """Periodically poll the cancel_check and set the asyncio.Event if True."""
    try:
        while True:
            await asyncio.sleep(1.0)
            if cancel_check():
                cancel_event.set()
                return
    except asyncio.CancelledError:
        pass


def _transcript_to_llm_messages(transcript: list[Message]) -> list[dict]:
    """Convert stored Message objects to the LLM's message format."""
    messages = []
    for msg in transcript:
        if msg.role in ("user", "assistant", "system"):
            messages.append({"role": msg.role, "content": msg.content})

    # Bedrock requires conversations to start with a user message
    if messages and messages[0].get("role") == "assistant":
        messages.insert(0, {"role": "user", "content": "(session started)"})

    return messages


# Intake completion: the conversation has covered enough ground when the user
# has had a substantive exchange (5+ user messages). The structured data
# extraction can happen in real-time via update_profile calls or as a
# post-processing batch job over the transcript later.
_INTAKE_MIN_USER_MESSAGES = 5


async def _check_intake_completion(deps: AgentDeps, user_id: str, transcript: list[Message]):
    """Mark intake complete once the user has had enough conversation.

    The intake is a coverage exercise - did we talk about their work, AI
    experience, and goals? We measure this by user message count as a proxy
    for conversational depth. 5 user messages means they've engaged across
    multiple topics.

    Structured data capture (profile fields) is a bonus - the transcript
    itself is the primary artifact, and we can extract structured data
    from it later if needed.
    """
    try:
        profile = await deps.profiles_repo.get(user_id)
        if not profile or profile.intake_completed_at:
            return

        user_messages = sum(1 for m in transcript if m.role == "user")

        if user_messages >= _INTAKE_MIN_USER_MESSAGES:
            await deps.profiles_repo.update(user_id, {
                "intake_completed_at": datetime.now(UTC).isoformat(),
                "onboarding_complete": True,
            })
            logger.info(
                "Intake complete: user=%s user_messages=%d",
                user_id, user_messages,
            )
    except Exception:
        logger.warning("Failed to check intake completion", exc_info=True)


async def _generate_title(user_msg: str, assistant_msg: str) -> str:
    """Call the LLM to generate a short session title."""
    prompt_messages = [
        {"role": "system", "content": "Generate a short title (max 6 words) for this conversation. Return only the title, no quotes or punctuation."},
        {"role": "user", "content": user_msg or "User started a new session"},
        {"role": "assistant", "content": assistant_msg},
        {"role": "user", "content": "Generate a short title for this conversation."},
    ]
    response = await call_llm(prompt_messages)
    title = (response.content or "New Chat").strip().strip('"').strip("'")
    return title[:100]
