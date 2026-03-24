"""Lambda handler for API Gateway WebSocket events.

Handles $connect, $disconnect, and $default routes. Uses the
Dispatcher-Worker pattern for long-running agent loops.

The Dispatcher ($default) validates the message, sets a session mutex,
and async-invokes itself as a Worker. The Worker runs the agent loop
and pushes tokens back via the API Gateway Management API.
"""

import asyncio
import json
import logging
import os
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Lazy-initialized globals (survive across warm Lambda invocations)
_deps = None
_connections_repo = None


def _init():
    """One-time initialization of deps. Called on first invocation."""
    global _deps, _connections_repo

    if _deps is not None:
        return

    from backend.deps import build_repos, build_storage, build_tool_registry, build_orgchart, build_agent_deps

    repos = build_repos()
    storage = build_storage()
    tool_registry = build_tool_registry()
    orgchart = build_orgchart()
    _deps = build_agent_deps(repos, storage, tool_registry, orgchart)

    from backend.config import settings
    if settings.connections_table:
        from backend.repository.connections import ConnectionsRepository
        _connections_repo = ConnectionsRepository()


def handler(event, context):
    """Lambda entry point. Routes by requestContext.routeKey or WORKER flag."""
    _init()

    # Worker invocation (async invoke from Dispatcher)
    if event.get("_worker"):
        return _handle_worker(event)

    # API Gateway WebSocket event
    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey", "")
    connection_id = request_context.get("connectionId", "")

    if route_key == "$connect":
        return _handle_connect(event, connection_id)
    elif route_key == "$disconnect":
        return _handle_disconnect(connection_id)
    elif route_key == "$default":
        return _handle_default(event, connection_id)
    else:
        logger.warning("Unknown route: %s", route_key)
        return {"statusCode": 400}


def _handle_connect(event, connection_id: str) -> dict:
    """Validate JWT and store connection in DynamoDB."""
    qs = event.get("queryStringParameters") or {}
    token = qs.get("token", "")

    if not token:
        logger.info("Connect rejected: no token")
        return {"statusCode": 401}

    try:
        from backend.auth import _verify_oidc_token
        user = _verify_oidc_token(token)
    except Exception as e:
        logger.info("Connect rejected: invalid token: %s", e)
        return {"statusCode": 401}

    # Store connection
    if _connections_repo:
        _connections_repo.put_connection(connection_id, user.user_id, user.email, user.name)

    logger.info("Connected: user=%s conn=%s", user.user_id, connection_id)
    return {"statusCode": 200}


def _handle_disconnect(connection_id: str) -> dict:
    """Remove connection from DynamoDB."""
    if _connections_repo:
        _connections_repo.delete_connection(connection_id)
    logger.info("Disconnected: conn=%s", connection_id)
    return {"statusCode": 200}


def _handle_default(event, connection_id: str) -> dict:
    """Dispatcher: parse message, dispatch to Worker or handle inline."""
    # Look up who this connection belongs to
    if not _connections_repo:
        return {"statusCode": 500, "body": "Connections table not configured"}

    conn = _connections_repo.get_connection(connection_id)
    if conn is None:
        _send_to_connection(connection_id, {"type": "error", "message": "Connection not found"})
        return {"statusCode": 403}

    # Parse the message
    body = event.get("body", "")
    try:
        msg = json.loads(body) if body else {}
    except json.JSONDecodeError:
        _send_to_connection(connection_id, {"type": "error", "message": "Invalid JSON"})
        return {"statusCode": 200}

    action = msg.get("action", "")

    # Simple actions handled inline by Dispatcher
    if action == "ping":
        _send_to_connection(connection_id, {"type": "pong"})
        return {"statusCode": 200}

    if action == "cancel":
        session_id = msg.get("session_id")
        if session_id and _connections_repo:
            _connections_repo.set_cancelled(session_id)
        return {"statusCode": 200}

    # Actions that need the Worker
    if action in ("chat", "start_session"):
        # For chat/start_session, set the processing mutex
        session_id = msg.get("session_id")
        if session_id:
            if not _connections_repo.set_processing(session_id, connection_id):
                _send_to_connection(connection_id, {
                    "type": "error",
                    "session_id": session_id,
                    "message": "Session is already processing",
                })
                return {"statusCode": 200}

        # Async-invoke self as Worker
        worker_payload = {
            "_worker": True,
            "action": action,
            "connection_id": connection_id,
            "user": {
                "user_id": conn["user_id"],
                "email": conn.get("email", ""),
                "name": conn.get("name", ""),
            },
            "body": msg,
        }

        try:
            import boto3
            from backend.config import settings
            lambda_client = boto3.client("lambda", region_name=settings.aws_region)
            lambda_client.invoke(
                FunctionName=settings.lambda_function_name,
                InvocationType="Event",  # Async
                Payload=json.dumps(worker_payload).encode(),
            )
        except Exception as e:
            logger.exception("Failed to invoke Worker")
            _send_to_connection(connection_id, {
                "type": "error",
                "message": f"Failed to process: {e}",
            })
            # Clear mutex on failure
            if session_id and action in ("chat", "start_session"):
                _connections_repo.clear_processing(session_id)

        return {"statusCode": 200}

    _send_to_connection(connection_id, {"type": "error", "message": f"Unknown action: {action}"})
    return {"statusCode": 200}


def _handle_worker(event) -> dict:
    """Worker: runs the agent loop for chat and start_session actions."""
    action = event.get("action", "")
    connection_id = event.get("connection_id", "")
    user_data = event.get("user", {})
    msg = event.get("body", {})
    session_id = msg.get("session_id")

    try:
        if action == "chat":
            asyncio.run(_worker_chat(connection_id, user_data, msg))
        elif action == "start_session":
            asyncio.run(_worker_start_session(connection_id, user_data, msg))
        else:
            _send_to_connection(connection_id, {"type": "error", "message": f"Unknown worker action: {action}"})
    except Exception as e:
        logger.exception("Worker failed: action=%s session=%s", action, session_id)
        _send_to_connection(connection_id, {
            "type": "error",
            "session_id": session_id,
            "message": "Internal error processing message.",
        })
    finally:
        # Clear processing mutex for chat/start_session
        if action in ("chat", "start_session") and session_id and _connections_repo:
            _connections_repo.clear_processing(session_id)
            _connections_repo.clear_cancelled(session_id)

    return {"statusCode": 200}


async def _worker_chat(connection_id: str, user_data: dict, msg: dict):
    """Worker: handle a chat message."""
    from backend.agent.executor import run_agent_session
    from backend.api.transport import ApiGatewayManagementSender
    from backend.config import settings

    session_id = msg.get("session_id")
    message = msg.get("message", "")

    # Session ownership check
    session = await _deps.sessions_repo.get(user_data["user_id"], session_id)
    if session is None:
        _send_to_connection(connection_id, {
            "type": "error", "session_id": session_id,
            "message": "Session not found or access denied",
        })
        return

    sender = ApiGatewayManagementSender(connection_id, settings.websocket_api_endpoint, settings.aws_region)

    def cancel_check():
        return _connections_repo.is_cancelled(session_id) if _connections_repo else False

    await run_agent_session(
        sender=sender,
        user_id=user_data["user_id"],
        user_email=user_data.get("email", ""),
        user_name=user_data.get("name", ""),
        session_id=session_id,
        user_message=message,
        deps=_deps,
        is_new_session=False,
        session_type=getattr(session, "type", "chat"),
        cancel_check=cancel_check,
    )


async def _worker_start_session(connection_id: str, user_data: dict, msg: dict):
    """Worker: create a new typed session and start conversation."""
    from backend.agent.executor import run_agent_session
    from backend.api.transport import ApiGatewayManagementSender
    from backend.config import settings
    from backend.models import Session
    import uuid

    session_type = msg.get("type", "chat")
    mode = msg.get("mode", "text")

    session_id = str(uuid.uuid4())
    HARDCODED_TITLES = {"intake": "Getting Started", "wrapup": "End of Day Wrap Up", "stuck": "Get Help", "tip": "New Tip"}
    title = HARDCODED_TITLES.get(session_type, "")
    session = Session(session_id=session_id, user_id=user_data["user_id"], title=title, type=session_type)
    await _deps.sessions_repo.create(session)

    sender = ApiGatewayManagementSender(connection_id, settings.websocket_api_endpoint, settings.aws_region)
    await sender.send({"type": "session", "session_id": session_id, "session_type": session_type})

    if mode == "text":
        def cancel_check():
            return _connections_repo.is_cancelled(session_id) if _connections_repo else False

        await run_agent_session(
            sender=sender,
            user_id=user_data["user_id"],
            user_email=user_data.get("email", ""),
            user_name=user_data.get("name", ""),
            session_id=session_id,
            user_message="",
            deps=_deps,
            is_new_session=True,
            session_type=session_type,
            cancel_check=cancel_check,
        )


def _send_to_connection(connection_id: str, data: dict):
    """Send a message to a WebSocket connection via Management API (sync)."""
    from backend.config import settings

    if not settings.websocket_api_endpoint:
        logger.warning("websocket_api_endpoint not configured, cannot send to %s", connection_id)
        return

    try:
        import boto3
        client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=settings.websocket_api_endpoint,
            region_name=settings.aws_region,
        )
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
    except Exception as e:
        logger.warning("Failed to send to connection %s: %s", connection_id, e)
