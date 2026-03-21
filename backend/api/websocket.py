"""WebSocket chat handler for local dev (FastAPI/uvicorn).

Production uses lambda_ws.py with API Gateway WebSocket API.
Both share the same agent executor (backend.agent.executor).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agent.context import build_system_prompt
from backend.agent.executor import run_agent_session
from backend.api.transport import WebSocketSender
from backend.auth import CurrentUser, _verify_oidc_token
from backend.config import settings
from backend.deps import AgentDeps
from backend.models import Message, Session
from backend.storage import load_memory, load_transcript, save_transcript
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level deps, set during app assembly
_deps: AgentDeps | None = None

# Active connections: connection_id -> (websocket, user)
_connections: dict[str, tuple[WebSocket, CurrentUser]] = {}

# Session processing mutex: session_id -> asyncio.Lock
_session_locks: dict[str, asyncio.Lock] = {}

# Cancel events: session_id -> asyncio.Event
_cancel_events: dict[str, asyncio.Event] = {}


def set_ws_deps(sessions_repo, profiles_repo, journal_repo, ideas_repo, storage, tool_registry, orgchart=None):
    global _deps
    _deps = AgentDeps(
        sessions_repo=sessions_repo,
        profiles_repo=profiles_repo,
        journal_repo=journal_repo,
        ideas_repo=ideas_repo,
        storage=storage,
        tool_registry=tool_registry,
        orgchart=orgchart,
    )


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
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Main WebSocket endpoint for local dev."""
    user = await _authenticate_ws(ws)
    if user is None:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    conn_id = str(uuid.uuid4())
    _connections[conn_id] = (ws, user)
    sender = WebSocketSender(ws)
    logger.info("WebSocket connected: user=%s conn=%s", user.user_id, conn_id)

    try:
        await sender.send({"type": "connected", "user_id": user.user_id})
        heartbeat_task = asyncio.create_task(_heartbeat_loop(ws))

        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await sender.send({"type": "error", "message": "Invalid JSON"})
                    continue

                action = msg.get("action")
                if action == "ping":
                    await sender.send({"type": "pong"})
                elif action == "chat":
                    asyncio.create_task(_handle_chat(sender, user, msg))
                elif action == "start_session":
                    asyncio.create_task(_handle_start_session(sender, user, msg))
                elif action == "cancel":
                    _handle_cancel(msg)
                elif action == "voice_session":
                    asyncio.create_task(_handle_voice_session(sender, user, msg))
                elif action == "tool_call":
                    asyncio.create_task(_handle_tool_call(sender, user, msg))
                elif action == "transcript":
                    asyncio.create_task(_handle_transcript(sender, user, msg))
                else:
                    await sender.send({"type": "error", "message": f"Unknown action: {action}"})
        finally:
            heartbeat_task.cancel()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s conn=%s", user.user_id, conn_id)
    except Exception:
        logger.exception("WebSocket error: user=%s conn=%s", user.user_id, conn_id)
    finally:
        _connections.pop(conn_id, None)


async def _heartbeat_loop(ws: WebSocket):
    try:
        while True:
            await asyncio.sleep(300)
            await ws.send_json({"type": "ping"})
    except (asyncio.CancelledError, Exception):
        pass


async def _handle_start_session(sender: MessageSender, user: CurrentUser, msg: dict):
    session_type = msg.get("type", "chat")
    session_id = str(uuid.uuid4())
    session = Session(session_id=session_id, user_id=user.user_id, title="", type=session_type)
    await _deps.sessions_repo.create(session)

    await sender.send({"type": "session", "session_id": session_id, "session_type": session_type})

    mode = msg.get("mode", "text")
    if mode == "text":
        await _run_agent(sender, user, session_id, "", is_new_session=True, session_type=session_type)


async def _handle_chat(sender: MessageSender, user: CurrentUser, msg: dict):
    session_id = msg.get("session_id")
    message = msg.get("message", "")

    if not session_id:
        await sender.send({"type": "error", "message": "Missing session_id"})
        return

    session = await _deps.sessions_repo.get(user.user_id, session_id)
    if session is None:
        await sender.send({"type": "error", "session_id": session_id, "message": "Session not found or access denied"})
        return

    await _run_agent(sender, user, session_id, message, is_new_session=False, session_type=getattr(session, "type", "chat"))


def _handle_cancel(msg: dict):
    session_id = msg.get("session_id")
    if session_id:
        event = _cancel_events.get(session_id)
        if event:
            event.set()


async def _handle_voice_session(sender: MessageSender, user: CurrentUser, msg: dict):
    session_id = msg.get("session_id")
    session_type = msg.get("type", "chat")
    resume = msg.get("resume", False)

    if not session_id:
        await sender.send({"type": "error", "message": "Missing session_id for voice session"})
        return

    try:
        profile = await _deps.profiles_repo.get(user.user_id)
        memory = await load_memory(_deps.storage, user.user_id)

        from backend.agent.skills import load_skill
        skill_instructions = None
        if session_type and session_type != "chat":
            skill_instructions = load_skill(session_type)

        system_prompt = build_system_prompt(profile=profile, memory=memory, skill_instructions=skill_instructions)

        transcript_context = None
        if resume:
            transcript = await load_transcript(_deps.storage, user.user_id, session_id)
            if transcript:
                transcript_context = "\n".join(f"{m.role}: {m.content}" for m in transcript)

        from backend.voice import create_voice_session
        result = await create_voice_session(system_prompt=system_prompt, session_id=session_id, transcript_context=transcript_context)

        await sender.send({
            "type": "voice_token",
            "session_id": session_id,
            "token": result["token"],
            "expires_at": result["expires_at"],
        })
    except Exception as e:
        logger.exception("Voice session creation failed")
        await sender.send({"type": "error", "session_id": session_id, "message": f"Failed to create voice session: {e}"})


async def _handle_tool_call(sender: MessageSender, user: CurrentUser, msg: dict):
    tool_name = msg.get("tool")
    tool_args = msg.get("args", {})
    tool_call_id = msg.get("tool_call_id", "")
    session_id = msg.get("session_id")

    if not tool_name or not session_id:
        await sender.send({"type": "error", "message": "Missing tool or session_id"})
        return

    schemas = _deps.tool_registry.get_schemas()
    valid_tools = {s["name"] for s in schemas}
    if tool_name not in valid_tools:
        await sender.send({"type": "tool_result", "session_id": session_id, "tool_call_id": tool_call_id, "result": f"Unknown tool: {tool_name}"})
        return

    session = await _deps.sessions_repo.get(user.user_id, session_id)
    if session is None:
        await sender.send({"type": "tool_result", "session_id": session_id, "tool_call_id": tool_call_id, "result": "Session not found or access denied"})
        return

    context = ToolContext(
        user_id=user.user_id, session_id=session_id,
        repos={"sessions": _deps.sessions_repo, "profiles": _deps.profiles_repo, "journal": _deps.journal_repo, "ideas": _deps.ideas_repo},
        storage=_deps.storage, config=settings,
    )

    try:
        result = await _deps.tool_registry.execute(tool_name, tool_args, context)
    except Exception as exc:
        logger.exception("Voice tool '%s' failed", tool_name)
        result = f"Error executing {tool_name}: {exc}"

    await sender.send({
        "type": "tool_result", "session_id": session_id,
        "tool_call_id": tool_call_id,
        "result": result if isinstance(result, str) else json.dumps(result),
    })


async def _handle_transcript(sender: MessageSender, user: CurrentUser, msg: dict):
    session_id = msg.get("session_id")
    role = msg.get("role", "user")
    content = msg.get("content", "")
    if not session_id or not content:
        return

    session = await _deps.sessions_repo.get(user.user_id, session_id)
    if session is None:
        return

    transcript = await load_transcript(_deps.storage, user.user_id, session_id) or []
    transcript.append(Message(role=role, content=content, timestamp=datetime.now(UTC)))
    await save_transcript(_deps.storage, user.user_id, session_id, transcript)
    session.message_count = len(transcript)
    session.updated_at = datetime.now(UTC)
    await _deps.sessions_repo.update(session)


async def _run_agent(sender: MessageSender, user: CurrentUser, session_id: str, user_message: str, is_new_session: bool = False, session_type: str = "chat"):
    """Run agent with session mutex (local dev in-process lock)."""
    lock = _get_session_lock(session_id)

    if lock.locked():
        await sender.send({"type": "error", "session_id": session_id, "message": "Session is already processing"})
        return

    cancel_event = asyncio.Event()
    _cancel_events[session_id] = cancel_event

    async with lock:
        try:
            await run_agent_session(
                sender=sender,
                user_id=user.user_id,
                user_email=user.email,
                user_name=user.name,
                session_id=session_id,
                user_message=user_message,
                deps=_deps,
                is_new_session=is_new_session,
                session_type=session_type,
                cancel_check=lambda: cancel_event.is_set(),
            )
        except Exception:
            logger.exception("Agent loop error: session=%s", session_id)
            await sender.send({"type": "error", "session_id": session_id, "message": "Internal error processing message."})
        finally:
            _cancel_events.pop(session_id, None)
            _session_locks.pop(session_id, None)


# Type alias for the handler functions
from backend.api.transport import MessageSender
