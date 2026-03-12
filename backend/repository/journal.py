"""Journal repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from functools import partial

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from backend.models import JournalEntry


class JournalRepository(ABC):
    """Abstract journal repository interface."""

    @abstractmethod
    async def list(
        self,
        user_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[JournalEntry]:
        """List journal entries for a user, optionally filtered by date range."""
        pass

    @abstractmethod
    async def create(self, entry: JournalEntry) -> None:
        """Create a new journal entry."""
        pass

    @abstractmethod
    async def delete(self, user_id: str, entry_id: str) -> None:
        """Delete a journal entry."""
        pass


class DynamoDBJournalRepository(JournalRepository):
    """DynamoDB journal storage. PK=user_id, SK=entry_id (ULID/timestamp-based)."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, entry: JournalEntry) -> dict:
        return {
            "user_id": entry.user_id,
            "entry_id": entry.entry_id,
            "content": entry.content,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat(),
        }

    def _deserialize(self, item: dict) -> JournalEntry:
        return JournalEntry(
            user_id=item["user_id"],
            entry_id=item["entry_id"],
            content=item["content"],
            tags=list(item.get("tags", [])),
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    async def list(
        self,
        user_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[JournalEntry]:
        loop = asyncio.get_event_loop()

        kwargs: dict = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ScanIndexForward": False,  # newest first
            "Limit": limit,
        }

        if date_from and date_to:
            kwargs["FilterExpression"] = (
                Key("created_at").between(date_from.isoformat(), date_to.isoformat())
            )
        elif date_from:
            kwargs["FilterExpression"] = Key("created_at").gte(date_from.isoformat())
        elif date_to:
            kwargs["FilterExpression"] = Key("created_at").lte(date_to.isoformat())

        try:
            response = await loop.run_in_executor(
                None,
                partial(self.table.query, **kwargs),
            )
            return [self._deserialize(item) for item in response.get("Items", [])]
        except ClientError:
            return []

    async def create(self, entry: JournalEntry) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(entry)),
        )

    async def delete(self, user_id: str, entry_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.delete_item,
                Key={"user_id": user_id, "entry_id": entry_id},
            ),
        )


class MemoryJournalRepository(JournalRepository):
    """In-memory journal storage for local dev and tests."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], JournalEntry] = {}

    async def list(
        self,
        user_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[JournalEntry]:
        entries = [e for (uid, _), e in self._entries.items() if uid == user_id]

        if date_from:
            entries = [e for e in entries if e.created_at >= date_from]
        if date_to:
            entries = [e for e in entries if e.created_at <= date_to]

        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    async def create(self, entry: JournalEntry) -> None:
        self._entries[(entry.user_id, entry.entry_id)] = entry

    async def delete(self, user_id: str, entry_id: str) -> None:
        self._entries.pop((user_id, entry_id), None)
