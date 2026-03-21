"""WebSocket chat handler - replaces SSE streaming.

Local dev: FastAPI WebSocket endpoint served by uvicorn.
Production: API Gateway WebSocket API -> Lambda (Dispatcher/Worker pattern).

The message protocol is the same in both modes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agent.context import build_system_prompt
from backend.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from backend.agent.loop import react_loop
from backend.auth import CurrentUser, _verify_oidc_token
from backend.config import settings
from backend.llm import call_llm
from backend.models import Message, Session
from backend.storage import load_memory, load_transcript, save_transcript
from backend.tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level deps, set during app assembly
_sessions_repo = None
_profiles_repo = None
_journal_repo = None
_ideas_repo = None
_storage = None
_tool_registry: ToolRegistry | None = None
_orgchart = None

# Active connections: connection_id -> (websocket, user)
_connections: dict[str, tuple[WebSocket, CurrentUser]] = {}

# Session processing mutex: session_id -> asyncio.Lock
_session_locks: dict[str, asyncio.Lock] = {}

# Cancel events: session_id -> asyncio.Event
_cancel_events: dict[str, asyncio.Event] = {}

# Token batching interval (seconds)
_TOKEN_BATCH_INTERVAL = 0.05  # 50ms

# Max frame size for messages sent to client
_MAX_FRAME_SIZE = 128 * 1024  # 128KB


def set_ws_deps(sessions_repo, profiles_repo, journal_repo, ideas_repo, storage, tool_registry, orgchart=None):
    global _sessions_repo, _profiles_repo, _journal_repo, _ideas_repo, _storage, _tool_registry, _orgchart
    _sessions_repo = sessions_repo
    _profiles_repo = profiles_repo
    _journal_repo = journal_repo
    _ideas_repo = ideas_repo
    _storage = storage
    _tool_registry = tool_registry
    _orgchart = orgchart


async def _send_json(ws: WebSocket, data: dict) -> bool:
    """Send JSON to client. Returns False if the connection is closed."""
    try:
        raw = json.dumps(data)
        # Frame chunking: split large messages
        if len(raw) > _MAX_FRAME_SIZE:
            chunk_id = str(uuid.uuid4())[:8]
            chunks = [raw[i:i + _MAX_FRAME_SIZE] for i in range(0, len(raw), _MAX_FRAME_SIZE)]
            for seq, chunk in enumerate(chunks):
                await ws.send_json({
                    "type": "chunk",
                    "chunk_id": chunk_id,
                    "seq": seq,
                    "total": len(chunks),
                    "data": chunk,
                })
        else:
            await ws.send_text(raw)
        return True
    except Exception:
        return False


async def _authenticate_ws(ws: WebSocket) -> CurrentUser | None:
    """Authenticate WebSocket connection via query string token."""
    token = ws.query_params.get("token")
    if not token:
        return None
    try:
        return _verify_oidc_token(token)
    except Exception:
        return None


def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a session."""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint for chat, session management, and voice."""
    # Authenticate
    user = await _authenticate_ws(ws)
    if user is None:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    conn_id = str(uuid.uuid4())
    _connections[conn_id] = (ws, user)
    logger.info("WebSocket connected: user=%s conn=%s", user.user_id, conn_id)

    try:
        # Send connection confirmation
        await _send_json(ws, {"type": "connected", "user_id": user.user_id})

        # Heartbeat task
        heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))

        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await _send_json(ws, {"type": "error", "message": "Invalid JSON"})
                    continue

                action = msg.get("action")
                if action == "ping":
                    await _send_json(ws, {"type": "pong"})
                elif action == "chat":
                    asyncio.create_task(
                        _handle_chat(ws, user, msg)
                    )
                elif action == "start_session":
                    asyncio.create_task(
                        _handle_start_session(ws, user, msg)
                    )
                elif action == "cancel":
                    _handle_cancel(msg)
                elif action == "voice_session":
                    asyncio.create_task(
                        _handle_voice_session(ws, user, msg)
                    )
                elif action == "tool_call":
                    asyncio.create_task(
                        _handle_tool_call(ws, user, msg)
                    )
                elif action == "transcript":
                    asyncio.create_task(
                        _handle_transcript(ws, user, msg)
                    )
                else:
                    await _send_json(ws, {
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })
        finally:
            heartbeat_task.cancel()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s conn=%s", user.user_id, conn_id)
    except Exception:
        logger.exception("WebSocket error: user=%s conn=%s", user.user_id, conn_id)
    finally:
        _connections.pop(conn_id, None)


async def _heartbeat_loop(ws: WebSocket):
    """Send periodic pings to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(300)  # 5 minutes
            await ws.send_json({"type": "ping"})
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def _handle_start_session(ws: WebSocket, user: CurrentUser, msg: dict):
    """Create a new typed session and start the conversation."""
    session_type = msg.get("type", "chat")
    mode = msg.get("mode", "text")

    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        user_id=user.user_id,
        title="",
        type=session_type,
    )
    await _sessions_repo.create(session)

    # Notify client of the new session
    await _send_json(ws, {
        "type": "session",
        "session_id": session_id,
        "session_type": session_type,
    })

    # For text mode, initiate the AI conversation
    if mode == "text":
        await _run_agent(ws, user, session_id, "", is_new_session=True, session_type=session_type)


async def _handle_chat(ws: WebSocket, user: CurrentUser, msg: dict):
    """Handle a chat message within an existing session."""
    session_id = msg.get("session_id")
    message = msg.get("message", "")

    if not session_id:
        await _send_json(ws, {"type": "error", "message": "Missing session_id"})
        return

    # Session ownership check
    session = await _sessions_repo.get(user.user_id, session_id)
    if session is None:
        await _send_json(ws, {
            "type": "error",
            "session_id": session_id,
            "message": "Session not found or access denied",
        })
        return

    await _run_agent(
        ws, user, session_id, message,
        is_new_session=False,
        session_type=getattr(session, "type", "chat"),
    )


def _handle_cancel(msg: dict):
    """Signal cancellation for an in-progress session."""
    session_id = msg.get("session_id")
    if session_id:
        event = _cancel_events.get(session_id)
        if event:
            event.set()


async def _handle_voice_session(ws: WebSocket, user: CurrentUser, msg: dict):
    """Create an OpenAI Realtime ephemeral token for voice mode."""
    # Placeholder - implemented in Step 8
    await _send_json(ws, {
        "type": "error",
        "message": "Voice mode not yet implemented",
    })


async def _handle_tool_call(ws: WebSocket, user: CurrentUser, msg: dict):
    """Execute a tool call relayed from voice mode."""
    # Placeholder - implemented in Step 8
    await _send_json(ws, {
        "type": "error",
        "message": "Voice tool calls not yet implemented",
    })


async def _handle_transcript(ws: WebSocket, user: CurrentUser, msg: dict):
    """Persist a voice transcript chunk."""
    # Placeholder - implemented in Step 8
    pass


async def _run_agent(
    ws: WebSocket,
    user: CurrentUser,
    session_id: str,
    user_message: str,
    is_new_session: bool = False,
    session_type: str = "chat",
):
    """Run the ReAct agent loop and stream results via WebSocket.

    Implements session mutex to prevent duplicate Workers.
    Uses token batching to reduce the number of WebSocket frames.
    """
    lock = _get_session_lock(session_id)

    # Session mutex: only one agent loop per session at a time
    if lock.locked():
        await _send_json(ws, {
            "type": "error",
            "session_id": session_id,
            "message": "Session is already processing",
        })
        return

    async with lock:
        try:
            await _run_agent_inner(ws, user, session_id, user_message, is_new_session, session_type)
        except Exception:
            logger.exception("Agent loop error: session=%s", session_id)
            await _send_json(ws, {
                "type": "error",
                "session_id": session_id,
                "message": "Internal error processing message.",
            })
        finally:
            _cancel_events.pop(session_id, None)
            # Clean up session lock if no longer needed
            if session_id in _session_locks and not _session_locks[session_id].locked():
                _session_locks.pop(session_id, None)


async def _run_agent_inner(
    ws: WebSocket,
    user: CurrentUser,
    session_id: str,
    user_message: str,
    is_new_session: bool,
    session_type: str,
):
    """Inner agent loop execution with token batching."""
    # Load session transcript
    transcript: list[Message] = []
    if not is_new_session:
        loaded = await load_transcript(_storage, user.user_id, session_id)
        if loaded:
            transcript = loaded

    # Load profile (auto-create on first access)
    profile = await _profiles_repo.get(user.user_id)
    if profile is None:
        from backend.models import UserProfile
        from backend.orgchart import enrich_profile_kwargs
        kwargs: dict = dict(user_id=user.user_id, email=user.email, name=user.name)
        if _orgchart and user.email:
            try:
                kwargs.update(enrich_profile_kwargs(_orgchart, user.email))
            except Exception:
                logger.warning("Org chart lookup failed for %s", user.email, exc_info=True)
        profile = UserProfile(**kwargs)
        await _profiles_repo.create(profile)

    memory = await load_memory(_storage, user.user_id)

    # Load session-type prompt
    from backend.agent.skills import load_skill
    skill_instructions = None
    if session_type and session_type != "chat":
        skill_instructions = load_skill(session_type)

    # Build system prompt
    system_prompt = build_system_prompt(
        profile=profile,
        memory=memory,
        skill_instructions=skill_instructions,
    )

    # Build tool context
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

    # Convert transcript to LLM message format
    llm_messages = _transcript_to_llm_messages(transcript)

    # Set up cancellation
    cancel_event = asyncio.Event()
    _cancel_events[session_id] = cancel_event

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
            await _send_json(ws, {
                "type": "token",
                "session_id": session_id,
                "content": combined,
            })
            token_buffer = []
            last_flush_time = time.monotonic()

    # Run the loop
    first_assistant_text: list[str] = []

    async for event in react_loop(
        user_message=llm_prompt,
        messages=llm_messages,
        system_prompt=system_prompt,
        tools=_tool_registry,
        context=context,
        cancel_event=cancel_event,
    ):
        if isinstance(event, TextEvent):
            first_assistant_text.append(event.text)
            token_buffer.append(event.text)
            # Flush if enough time has passed
            if time.monotonic() - last_flush_time >= _TOKEN_BATCH_INTERVAL:
                await flush_tokens()
        elif isinstance(event, ToolCallEvent):
            await flush_tokens()
            await _send_json(ws, {
                "type": "tool_call",
                "session_id": session_id,
                "tool": event.tool_name,
                "tool_call_id": event.tool_call_id,
                "args": event.arguments,
            })
        elif isinstance(event, ToolResultEvent):
            await _send_json(ws, {
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
            await _send_json(ws, {
                "type": "done",
                "session_id": session_id,
                "usage": usage_data,
            })
        elif isinstance(event, ErrorEvent):
            await flush_tokens()
            await _send_json(ws, {
                "type": "error",
                "session_id": session_id,
                "message": event.error,
            })

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
    await save_transcript(_storage, user.user_id, session_id, transcript)
    session = await _sessions_repo.get(user.user_id, session_id)
    if session:
        session.message_count = len(transcript)
        session.updated_at = datetime.now(UTC)
        await _sessions_repo.update(session)

    # Generate title for new sessions
    if is_new_session and assistant_text:
        try:
            title = await _generate_title(user_message or "New conversation", assistant_text)
            if session:
                session.title = title
                await _sessions_repo.update(session)
            # Notify client of the title
            await _send_json(ws, {
                "type": "session_update",
                "session_id": session_id,
                "title": title,
            })
        except Exception:
            logger.warning("Failed to generate session title", exc_info=True)


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
