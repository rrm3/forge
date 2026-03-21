"""Transport abstraction for sending messages to WebSocket clients.

Two implementations:
- WebSocketSender: FastAPI WebSocket (local dev, uvicorn)
- ApiGatewayManagementSender: API Gateway Management API (production Lambda)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Protocol

logger = logging.getLogger(__name__)

# Max frame size for messages sent to client (API Gateway limit: 128KB server-to-client)
MAX_FRAME_SIZE = 128 * 1024


class MessageSender(Protocol):
    """Protocol for sending JSON messages to a connected client."""

    async def send(self, data: dict) -> bool:
        """Send a JSON message. Returns False if the connection is gone."""
        ...


class WebSocketSender:
    """Sends messages via FastAPI WebSocket (local dev)."""

    def __init__(self, ws) -> None:
        self._ws = ws

    async def send(self, data: dict) -> bool:
        try:
            raw = json.dumps(data)
            if len(raw) > MAX_FRAME_SIZE:
                return await self._send_chunked(raw)
            await self._ws.send_text(raw)
            return True
        except Exception:
            return False

    async def _send_chunked(self, raw: str) -> bool:
        chunk_id = str(uuid.uuid4())[:8]
        chunks = [raw[i:i + MAX_FRAME_SIZE] for i in range(0, len(raw), MAX_FRAME_SIZE)]
        for seq, chunk in enumerate(chunks):
            try:
                await self._ws.send_json({
                    "type": "chunk",
                    "chunk_id": chunk_id,
                    "seq": seq,
                    "total": len(chunks),
                    "data": chunk,
                })
            except Exception:
                return False
        return True


class ApiGatewayManagementSender:
    """Sends messages via API Gateway Management API (production Lambda).

    Uses boto3 apigatewaymanagementapi client to push messages to
    connected WebSocket clients.
    """

    def __init__(self, connection_id: str, endpoint_url: str, region: str = "us-east-1") -> None:
        self._connection_id = connection_id
        self._endpoint_url = endpoint_url
        self._region = region
        self._client = None
        self._gone = False

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "apigatewaymanagementapi",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
            )
        return self._client

    async def send(self, data: dict) -> bool:
        if self._gone:
            return False

        import asyncio

        raw = json.dumps(data)

        if len(raw) > MAX_FRAME_SIZE:
            return await self._send_chunked(raw)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._get_client().post_to_connection(
                    ConnectionId=self._connection_id,
                    Data=raw.encode("utf-8"),
                ),
            )
            return True
        except Exception as e:
            error_code = getattr(getattr(e, "response", {}), "get", lambda *a: None)
            if error_code is None:
                # Check if it's a GoneException
                err_resp = getattr(e, "response", {})
                if isinstance(err_resp, dict) and err_resp.get("Error", {}).get("Code") == "GoneException":
                    self._gone = True
                    logger.info("Connection %s is gone", self._connection_id)
                    return False
            logger.warning("Failed to send to connection %s: %s", self._connection_id, e)
            return False

    async def _send_chunked(self, raw: str) -> bool:
        chunk_id = str(uuid.uuid4())[:8]
        chunks = [raw[i:i + MAX_FRAME_SIZE] for i in range(0, len(raw), MAX_FRAME_SIZE)]
        for seq, chunk in enumerate(chunks):
            ok = await self.send({
                "type": "chunk",
                "chunk_id": chunk_id,
                "seq": seq,
                "total": len(chunks),
                "data": chunk,
            })
            if not ok:
                return False
        return True
