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
    async def get_interested_user_ids(self, collab_id: str) -> list[str]:
        """Return the list of user IDs who have expressed interest in a collab."""
        pass

    @abstractmethod
    async def get_interest_counts(self, collab_ids: list[str]) -> dict[str, int]:
        """Batch get interest counts for multiple collabs. Returns {collab_id: count}."""
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

    @abstractmethod
    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Collaboration | None:
        """Find a collab by its provenance (source_session_id + source_tool_call_id) for a given user.

        Used by the session-load endpoint to determine whether a prepared collab has already
        been published. Returns None if no match exists or on any retrieval error.
        """
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
            "interested_count": collab.interested_count,
            "comment_count": collab.comment_count,
            "tags": collab.tags,
            "created_at": collab.created_at.isoformat(),
            "updated_at": collab.updated_at.isoformat(),
        }
        if collab.business_value:
            d["business_value"] = collab.business_value
        if collab.source_session_id:
            d["source_session_id"] = collab.source_session_id
        if collab.source_tool_call_id:
            d["source_tool_call_id"] = collab.source_tool_call_id
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
            interested_count=int(item.get("interested_count", 0)),
            comment_count=int(item.get("comment_count", 0)),
            business_value=item.get("business_value", ""),
            tags=list(item.get("tags", [])),
            source_session_id=item.get("source_session_id", ""),
            source_tool_call_id=item.get("source_tool_call_id", ""),
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
        else:
            # Exclude archived by default unless explicitly requested
            collabs = [c for c in collabs if c.status != "archived"]

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
        """Put interest with condition to prevent duplicates. Atomically increments interested_count."""
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
        # Atomic increment interested_count on the collab
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.collabs_table.update_item,
                    Key={"collab_id": collab_id},
                    UpdateExpression="ADD interested_count :one",
                    ExpressionAttributeValues={":one": 1},
                ),
            )
        except ClientError:
            logger.warning("Failed to increment interested_count for %s", collab_id, exc_info=True)
        return True

    async def withdraw_interest(self, collab_id: str, user_id: str) -> bool:
        """Delete interest record. Atomically decrements interested_count."""
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
            if not response.get("Attributes"):
                return False
        except ClientError:
            return False
        # Atomic decrement interested_count, but never below zero
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.collabs_table.update_item,
                    Key={"collab_id": collab_id},
                    UpdateExpression="ADD interested_count :neg_one",
                    ConditionExpression="interested_count > :zero",
                    ExpressionAttributeValues={":neg_one": -1, ":zero": 0},
                ),
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                logger.warning("Failed to decrement interested_count for %s", collab_id, exc_info=True)
        return True

    async def get_user_interests(self, user_id: str, collab_ids: list[str]) -> set[str]:
        """Batch check which collabs the user has expressed interest in using BatchGetItem."""
        if not collab_ids:
            return set()

        loop = asyncio.get_event_loop()
        interested = set()
        table_name = self.interests_table.table_name
        # BatchGetItem supports up to 100 keys per call
        for i in range(0, len(collab_ids), 100):
            batch = collab_ids[i:i + 100]
            keys = [{"collab_id": cid, "user_id": user_id} for cid in batch]
            try:
                response = await loop.run_in_executor(
                    None,
                    partial(
                        self.dynamodb.meta.client.batch_get_item,
                        RequestItems={
                            table_name: {
                                "Keys": keys,
                                "ProjectionExpression": "collab_id",
                            }
                        },
                    ),
                )
                for item in response.get("Responses", {}).get(table_name, []):
                    interested.add(item["collab_id"])
            except ClientError:
                logger.warning("BatchGetItem failed for interests", exc_info=True)
        return interested

    async def get_interested_user_ids(self, collab_id: str) -> list[str]:
        """Query the interests table for all users interested in a collab."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.interests_table.query,
                    KeyConditionExpression="collab_id = :cid",
                    ExpressionAttributeValues={":cid": collab_id},
                    ProjectionExpression="user_id",
                ),
            )
            return [item["user_id"] for item in response.get("Items", [])]
        except ClientError:
            return []

    async def get_interest_counts(self, collab_ids: list[str]) -> dict[str, int]:
        """Batch get interest counts by querying each collab's interests."""
        if not collab_ids:
            return {}

        loop = asyncio.get_event_loop()
        counts: dict[str, int] = {}
        for collab_id in collab_ids:
            try:
                response = await loop.run_in_executor(
                    None,
                    partial(
                        self.interests_table.query,
                        KeyConditionExpression="collab_id = :cid",
                        ExpressionAttributeValues={":cid": collab_id},
                        Select="COUNT",
                    ),
                )
                counts[collab_id] = response.get("Count", 0)
            except ClientError:
                counts[collab_id] = 0
        return counts

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

    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Collaboration | None:
        """Scan with a filter on author_id + source_session_id + source_tool_call_id.

        Expected to return zero or one row. Used on session load to check whether
        a prepared collab has already been published. Fails closed to None on any error.

        DynamoDB `Limit` applies to rows examined BEFORE the FilterExpression,
        not to filtered matches. Using Limit=1 here would read one random row
        and return None unless that one row happened to match — i.e., it would
        almost always miss a real published record. Instead we paginate the
        scan, apply the filter server-side, and return on the first match.
        """
        if not user_id or not session_id or not tool_call_id:
            return None
        loop = asyncio.get_event_loop()
        last_key = None
        try:
            while True:
                kwargs: dict = {
                    "FilterExpression": (
                        "author_id = :uid AND source_session_id = :sid "
                        "AND source_tool_call_id = :tcid"
                    ),
                    "ExpressionAttributeValues": {
                        ":uid": user_id,
                        ":sid": session_id,
                        ":tcid": tool_call_id,
                    },
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                response = await loop.run_in_executor(
                    None, partial(self.collabs_table.scan, **kwargs)
                )
                items = response.get("Items", [])
                if items:
                    return self._deserialize_collab(items[0])
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    return None
        except ClientError:
            logger.warning(
                "collab find_by_source scan failed user=%s session=%s tool_call=%s",
                user_id, session_id, tool_call_id, exc_info=True,
            )
            return None


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
        else:
            collabs = [c for c in collabs if c.status != "archived"]
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
        collab = self._collabs.get(collab_id)
        if collab:
            self._collabs[collab_id] = collab.model_copy(update={"interested_count": collab.interested_count + 1})
        self._save()
        return True

    async def withdraw_interest(self, collab_id: str, user_id: str) -> bool:
        key = (collab_id, user_id)
        if key not in self._interests:
            return False
        self._interests.discard(key)
        self._interest_messages.pop(key, None)
        collab = self._collabs.get(collab_id)
        if collab:
            self._collabs[collab_id] = collab.model_copy(update={"interested_count": max(0, collab.interested_count - 1)})
        self._save()
        return True

    async def get_user_interests(self, user_id: str, collab_ids: list[str]) -> set[str]:
        return {cid for cid in collab_ids if (cid, user_id) in self._interests}

    async def get_interested_user_ids(self, collab_id: str) -> list[str]:
        return [uid for cid, uid in self._interests if cid == collab_id]

    async def get_interest_counts(self, collab_ids: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cid in collab_ids:
            counts[cid] = sum(1 for c, _ in self._interests if c == cid)
        return counts

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

    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Collaboration | None:
        if not user_id or not session_id or not tool_call_id:
            return None
        for collab in self._collabs.values():
            if (
                collab.author_id == user_id
                and collab.source_session_id == session_id
                and collab.source_tool_call_id == tool_call_id
            ):
                return collab
        return None
