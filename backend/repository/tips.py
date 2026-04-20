"""Tip repositories - abstract base, DynamoDB, and in-memory implementations."""

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

from backend.models import Tip, TipComment

logger = logging.getLogger(__name__)


class TipRepository(ABC):
    """Abstract tip repository interface."""

    @abstractmethod
    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50, category: str | None = None) -> list[Tip]:
        """List tips, optionally filtered by department and/or category."""
        pass

    @abstractmethod
    async def get(self, tip_id: str) -> Tip | None:
        """Get a tip by ID, or None if not found."""
        pass

    @abstractmethod
    async def create(self, tip: Tip) -> None:
        """Create a new tip."""
        pass

    @abstractmethod
    async def update(self, tip_id: str, fields: dict) -> Tip | None:
        """Update tip fields. Returns updated tip, or None if not found."""
        pass

    @abstractmethod
    async def delete(self, tip_id: str) -> None:
        """Delete a tip and its votes/comments."""
        pass

    @abstractmethod
    async def upvote(self, tip_id: str, user_id: str) -> bool:
        """Upvote a tip. Returns True if new vote, False if already voted."""
        pass

    @abstractmethod
    async def remove_vote(self, tip_id: str, user_id: str) -> bool:
        """Remove a vote. Returns True if vote was removed."""
        pass

    @abstractmethod
    async def get_user_votes(self, user_id: str, tip_ids: list[str]) -> set[str]:
        """Batch check which tips the user has voted on. Returns set of tip_ids."""
        pass

    @abstractmethod
    async def list_comments(self, tip_id: str) -> list[TipComment]:
        """List comments for a tip in chronological order."""
        pass

    @abstractmethod
    async def add_comment(self, comment: TipComment) -> None:
        """Add a comment to a tip."""
        pass

    @abstractmethod
    async def update_comment(self, tip_id: str, comment_id: str, content: str) -> TipComment | None:
        """Update a comment's content. Returns updated comment, or None if not found."""
        pass

    @abstractmethod
    async def delete_comment(self, tip_id: str, comment_id: str) -> None:
        """Delete a comment."""
        pass

    @abstractmethod
    async def count_by_authors(self, author_ids: list[str]) -> dict[str, int]:
        """Count tips per author. Returns {author_id: count}."""
        pass

    @abstractmethod
    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Tip | None:
        """Find a tip by its provenance (source_session_id + source_tool_call_id) for a given user.

        Used by the session-load endpoint to determine whether a prepared tip has already
        been published. Returns None if no match exists or on any retrieval error.
        """
        pass


class DynamoDBTipRepository(TipRepository):
    """DynamoDB tip storage. Tips PK=tip_id, Votes PK=tip_id+SK=user_id, Comments PK=tip_id+SK=comment_id."""

    def __init__(self, tips_table_name: str, votes_table_name: str, comments_table_name: str, region: str = "us-east-1") -> None:
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.tips_table = self.dynamodb.Table(tips_table_name)
        self.votes_table = self.dynamodb.Table(votes_table_name)
        self.comments_table = self.dynamodb.Table(comments_table_name)

    def _serialize_tip(self, tip: Tip) -> dict:
        d = {
            "tip_id": tip.tip_id,
            "author_id": tip.author_id,
            "department": tip.department,
            "title": tip.title,
            "content": tip.content,
            "tags": tip.tags,
            "category": tip.category,
            "vote_count": tip.vote_count,
            "comment_count": tip.comment_count,
            "created_at": tip.created_at.isoformat(),
        }
        if tip.summary:
            d["summary"] = tip.summary
        if tip.artifact:
            d["artifact"] = tip.artifact
        if tip.source_session_id:
            d["source_session_id"] = tip.source_session_id
        if tip.source_tool_call_id:
            d["source_tool_call_id"] = tip.source_tool_call_id
        return d

    def _deserialize_tip(self, item: dict) -> Tip:
        return Tip(
            tip_id=item["tip_id"],
            author_id=item["author_id"],
            department=item.get("department", ""),
            title=item.get("title", ""),
            content=item["content"],
            summary=item.get("summary", ""),
            tags=list(item.get("tags", [])),
            category=item.get("category", "tip"),
            artifact=item.get("artifact", ""),
            vote_count=int(item.get("vote_count", 0)),
            comment_count=int(item.get("comment_count", 0)),
            source_session_id=item.get("source_session_id", ""),
            source_tool_call_id=item.get("source_tool_call_id", ""),
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    def _serialize_comment(self, comment: TipComment) -> dict:
        return {
            "tip_id": comment.tip_id,
            "comment_id": comment.comment_id,
            "author_id": comment.author_id,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }

    def _deserialize_comment(self, item: dict) -> TipComment:
        return TipComment(
            tip_id=item["tip_id"],
            comment_id=item["comment_id"],
            author_id=item["author_id"],
            content=item["content"],
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50, category: str | None = None) -> list[Tip]:
        """Scan all tips, filter by department/category in Python, sort in Python.

        Note: DynamoDB scan returns max 1MB per call. At ~5-10KB per tip this
        handles ~100-200 tips per scan. For 700 employees this is plenty.
        If the table grows past ~200 tips, add LastEvaluatedKey pagination.
        """
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.tips_table.scan),
            )
            tips = [self._deserialize_tip(item) for item in response.get("Items", [])]
        except ClientError:
            logger.error("Failed to scan tips table", exc_info=True)
            return []

        if department:
            dept_lower = department.lower()
            tips = [t for t in tips if t.department.lower() == dept_lower or t.department.lower() in ("everyone", "all", "")]

        if category:
            tips = [t for t in tips if t.category == category]

        if sort_by == "popular":
            tips.sort(key=lambda t: t.vote_count, reverse=True)
        else:
            tips.sort(key=lambda t: t.created_at, reverse=True)

        return tips[:limit]

    async def get(self, tip_id: str) -> Tip | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.tips_table.get_item, Key={"tip_id": tip_id}),
            )
            item = response.get("Item")
            return self._deserialize_tip(item) if item else None
        except ClientError:
            return None

    async def create(self, tip: Tip) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.tips_table.put_item, Item=self._serialize_tip(tip)),
        )

    async def update(self, tip_id: str, fields: dict) -> Tip | None:
        allowed = {"title", "content", "tags", "department", "summary", "category", "artifact"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return await self.get(tip_id)

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
                    self.tips_table.update_item,
                    Key={"tip_id": tip_id},
                    UpdateExpression=update_expr,
                    ConditionExpression="attribute_exists(tip_id)",
                    ExpressionAttributeNames=attr_names,
                    ExpressionAttributeValues=attr_values,
                    ReturnValues="ALL_NEW",
                ),
            )
            item = response.get("Attributes")
            return self._deserialize_tip(item) if item else None
        except ClientError:
            logger.error("Failed to update tip %s", tip_id, exc_info=True)
            return None

    async def delete(self, tip_id: str) -> None:
        loop = asyncio.get_event_loop()
        # Delete the tip itself
        await loop.run_in_executor(
            None,
            partial(self.tips_table.delete_item, Key={"tip_id": tip_id}),
        )
        # Clean up votes for this tip
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.votes_table.query, KeyConditionExpression="tip_id = :tid",
                        ExpressionAttributeValues={":tid": tip_id}),
            )
            for item in response.get("Items", []):
                await loop.run_in_executor(
                    None,
                    partial(self.votes_table.delete_item,
                            Key={"tip_id": tip_id, "user_id": item["user_id"]}),
                )
        except ClientError:
            logger.warning("Failed to clean up votes for tip %s", tip_id, exc_info=True)
        # Clean up comments for this tip
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.comments_table.query, KeyConditionExpression="tip_id = :tid",
                        ExpressionAttributeValues={":tid": tip_id}),
            )
            for item in response.get("Items", []):
                await loop.run_in_executor(
                    None,
                    partial(self.comments_table.delete_item,
                            Key={"tip_id": tip_id, "comment_id": item["comment_id"]}),
                )
        except ClientError:
            logger.warning("Failed to clean up comments for tip %s", tip_id, exc_info=True)

    async def upvote(self, tip_id: str, user_id: str) -> bool:
        """Put vote with condition to prevent duplicates, then atomic increment."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.votes_table.put_item,
                    Item={
                        "tip_id": tip_id,
                        "user_id": user_id,
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    ConditionExpression="attribute_not_exists(tip_id) AND attribute_not_exists(user_id)",
                ),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

        # Atomic increment vote_count
        await loop.run_in_executor(
            None,
            partial(
                self.tips_table.update_item,
                Key={"tip_id": tip_id},
                UpdateExpression="ADD vote_count :one",
                ExpressionAttributeValues={":one": 1},
            ),
        )
        return True

    async def remove_vote(self, tip_id: str, user_id: str) -> bool:
        """Delete vote, then atomic decrement."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.votes_table.delete_item,
                    Key={"tip_id": tip_id, "user_id": user_id},
                ),
            )
        except ClientError:
            return False

        # Atomic decrement vote_count
        await loop.run_in_executor(
            None,
            partial(
                self.tips_table.update_item,
                Key={"tip_id": tip_id},
                UpdateExpression="ADD vote_count :neg_one",
                ExpressionAttributeValues={":neg_one": -1},
            ),
        )
        return True

    async def get_user_votes(self, user_id: str, tip_ids: list[str]) -> set[str]:
        """Batch check which tips the user has voted on."""
        if not tip_ids:
            return set()

        loop = asyncio.get_event_loop()
        voted = set()
        for tip_id in tip_ids:
            try:
                response = await loop.run_in_executor(
                    None,
                    partial(
                        self.votes_table.get_item,
                        Key={"tip_id": tip_id, "user_id": user_id},
                    ),
                )
                if response.get("Item"):
                    voted.add(tip_id)
            except ClientError:
                pass
        return voted

    async def list_comments(self, tip_id: str) -> list[TipComment]:
        """Query comments for a tip in chronological order."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.comments_table.query,
                    KeyConditionExpression="tip_id = :tid",
                    ExpressionAttributeValues={":tid": tip_id},
                    ScanIndexForward=True,
                ),
            )
            return [self._deserialize_comment(item) for item in response.get("Items", [])]
        except ClientError:
            return []

    async def add_comment(self, comment: TipComment) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.comments_table.put_item, Item=self._serialize_comment(comment)),
        )
        # Atomic increment comment_count on the tip
        await loop.run_in_executor(
            None,
            partial(
                self.tips_table.update_item,
                Key={"tip_id": comment.tip_id},
                UpdateExpression="ADD comment_count :one",
                ExpressionAttributeValues={":one": 1},
            ),
        )

    async def update_comment(self, tip_id: str, comment_id: str, content: str) -> TipComment | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self.comments_table.update_item,
                    Key={"tip_id": tip_id, "comment_id": comment_id},
                    UpdateExpression="SET content = :c",
                    ConditionExpression="attribute_exists(tip_id)",
                    ExpressionAttributeValues={":c": content},
                    ReturnValues="ALL_NEW",
                ),
            )
            item = response.get("Attributes")
            return self._deserialize_comment(item) if item else None
        except ClientError:
            logger.error("Failed to update comment %s on tip %s", comment_id, tip_id, exc_info=True)
            return None

    async def delete_comment(self, tip_id: str, comment_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.comments_table.delete_item, Key={"tip_id": tip_id, "comment_id": comment_id}),
        )
        # Atomic decrement comment_count, but never below zero
        try:
            await loop.run_in_executor(
                None,
                partial(
                    self.tips_table.update_item,
                    Key={"tip_id": tip_id},
                    UpdateExpression="ADD comment_count :neg_one",
                    ConditionExpression="comment_count > :zero",
                    ExpressionAttributeValues={":neg_one": -1, ":zero": 0},
                ),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    async def count_by_authors(self, author_ids: list[str]) -> dict[str, int]:
        if not author_ids:
            return {}
        loop = asyncio.get_event_loop()
        counts: dict[str, int] = {}
        last_key = None
        author_set = set(author_ids)
        while True:
            kwargs: dict = {"ProjectionExpression": "author_id"}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            response = await loop.run_in_executor(
                None, partial(self.tips_table.scan, **kwargs)
            )
            for item in response.get("Items", []):
                aid = item.get("author_id", "")
                if aid in author_set:
                    counts[aid] = counts.get(aid, 0) + 1
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
        return counts

    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Tip | None:
        """Scan with a filter on author_id + source_session_id + source_tool_call_id.

        Expected to return zero or one row. Used on session load to check whether
        a prepared tip has already been published. Fails closed to None on any error.

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
                    None, partial(self.tips_table.scan, **kwargs)
                )
                items = response.get("Items", [])
                if items:
                    return self._deserialize_tip(items[0])
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    return None
        except ClientError:
            logger.warning(
                "find_by_source scan failed user=%s session=%s tool_call=%s",
                user_id, session_id, tool_call_id, exc_info=True,
            )
            return None


class MemoryTipRepository(TipRepository):
    """In-memory tip storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._tips: dict[str, Tip] = {}
        self._votes: set[tuple[str, str]] = set()
        self._comments: dict[str, list[TipComment]] = {}
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            path = Path(self._persist_path)
            if path.exists():
                data = json.loads(path.read_text())
                for item in data.get("tips", []):
                    t = Tip.model_validate(item)
                    self._tips[t.tip_id] = t
                for pair in data.get("votes", []):
                    self._votes.add((pair[0], pair[1]))
                for tip_id, comment_list in data.get("comments", {}).items():
                    self._comments[tip_id] = [
                        TipComment.model_validate(c) for c in comment_list
                    ]
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tips": [t.model_dump(mode="json") for t in self._tips.values()],
            "votes": [[tid, uid] for tid, uid in self._votes],
            "comments": {
                tip_id: [c.model_dump(mode="json") for c in comments]
                for tip_id, comments in self._comments.items()
            },
        }
        path.write_text(json.dumps(data, default=str))

    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50, category: str | None = None) -> list[Tip]:
        tips = list(self._tips.values())
        if department:
            dept_lower = department.lower()
            tips = [t for t in tips if t.department.lower() == dept_lower or t.department.lower() in ("everyone", "all", "")]
        if category:
            tips = [t for t in tips if t.category == category]
        if sort_by == "popular":
            tips.sort(key=lambda t: t.vote_count, reverse=True)
        else:
            tips.sort(key=lambda t: t.created_at, reverse=True)
        return tips[:limit]

    async def get(self, tip_id: str) -> Tip | None:
        return self._tips.get(tip_id)

    async def create(self, tip: Tip) -> None:
        self._tips[tip.tip_id] = tip
        self._save()

    async def update(self, tip_id: str, fields: dict) -> Tip | None:
        tip = self._tips.get(tip_id)
        if tip is None:
            return None
        allowed = {"title", "content", "tags", "department", "summary", "category", "artifact"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            self._tips[tip_id] = tip.model_copy(update=updates)
            self._save()
        return self._tips[tip_id]

    async def delete(self, tip_id: str) -> None:
        self._tips.pop(tip_id, None)
        self._votes = {(tid, uid) for tid, uid in self._votes if tid != tip_id}
        self._comments.pop(tip_id, None)
        self._save()

    async def upvote(self, tip_id: str, user_id: str) -> bool:
        key = (tip_id, user_id)
        if key in self._votes:
            return False
        self._votes.add(key)
        tip = self._tips.get(tip_id)
        if tip:
            self._tips[tip_id] = tip.model_copy(update={"vote_count": tip.vote_count + 1})
        self._save()
        return True

    async def remove_vote(self, tip_id: str, user_id: str) -> bool:
        key = (tip_id, user_id)
        if key not in self._votes:
            return False
        self._votes.discard(key)
        tip = self._tips.get(tip_id)
        if tip:
            self._tips[tip_id] = tip.model_copy(update={"vote_count": max(0, tip.vote_count - 1)})
        self._save()
        return True

    async def get_user_votes(self, user_id: str, tip_ids: list[str]) -> set[str]:
        return {tid for tid in tip_ids if (tid, user_id) in self._votes}

    async def list_comments(self, tip_id: str) -> list[TipComment]:
        return list(self._comments.get(tip_id, []))

    async def add_comment(self, comment: TipComment) -> None:
        if comment.tip_id not in self._comments:
            self._comments[comment.tip_id] = []
        self._comments[comment.tip_id].append(comment)
        tip = self._tips.get(comment.tip_id)
        if tip:
            self._tips[comment.tip_id] = tip.model_copy(update={"comment_count": tip.comment_count + 1})
        self._save()

    async def update_comment(self, tip_id: str, comment_id: str, content: str) -> TipComment | None:
        for i, c in enumerate(self._comments.get(tip_id, [])):
            if c.comment_id == comment_id:
                updated = c.model_copy(update={"content": content})
                self._comments[tip_id][i] = updated
                self._save()
                return updated
        return None

    async def delete_comment(self, tip_id: str, comment_id: str) -> None:
        if tip_id in self._comments:
            self._comments[tip_id] = [c for c in self._comments[tip_id] if c.comment_id != comment_id]
            tip = self._tips.get(tip_id)
            if tip:
                self._tips[tip_id] = tip.model_copy(update={"comment_count": max(0, tip.comment_count - 1)})
            self._save()

    async def count_by_authors(self, author_ids: list[str]) -> dict[str, int]:
        if not author_ids:
            return {}
        author_set = set(author_ids)
        counts: dict[str, int] = {}
        for tip in self._tips.values():
            if tip.author_id in author_set:
                counts[tip.author_id] = counts.get(tip.author_id, 0) + 1
        return counts

    async def find_by_source(self, user_id: str, session_id: str, tool_call_id: str) -> Tip | None:
        if not user_id or not session_id or not tool_call_id:
            return None
        for tip in self._tips.values():
            if (
                tip.author_id == user_id
                and tip.source_session_id == session_id
                and tip.source_tool_call_id == tool_call_id
            ):
                return tip
        return None
