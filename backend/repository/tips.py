"""Tip repositories - abstract base, DynamoDB, and in-memory implementations."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.models import Tip, TipComment


class TipRepository(ABC):
    """Abstract tip repository interface."""

    @abstractmethod
    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50) -> list[Tip]:
        """List tips, optionally filtered by department."""
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


class DynamoDBTipRepository(TipRepository):
    """DynamoDB tip storage. Tips PK=tip_id, Votes PK=tip_id+SK=user_id, Comments PK=tip_id+SK=comment_id."""

    def __init__(self, tips_table_name: str, votes_table_name: str, comments_table_name: str, region: str = "us-east-1") -> None:
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.tips_table = self.dynamodb.Table(tips_table_name)
        self.votes_table = self.dynamodb.Table(votes_table_name)
        self.comments_table = self.dynamodb.Table(comments_table_name)

    def _serialize_tip(self, tip: Tip) -> dict:
        return {
            "tip_id": tip.tip_id,
            "author_id": tip.author_id,
            "author_name": tip.author_name,
            "department": tip.department,
            "title": tip.title,
            "content": tip.content,
            "tags": tip.tags,
            "vote_count": tip.vote_count,
            "created_at": tip.created_at.isoformat(),
        }

    def _deserialize_tip(self, item: dict) -> Tip:
        return Tip(
            tip_id=item["tip_id"],
            author_id=item["author_id"],
            author_name=item.get("author_name", ""),
            department=item.get("department", ""),
            title=item.get("title", ""),
            content=item["content"],
            tags=list(item.get("tags", [])),
            vote_count=int(item.get("vote_count", 0)),
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    def _serialize_comment(self, comment: TipComment) -> dict:
        return {
            "tip_id": comment.tip_id,
            "comment_id": comment.comment_id,
            "author_id": comment.author_id,
            "author_name": comment.author_name,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }

    def _deserialize_comment(self, item: dict) -> TipComment:
        return TipComment(
            tip_id=item["tip_id"],
            comment_id=item["comment_id"],
            author_id=item["author_id"],
            author_name=item.get("author_name", ""),
            content=item["content"],
            created_at=datetime.fromisoformat(item["created_at"]),
        )

    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50) -> list[Tip]:
        """Scan all tips (small table), filter by department in Python, sort in Python."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.tips_table.scan),
            )
            tips = [self._deserialize_tip(item) for item in response.get("Items", [])]
        except ClientError:
            return []

        if department:
            tips = [t for t in tips if t.department.lower() == department.lower()]

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

    async def list(self, department: str | None = None, sort_by: str = "recent", limit: int = 50) -> list[Tip]:
        tips = list(self._tips.values())
        if department:
            tips = [t for t in tips if t.department.lower() == department.lower()]
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
        self._save()
