"""Collab repositories - abstract base, DynamoDB, and in-memory implementations."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.models import Collaboration, CollabComment, CollabInterest

logger = logging.getLogger(__name__)


class CollabRepository(ABC):
    """Abstract collaboration repository interface."""

    @abstractmethod
    async def list(self, status: str | None = None, department: str | None = None, limit: int = 50) -> list[Collaboration]:
        """List collaborations, optionally filtered by status and/or department."""
        pass

    @abstractmethod
    async def get(self, collab_id: str) -> Collaboration | None:
        """Get a collaboration by ID, or None if not found."""
        pass

    @abstractmethod
    async def create(self, collab: Collaboration) -> Collaboration:
        """Create a new collaboration."""
        pass

    @abstractmethod
    async def update(self, collab_id: str, fields: dict) -> Collaboration | None:
        """Update collab fields. Returns updated collab, or None if not found."""
        pass

    @abstractmethod
    async def delete(self, collab_id: str) -> None:
        """Soft-delete a collaboration by setting status=archived."""
        pass

    @abstractmethod
    async def express_interest(self, collab_id: str, user_id: str, message: str = "") -> bool:
        """Express interest in a collaboration. Returns False if already interested."""
        pass

    @abstractmethod
    async def withdraw_interest(self, collab_id: str, user_id: str) -> bool:
        """Withdraw interest. Returns True if interest was removed."""
        pass

    @abstractmethod
    async def get_user_interests(self, user_id: str, collab_ids: list[str]) -> set[str]:
        """Batch check which collabs the user has expressed interest in. Returns set of collab_ids."""
        pass

    @abstractmethod
    async def list_comments(self, collab_id: str) -> list[CollabComment]:
        """List comments for a collaboration in chronological order."""
        pass

    @abstractmethod
    async def add_comment(self, comment: CollabComment) -> CollabComment:
        """Add a comment to a collaboration."""
        pass

    @abstractmethod
    async def delete_comment(self, collab_id: str, comment_id: str) -> None:
        """Delete a comment."""
        pass


class DynamoDBCollabRepository(CollabRepository):
    """DynamoDB collab storage. Collabs PK=collab_id, Interests PK=collab_id+SK=user_id, Comments PK=collab_id+SK=comment_id."""

    def __init__(self, collabs_table_name: str, interests_table_name: str, comments_table_name: str, region: str = "us-east-1") -> None:
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.collabs_table = self.dynamodb.Table(collabs_table_name)
        self.interests_table = self.dynamodb.Table(interests_table_name)
        self.comments_table = self.dynamodb.Table(comments_table_name)

    def _serialize_collab(self, collab: Collaboration) -> dict:
        d = {
            "collab_id": collab.collab_id,
            "author_id": collab.author_id,
            "department": collab.department,
            "title": collab.title,
            "problem": collab.problem,
            "needed_skills": collab.needed_skills,
            "time_commitment": collab.time_commitment,
            "status": collab.status,
            "comment_count": collab.comment_count,
            "tags": collab.tags,
            "created_at": collab.created_at.isoformat(),
            "updated_at": collab.updated_at.isoformat(),
        }
        if collab.business_value:
            d["business_value"] = collab.business_value
        return d

    def _deserialize_collab(self, item: dict) -> Collaboration:
        return Collaboration(
            collab_id=item["collab_id"],
            author_id=item["author_id"],
            department=item.get("department", ""),
            title=item.get("title", ""),
            problem=item.get("problem", ""),
            needed_skills=list(item.get("needed_skills", [])),
            time_commitment=item.get("time_commitment", ""),
            status=item.get("status", "open"),
            interested_ids=[],  # populated by API route from interests table
            comment_count=int(item.get("comment_count", 0)),
            business_value=item.get("business_value", ""),
            tags=list(item.get("tags", [])),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item.get("updated_at", item["created_at"])),
        )

    def _serialize_comment(self, comment: CollabComment) -> dict:
        return {
            "collab_id": comment.collab_id,
            "comment_id": comment.comment_id,
            "author_id": comment.author_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }

    def _deserialize_comment(self, item: dict) -> CollabComment:
        return CollabComment(
            collab_id=item["collab_id"],
            comment_id=item["comment_id"],
            author_id=item["author_id"],
            content=item["content"],
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    async def list(self, status: str | None = None, department: str | None = None, limit: int = 50) -> list[Collaboration]:
        """Scan all collabs, filter by status/department in Python, sort by created_at descending.

        Note: DynamoDB scan returns max 1MB per call. At ~5-10KB per collab this
        handles ~100-200 collabs per scan. For 700 employees this is plenty.
        If the table grows past ~200 collabs, add LastEvaluatedKey pagination.
        """
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.collabs_table.scan),
            )
            collabs = [self._deserialize_collab(item) for item in response.get("Items", [])]
        except ClientError:
            logger.error("Failed to scan collabs table", exc_info=True)
            return []

        if status:
            collabs = [c for c in collabs if c.status == status]

        if department:
            dept_lower = department.lower()
            collabs = [c for c in collabs if c.department.lower() == dept_lower or c.department.lower() in ("everyone", "all", "")]

        collabs.sort(key=lambda c: c.created_at, reverse=True)
        return collabs[:limit]

    async def get(self, collab_id: str) -> Collaboration | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.collabs_table.get_item, Key={"collab_id": collab_id}),
            )
            item = response.get("Item")
            return self._deserialize_collab(item) if item else None
        except ClientError:
            return None

    async def create(self, collab: Collaboration) -> Collaboration:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.collabs_table.put_item, Item=self._serialize_collab(collab)),
        )
        return collab

    async def update(self, collab_id: str, fields: dict) -> Collaboration | None:
        allowed = {"title", "problem", "needed_skills", "time_commitment", "tags", "status", "business_value"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get(collab_id)

        # Always bump updated_at on any field change
        updates["updated_at"] = datetime.now(UTC).isoformat()

        expr_parts = []
        attr_names = {}
        attr_values = {}
        for i, (key, val) in enumerate(updates.items()):
            placeholder = f":v{i}"
            name_placeholder = f"#k{i}"
            expr_parts.append(f"{name_placeholder} = {placeholder}")
            attr_names[name_placeholder] = key
            attr_values[placeholder] = val
        update_expr = "SET " + ", ".join(expr_parts)

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.collabs_table.update_item,
                    Key={"collab_id": collab_id},
                    UpdateExpression=update_expr,
                    ConditionExpression="attribute_exists(collab_id)",
                    ExpressionAttributeNames=attr_names,
                    ExpressionAttributeValues=attr_values,
                    ReturnValues="ALL_NEW",
                ),
            )
            item = response.get("Attributes")
            return self._deserialize_collab(item) if item else None
        except ClientError:
            logger.error("Failed to update collab %s", collab_id, exc_info=True)
            return None

    async def delete(self, collab_id: str) -> None:
        """Soft-delete by setting status=archived."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.collabs_table.update_item,
                    Key={"collab_id": collab_id},
                    UpdateExpression="SET #s = :archived, #u = :now",
                    ExpressionAttributeNames={"#s": "status", "#u": "updated_at"},
                    ExpressionAttributeValues={
                        ":archived": "archived",
                        ":now": datetime.now(UTC).isoformat(),
                    },
                ),
            )
        except ClientError:
            logger.error("Failed to archive collab %s", collab_id, exc_info=True)

    async def express_interest(self, collab_id: str, user_id: str, message: str = "") -> bool:
        """Put interest with condition to prevent duplicates."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.interests_table.put_item,
                    Item={
                        "collab_id": collab_id,
                        "user_id": user_id,
                        "message": message,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    ConditionExpression="attribute_not_exists(collab_id) AND attribute_not_exists(user_id)",
                ),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    async def withdraw_interest(self, collab_id: str, user_id: str) -> bool:
        """Delete interest record."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.interests_table.delete_item,
                    Key={"collab_id": collab_id, "user_id": user_id},
                    ReturnValues="ALL_OLD",
                ),
            )
            return bool(response.get("Attributes"))
        except ClientError:
            return False

    async def get_user_interests(self, user_id: str, collab_ids: list[str]) -> set[str]:
        """Batch check which collabs the user has expressed interest in."""
        if not collab_ids:
            return set()

        loop = asyncio.get_event_loop()
        interested = set()
        for collab_id in collab_ids:
            try:
                response = await loop.run_in_executor(
                    None,
                    partial(
                        self.interests_table.get_item,
                        Key={"collab_id": collab_id, "user_id": user_id},
                    ),
                )
                if response.get("Item"):
                    interested.add(collab_id)
            except ClientError:
                pass
        return interested

    async def list_comments(self, collab_id: str) -> list[CollabComment]:
        """Query comments for a collab in chronological order."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.comments_table.query,
                    KeyConditionExpression="collab_id = :cid",
                    ExpressionAttributeValues={":cid": collab_id},
                    ScanIndexForward=True,
                ),
            )
            return [self._deserialize_comment(item) for item in response.get("Items", [])]
        except ClientError:
            return []

    async def add_comment(self, comment: CollabComment) -> CollabComment:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.comments_table.put_item, Item=self._serialize_comment(comment)),
        )
        # Atomic increment comment_count on the collab
        await loop.run_in_executor(
            None,
            partial(
                self.collabs_table.update_item,
                Key={"collab_id": comment.collab_id},
                UpdateExpression="ADD comment_count :one",
                ExpressionAttributeValues={":one": 1},
            ),
        )
        return comment

    async def delete_comment(self, collab_id: str, comment_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.comments_table.delete_item, Key={"collab_id": collab_id, "comment_id": comment_id}),
        )
        # Atomic decrement comment_count, but never below zero
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.collabs_table.update_item,
                    Key={"collab_id": collab_id},
                    UpdateExpression="ADD comment_count :neg_one",
                    ConditionExpression="comment_count > :zero",
                    ExpressionAttributeValues={":neg_one": -1, ":zero": 0},
                ),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise


class MemoryCollabRepository(CollabRepository):
    """In-memory collab storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._collabs: dict[str, Collaboration] = {}
        self._interests: set[tuple[str, str]] = set()  # (collab_id, user_id)
        self._interest_messages: dict[tuple[str, str], str] = {}
        self._comments: dict[str, list[CollabComment]] = {}
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            if path.exists():
                data = json.loads(path.read_text())
                for item in data.get("collabs", []):
                    c = Collaboration.model_validate(item)
                    self._collabs[c.collab_id] = c
                for pair in data.get("interests", []):
                    self._interests.add((pair[0], pair[1]))
                    if len(pair) > 2:
                        self._interest_messages[(pair[0], pair[1])] = pair[2]
                for collab_id, comment_list in data.get("comments", {}).items():
                    self._comments[collab_id] = [
                        CollabComment.model_validate(c) for c in comment_list
                    ]
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "collabs": [c.model_dump(mode="json") for c in self._collabs.values()],
            "interests": [
                [cid, uid, self._interest_messages.get((cid, uid), "")]
                for cid, uid in self._interests
            ],
            "comments": {
                collab_id: [c.model_dump(mode="json") for c in comments]
                for collab_id, comments in self._comments.items()
            },
        }
        path.write_text(json.dumps(data, default=str))

    async def list(self, status: str | None = None, department: str | None = None, limit: int = 50) -> list[Collaboration]:
        collabs = list(self._collabs.values())
        if status:
            collabs = [c for c in collabs if c.status == status]
        if department:
            dept_lower = department.lower()
            collabs = [c for c in collabs if c.department.lower() == dept_lower or c.department.lower() in ("everyone", "all", "")]
        collabs.sort(key=lambda c: c.created_at, reverse=True)
        return collabs[:limit]

    async def get(self, collab_id: str) -> Collaboration | None:
        return self._collabs.get(collab_id)

    async def create(self, collab: Collaboration) -> Collaboration:
        self._collabs[collab.collab_id] = collab
        self._save()
        return collab

    async def update(self, collab_id: str, fields: dict) -> Collaboration | None:
        collab = self._collabs.get(collab_id)
        if collab is None:
            return None
        allowed = {"title", "problem", "needed_skills", "time_commitment", "tags", "status", "business_value"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            updates["updated_at"] = datetime.now(UTC)
            self._collabs[collab_id] = collab.model_copy(update=updates)
            self._save()
        return self._collabs[collab_id]

    async def delete(self, collab_id: str) -> None:
        """Soft-delete by setting status=archived."""
        collab = self._collabs.get(collab_id)
        if collab:
            self._collabs[collab_id] = collab.model_copy(update={
                "status": "archived",
                "updated_at": datetime.now(UTC),
            })
            self._save()

    async def express_interest(self, collab_id: str, user_id: str, message: str = "") -> bool:
        key = (collab_id, user_id)
        if key in self._interests:
            return False
        self._interests.add(key)
        self._interest_messages[key] = message
        self._save()
        return True

    async def withdraw_interest(self, collab_id: str, user_id: str) -> bool:
        key = (collab_id, user_id)
        if key not in self._interests:
            return False
        self._interests.discard(key)
        self._interest_messages.pop(key, None)
        self._save()
        return True

    async def get_user_interests(self, user_id: str, collab_ids: list[str]) -> set[str]:
        return {cid for cid in collab_ids if (cid, user_id) in self._interests}

    async def list_comments(self, collab_id: str) -> list[CollabComment]:
        return list(self._comments.get(collab_id, []))

    async def add_comment(self, comment: CollabComment) -> CollabComment:
        if comment.collab_id not in self._comments:
            self._comments[comment.collab_id] = []
        self._comments[comment.collab_id].append(comment)
        collab = self._collabs.get(comment.collab_id)
        if collab:
            self._collabs[comment.collab_id] = collab.model_copy(update={"comment_count": collab.comment_count + 1})
        self._save()
        return comment

    async def delete_comment(self, collab_id: str, comment_id: str) -> None:
        if collab_id in self._comments:
            self._comments[collab_id] = [c for c in self._comments[collab_id] if c.comment_id != comment_id]
            collab = self._collabs.get(collab_id)
            if collab:
                self._collabs[collab_id] = collab.model_copy(update={"comment_count": max(0, collab.comment_count - 1)})
            self._save()
