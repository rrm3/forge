"""WebSocket chat handler for local dev (FastAPI/uvicorn).

Production uses lambda_ws.py with API Gateway WebSocket API.
Both share the same agent executor (backend.agent.executor).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.agent.executor import run_agent_session
from backend.api.transport import WebSocketSender
from backend.auth import CurrentUser, _masquerade_user, _verify_oidc_token
from backend.config import settings
from backend.deps import AgentDeps
from backend.models import Session

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
    """Authenticate WebSocket connection via query string token.

    In dev_mode, an optional ``masquerade`` query parameter swaps the
    authenticated identity to the given email address.
    """
    token = ws.query_params.get("token")
    if not token:
        return None
    try:
        user = _verify_oidc_token(token)
    except Exception:
        return None

    # Masquerade: swap identity in dev mode
    if settings.dev_mode:
        masquerade_email = ws.query_params.get("masquerade")
        if masquerade_email:
            user = _masquerade_user(masquerade_email, user)

    return user


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


# Type alias used in handler signatures
from backend.api.transport import MessageSender  # noqa: E402
