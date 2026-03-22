"""Session repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from backend.models import Session


class SessionRepository(ABC):
    """Abstract session repository interface."""

    @abstractmethod
    async def list(self, user_id: str) -> list[Session]:
        """List all sessions for a user."""
        pass

    @abstractmethod
    async def get(self, user_id: str, session_id: str) -> Session | None:
        """Get a session by user_id and session_id, or None if not found."""
        pass

    @abstractmethod
    async def create(self, session: Session) -> None:
        """Create a new session."""
        pass

    @abstractmethod
    async def update(self, session: Session) -> None:
        """Update an existing session."""
        pass

    @abstractmethod
    async def delete(self, user_id: str, session_id: str) -> None:
        """Delete a session."""
        pass


class DynamoDBSessionRepository(SessionRepository):
    """DynamoDB session storage. Stores metadata only; transcript is on S3."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, session: Session) -> dict:
        return {
            "user_id": session.user_id,
            "session_id": session.session_id,
            "title": session.title,
            "type": session.type,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": session.message_count,
            "summary": session.summary,
        }

    def _deserialize(self, item: dict) -> Session:
        created = datetime.fromisoformat(item["created_at"])
        updated = datetime.fromisoformat(item["updated_at"])
        # Ensure timezone-aware for consistent sorting
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)
        return Session(
            user_id=item["user_id"],
            session_id=item["session_id"],
            title=item.get("title", ""),
            type=item.get("type", "chat"),
            created_at=created,
            updated_at=updated,
            message_count=int(item.get("message_count", 0)),
            summary=item.get("summary", ""),
        )

    async def list(self, user_id: str) -> list[Session]:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                self.table.query,
                KeyConditionExpression=Key("user_id").eq(user_id),
            ),
        )
        return [self._deserialize(item) for item in response.get("Items", [])]

    async def get(self, user_id: str, session_id: str) -> Session | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.table.get_item,
                    Key={"user_id": user_id, "session_id": session_id},
                ),
            )
            item = response.get("Item")
            return self._deserialize(item) if item else None
        except ClientError:
            return None

    async def create(self, session: Session) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(session)),
        )

    async def update(self, session: Session) -> None:
        session.updated_at = datetime.now(UTC)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(session)),
        )

    async def delete(self, user_id: str, session_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.delete_item,
                Key={"user_id": user_id, "session_id": session_id},
            ),
        )


class MemorySessionRepository(SessionRepository):
    """In-memory session storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._sessions: dict[tuple[str, str], Session] = {}
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            if path.exists():
                data = json.loads(path.read_text())
                for item in data:
                    s = Session.model_validate(item)
                    self._sessions[(s.user_id, s.session_id)] = s
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump(mode="json") for s in self._sessions.values()]
        path.write_text(json.dumps(data, default=str))

    async def list(self, user_id: str) -> list[Session]:
        return [s for (uid, _), s in self._sessions.items() if uid == user_id]

    async def get(self, user_id: str, session_id: str) -> Session | None:
        return self._sessions.get((user_id, session_id))

    async def create(self, session: Session) -> None:
        self._sessions[(session.user_id, session.session_id)] = session
        self._save()

    async def update(self, session: Session) -> None:
        session.updated_at = datetime.now(UTC)
        self._sessions[(session.user_id, session.session_id)] = session
        self._save()

    async def delete(self, user_id: str, session_id: str) -> None:
        self._sessions.pop((user_id, session_id), None)
        self._save()
