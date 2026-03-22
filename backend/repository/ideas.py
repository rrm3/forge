"""Idea repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.models import Idea


class IdeaRepository(ABC):
    """Abstract idea repository interface."""

    @abstractmethod
    async def list(self, status_filter: str | None = None, limit: int = 50) -> list[Idea]:
        """List ideas, optionally filtered by status."""
        pass

    @abstractmethod
    async def get(self, idea_id: str) -> Idea | None:
        """Get an idea by ID, or None if not found."""
        pass

    @abstractmethod
    async def create(self, idea: Idea) -> None:
        """Create a new idea."""
        pass

    @abstractmethod
    async def update(self, idea_id: str, fields: dict) -> None:
        """Update specific fields on an idea."""
        pass


class DynamoDBIdeaRepository(IdeaRepository):
    """DynamoDB idea storage. PK=idea_id."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, idea: Idea) -> dict:
        return {
            "idea_id": idea.idea_id,
            "title": idea.title,
            "description": idea.description,
            "required_skills": idea.required_skills,
            "proposed_by": idea.proposed_by,
            "proposed_by_name": idea.proposed_by_name,
            "status": idea.status,
            "interested_users": idea.interested_users,
            "created_at": idea.created_at.isoformat(),
        }

    def _deserialize(self, item: dict) -> Idea:
        return Idea(
            idea_id=item["idea_id"],
            title=item["title"],
            description=item["description"],
            required_skills=list(item.get("required_skills", [])),
            proposed_by=item["proposed_by"],
            proposed_by_name=item.get("proposed_by_name", ""),
            status=item.get("status", "open"),
            interested_users=list(item.get("interested_users", [])),
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    async def list(self, status_filter: str | None = None, limit: int = 50) -> list[Idea]:
        """Scan all ideas (small table). Optionally filter by status."""
        loop = asyncio.get_event_loop()

        kwargs: dict = {"Limit": limit}
        if status_filter:
            kwargs["FilterExpression"] = "#status = :status"
            kwargs["ExpressionAttributeNames"] = {"#status": "status"}
            kwargs["ExpressionAttributeValues"] = {":status": status_filter}

        try:
            response = await loop.run_in_executor(
                None,
                partial(self.table.scan, **kwargs),
            )
            return [self._deserialize(item) for item in response.get("Items", [])]
        except ClientError:
            return []

    async def get(self, idea_id: str) -> Idea | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.table.get_item, Key={"idea_id": idea_id}),
            )
            item = response.get("Item")
            return self._deserialize(item) if item else None
        except ClientError:
            return None

    async def create(self, idea: Idea) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(idea)),
        )

    async def update(self, idea_id: str, fields: dict) -> None:
        """Update specific fields on an idea."""
        set_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        expr_names = {f"#{k}": k for k in fields}
        expr_values = {f":{k}": v for k, v in fields.items()}

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.update_item,
                Key={"idea_id": idea_id},
                UpdateExpression=set_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            ),
        )


class MemoryIdeaRepository(IdeaRepository):
    """In-memory idea storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._ideas: dict[str, Idea] = {}
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
                    idea = Idea.model_validate(item)
                    self._ideas[idea.idea_id] = idea
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [i.model_dump(mode="json") for i in self._ideas.values()]
        path.write_text(json.dumps(data, default=str))

    async def list(self, status_filter: str | None = None, limit: int = 50) -> list[Idea]:
        ideas = list(self._ideas.values())
        if status_filter:
            ideas = [i for i in ideas if i.status == status_filter]
        ideas.sort(key=lambda i: i.created_at, reverse=True)
        return ideas[:limit]

    async def get(self, idea_id: str) -> Idea | None:
        return self._ideas.get(idea_id)

    async def create(self, idea: Idea) -> None:
        self._ideas[idea.idea_id] = idea
        self._save()

    async def update(self, idea_id: str, fields: dict) -> None:
        idea = self._ideas.get(idea_id)
        if idea is None:
            return
        merged = {**idea.model_dump(), **fields}
        updated = Idea.model_validate(merged)
        self._ideas[idea_id] = updated
        self._save()
