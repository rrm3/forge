"""DynamoDB connections repository for WebSocket connection state.

Stores connection_id -> user mapping, session processing mutex,
and cancel flags. Uses a single DynamoDB table with TTL.
"""

import asyncio
import logging
import time
from functools import partial

import boto3
from botocore.exceptions import ClientError

from backend.config import settings

logger = logging.getLogger(__name__)

# TTL for connections: 2 hours (API Gateway max connection duration)
_CONNECTION_TTL = 2 * 60 * 60

# TTL for processing locks: 5 minutes (crashed Worker cleanup)
_PROCESSING_TTL = 5 * 60


class ConnectionsRepository:
    """DynamoDB repository for WebSocket connections and session state."""

    def __init__(self, table_name: str | None = None, region: str | None = None) -> None:
        self.table_name = table_name or settings.connections_table
        self.region = region or settings.aws_region
        if not self.table_name:
            raise ValueError("connections_table not configured")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)

    # ----- Connection management -----

    def put_connection(self, connection_id: str, user_id: str, email: str = "", name: str = "") -> None:
        """Store a new WebSocket connection."""
        now = int(time.time())
        self.table.put_item(Item={
            "connection_id": connection_id,
            "user_id": user_id,
            "email": email,
            "name": name,
            "connected_at": str(now),
            "ttl": now + _CONNECTION_TTL,
        })

    def delete_connection(self, connection_id: str) -> None:
        """Remove a connection record."""
        try:
            self.table.delete_item(Key={"connection_id": connection_id})
        except ClientError:
            pass

    def get_connection(self, connection_id: str) -> dict | None:
        """Get user info for a connection. Returns None if not found."""
        try:
            response = self.table.get_item(Key={"connection_id": connection_id})
            return response.get("Item")
        except ClientError:
            return None

    # ----- Session processing mutex -----

    def set_processing(self, session_id: str, connection_id: str) -> bool:
        """Set the processing flag for a session. Returns False if already processing.

        Uses a conditional put to ensure only one Worker runs per session.
        The item key uses a PROCESSING# prefix to distinguish from connections.
        """
        now = int(time.time())
        try:
            self.table.put_item(
                Item={
                    "connection_id": f"PROCESSING#{session_id}",
                    "user_id": "SYSTEM",
                    "worker_connection_id": connection_id,
                    "started_at": str(now),
                    "ttl": now + _PROCESSING_TTL,
                },
                ConditionExpression="attribute_not_exists(connection_id)",
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def clear_processing(self, session_id: str) -> None:
        """Clear the processing flag for a session."""
        try:
            self.table.delete_item(Key={"connection_id": f"PROCESSING#{session_id}"})
        except ClientError:
            pass

    # ----- Cancel flag -----

    def set_cancelled(self, session_id: str) -> None:
        """Set the cancel flag for a session."""
        now = int(time.time())
        self.table.put_item(Item={
            "connection_id": f"CANCEL#{session_id}",
            "user_id": "SYSTEM",
            "ttl": now + _PROCESSING_TTL,
        })

    def is_cancelled(self, session_id: str) -> bool:
        """Check if a session has been cancelled."""
        try:
            response = self.table.get_item(Key={"connection_id": f"CANCEL#{session_id}"})
            return response.get("Item") is not None
        except ClientError:
            return False

    def clear_cancelled(self, session_id: str) -> None:
        """Clear the cancel flag."""
        try:
            self.table.delete_item(Key={"connection_id": f"CANCEL#{session_id}"})
        except ClientError:
            pass
