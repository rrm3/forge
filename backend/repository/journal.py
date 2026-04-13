"""Journal repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from functools import partial
from pathlib import Path

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
        last_exc: ClientError | None = None
        for attempt in range(3):
            try:
                await loop.run_in_executor(
                    None,
                    partial(self.table.put_item, Item=self._serialize(entry)),
                )
                return
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code in (
                    "ProvisionedThroughputExceededException",
                    "ThrottlingException",
                    "InternalServerError",
                ):
                    last_exc = exc
                    await asyncio.sleep(0.5 * (2 ** attempt))
                else:
                    raise
        raise last_exc  # type: ignore[misc]

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

    def __init__(self, persist_path: str | None = None) -> None:
        self._entries: dict[tuple[str, str], JournalEntry] = {}
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
                    e = JournalEntry.model_validate(item)
                    self._entries[(e.user_id, e.entry_id)] = e
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.model_dump(mode="json") for e in self._entries.values()]
        path.write_text(json.dumps(data, default=str))

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
        self._save()

    async def delete(self, user_id: str, entry_id: str) -> None:
        self._entries.pop((user_id, entry_id), None)
        self._save()
