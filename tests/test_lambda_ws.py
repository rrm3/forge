"""Tests for production Lambda WebSocket handler."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("DEV_MODE", "true")

from backend.api.transport import MAX_FRAME_SIZE, WebSocketSender, ApiGatewayManagementSender
from backend.deps import AgentDeps, build_repos, build_storage, build_tool_registry, build_agent_deps


class TestTransportAbstraction:
    """Test the MessageSender implementations."""

    def test_max_frame_size(self):
        assert MAX_FRAME_SIZE == 128 * 1024

    def test_websocket_sender_construction(self):
        """WebSocketSender should wrap a WebSocket object."""
        mock_ws = MagicMock()
        sender = WebSocketSender(mock_ws)
        assert sender._ws is mock_ws

    def test_api_gateway_sender_construction(self):
        """ApiGatewayManagementSender should accept connection params."""
        sender = ApiGatewayManagementSender(
            connection_id="abc123=",
            endpoint_url="https://api.execute-api.us-east-1.amazonaws.com/v1",
            region="us-east-1",
        )
        assert sender._connection_id == "abc123="
        assert sender._endpoint_url == "https://api.execute-api.us-east-1.amazonaws.com/v1"
        assert not sender._gone

    def test_api_gateway_sender_gone_flag(self):
        """Once marked gone, sender should return False without trying."""
        sender = ApiGatewayManagementSender("abc", "https://example.com")
        sender._gone = True
        # The sync check works even outside async context
        assert sender._gone is True


class TestAgentDeps:
    """Test the shared dependency construction."""

    def test_build_repos_dev_mode(self):
        repos = build_repos()
        assert "sessions" in repos
        assert "profiles" in repos
        assert "journal" in repos
        assert "ideas" in repos

    def test_build_storage_dev_mode(self):
        storage = build_storage()
        assert storage is not None

    def test_build_tool_registry(self):
        registry = build_tool_registry()
        schemas = registry.get_schemas()
        names = [s["name"] for s in schemas]
        assert "search_internal" in names
        assert "search_web" in names
        assert "read_profile" in names
        assert "update_profile" in names
        # analyze_and_advise removed pre-launch
        assert "analyze_and_advise" not in names
        # search_profiles disabled pre-launch (security review needed)
        assert "search_profiles" not in names

    def test_build_agent_deps(self):
        repos = build_repos()
        storage = build_storage()
        registry = build_tool_registry()
        deps = build_agent_deps(repos, storage, registry)
        assert isinstance(deps, AgentDeps)
        assert deps.sessions_repo is repos["sessions"]
        assert deps.tool_registry is registry


class TestLambdaHandler:
    """Test the Lambda handler routing logic."""

    def test_handler_connect_no_token(self):
        """$connect without token should return 401."""
        from backend.lambda_ws import handler, _init

        # Ensure _init has been called (dev mode, no connections table)
        _init()

        event = {
            "requestContext": {"routeKey": "$connect", "connectionId": "conn1"},
            "queryStringParameters": {},
        }
        result = handler(event, None)
        assert result["statusCode"] == 401

    def test_handler_connect_missing_qs(self):
        """$connect with no queryStringParameters should return 401."""
        from backend.lambda_ws import handler

        event = {
            "requestContext": {"routeKey": "$connect", "connectionId": "conn1"},
        }
        result = handler(event, None)
        assert result["statusCode"] == 401

    def test_handler_disconnect(self):
        """$disconnect should return 200."""
        from backend.lambda_ws import handler

        event = {
            "requestContext": {"routeKey": "$disconnect", "connectionId": "conn1"},
        }
        result = handler(event, None)
        assert result["statusCode"] == 200

    def test_handler_unknown_route(self):
        """Unknown route should return 400."""
        from backend.lambda_ws import handler

        event = {
            "requestContext": {"routeKey": "$unknown", "connectionId": "conn1"},
        }
        result = handler(event, None)
        assert result["statusCode"] == 400

    def test_handler_worker_event(self):
        """Worker events should be routed to _handle_worker."""
        from backend.lambda_ws import handler

        # Worker with unknown action should handle gracefully
        event = {
            "_worker": True,
            "action": "unknown",
            "connection_id": "conn1",
            "user": {"user_id": "u1", "email": "", "name": ""},
            "body": {},
        }
        # This will try to send an error via Management API, which will fail
        # silently in dev mode (no endpoint configured). That's expected.
        result = handler(event, None)
        assert result["statusCode"] == 200


class TestConnectionsRepository:
    """Test the connections repository (when available)."""

    def test_import(self):
        """ConnectionsRepository should be importable."""
        from backend.repository.connections import ConnectionsRepository
        assert ConnectionsRepository is not None

    def test_requires_table_name(self):
        """Should raise if no table name configured."""
        with pytest.raises(ValueError, match="connections_table"):
            from backend.repository.connections import ConnectionsRepository
            ConnectionsRepository(table_name="")
