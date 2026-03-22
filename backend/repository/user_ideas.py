"""User Ideas repositories - abstract base, DynamoDB, and in-memory implementations."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.models import UserIdea


class UserIdeaRepository(ABC):
    """Abstract user idea repository interface."""

    @abstractmethod
    async def list(self, user_id: str, limit: int = 50) -> list[UserIdea]:
        """List user's ideas, sorted by updated_at desc."""
        pass

    @abstractmethod
    async def get(self, user_id: str, idea_id: str) -> UserIdea | None:
        """Get a single idea by user_id and idea_id."""
        pass

    @abstractmethod
    async def create(self, idea: UserIdea) -> None:
        """Create a new idea."""
        pass

    @abstractmethod
    async def update(self, user_id: str, idea_id: str, fields: dict) -> None:
        """Partial update of an idea's fields."""
        pass

    @abstractmethod
    async def delete(self, user_id: str, idea_id: str) -> None:
        """Delete an idea."""
        pass

    @abstractmethod
    async def link_session(self, user_id: str, idea_id: str, session_id: str) -> None:
        """Add a session to the idea's linked_sessions list."""
        pass


class DynamoDBUserIdeaRepository(UserIdeaRepository):
    """DynamoDB user idea storage. PK=user_id, SK=idea_id."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, idea: UserIdea) -> dict:
        data = idea.model_dump(mode="json")
        # DynamoDB doesn't handle empty strings in keys well, ensure lists are stored properly
        data["created_at"] = idea.created_at.isoformat()
        data["updated_at"] = idea.updated_at.isoformat()
        return data

    def _deserialize(self, item: dict) -> UserIdea:
        return UserIdea.model_validate(item)

    async def list(self, user_id: str, limit: int = 50) -> list[UserIdea]:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.table.query,
                    KeyConditionExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                    ScanIndexForward=False,
                ),
            )
            ideas = [self._deserialize(item) for item in response.get("Items", [])]
        except ClientError:
            return []

        # Sort by updated_at desc (DynamoDB sorts by SK, so we sort in Python)
        ideas.sort(key=lambda i: i.updated_at, reverse=True)
        return ideas[:limit]

    async def get(self, user_id: str, idea_id: str) -> UserIdea | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.table.get_item,
                    Key={"user_id": user_id, "idea_id": idea_id},
                ),
            )
            item = response.get("Item")
            return self._deserialize(item) if item else None
        except ClientError:
            return None

    async def create(self, idea: UserIdea) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(idea)),
        )

    async def update(self, user_id: str, idea_id: str, fields: dict) -> None:
        loop = asyncio.get_event_loop()
        # Build update expression dynamically
        update_parts = []
        attr_names = {}
        attr_values = {}
        for i, (key, value) in enumerate(fields.items()):
            placeholder_name = f"#k{i}"
            placeholder_value = f":v{i}"
            update_parts.append(f"{placeholder_name} = {placeholder_value}")
            attr_names[placeholder_name] = key
            attr_values[placeholder_value] = value

        if not update_parts:
            return

        update_expr = "SET " + ", ".join(update_parts)
        await loop.run_in_executor(
            None,
            partial(
                self.table.update_item,
                Key={"user_id": user_id, "idea_id": idea_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
            ),
        )

    async def delete(self, user_id: str, idea_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.delete_item,
                Key={"user_id": user_id, "idea_id": idea_id},
            ),
        )

    async def link_session(self, user_id: str, idea_id: str, session_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.update_item,
                Key={"user_id": user_id, "idea_id": idea_id},
                UpdateExpression="SET linked_sessions = list_append(if_not_exists(linked_sessions, :empty), :sess)",
                ExpressionAttributeValues={
                    ":sess": [session_id],
                    ":empty": [],
                },
            ),
        )


class MemoryUserIdeaRepository(UserIdeaRepository):
    """In-memory user idea storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._ideas: dict[tuple[str, str], UserIdea] = {}
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            if path.exists():
                data = json.loads(path.read_text())
                for item in data.get("ideas", []):
                    idea = UserIdea.model_validate(item)
                    self._ideas[(idea.user_id, idea.idea_id)] = idea
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "ideas": [idea.model_dump(mode="json") for idea in self._ideas.values()],
        }
        path.write_text(json.dumps(data, default=str))

    async def list(self, user_id: str, limit: int = 50) -> list[UserIdea]:
        ideas = [i for i in self._ideas.values() if i.user_id == user_id]
        ideas.sort(key=lambda i: i.updated_at, reverse=True)
        return ideas[:limit]

    async def get(self, user_id: str, idea_id: str) -> UserIdea | None:
        return self._ideas.get((user_id, idea_id))

    async def create(self, idea: UserIdea) -> None:
        self._ideas[(idea.user_id, idea.idea_id)] = idea
        self._save()

    async def update(self, user_id: str, idea_id: str, fields: dict) -> None:
        key = (user_id, idea_id)
        idea = self._ideas.get(key)
        if idea is None:
            return
        self._ideas[key] = idea.model_copy(update=fields)
        self._save()

    async def delete(self, user_id: str, idea_id: str) -> None:
        self._ideas.pop((user_id, idea_id), None)
        self._save()

    async def link_session(self, user_id: str, idea_id: str, session_id: str) -> None:
        key = (user_id, idea_id)
        idea = self._ideas.get(key)
        if idea is None:
            return
        if session_id not in idea.linked_sessions:
            updated_sessions = list(idea.linked_sessions) + [session_id]
            self._ideas[key] = idea.model_copy(update={"linked_sessions": updated_sessions})
            self._save()
