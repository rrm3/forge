"""Profile repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial

import boto3
from botocore.exceptions import ClientError

from backend.models import UserProfile


class ProfileRepository(ABC):
    """Abstract profile repository interface."""

    @abstractmethod
    async def get(self, user_id: str) -> UserProfile | None:
        """Get a user's profile, or None if not found."""
        pass

    @abstractmethod
    async def create(self, profile: UserProfile) -> None:
        """Create a new profile."""
        pass

    @abstractmethod
    async def update(self, user_id: str, fields: dict) -> None:
        """Update specific fields on a profile."""
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> None:
        """Delete a profile."""
        pass


class DynamoDBProfileRepository(ProfileRepository):
    """DynamoDB profile storage. One item per user (PK=user_id)."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, profile: UserProfile) -> dict:
        return {
            "user_id": profile.user_id,
            "email": profile.email,
            "name": profile.name,
            "title": profile.title,
            "department": profile.department,
            "manager": profile.manager,
            "direct_reports": profile.direct_reports,
            "team": profile.team,
            "ai_experience_level": profile.ai_experience_level,
            "interests": profile.interests,
            "tools_used": profile.tools_used,
            "goals": profile.goals,
            "onboarding_complete": profile.onboarding_complete,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }

    def _deserialize(self, item: dict) -> UserProfile:
        return UserProfile(
            user_id=item["user_id"],
            email=item.get("email", ""),
            name=item.get("name", ""),
            title=item.get("title", ""),
            department=item.get("department", ""),
            manager=item.get("manager", ""),
            direct_reports=list(item.get("direct_reports", [])),
            team=item.get("team", ""),
            ai_experience_level=item.get("ai_experience_level", ""),
            interests=list(item.get("interests", [])),
            tools_used=list(item.get("tools_used", [])),
            goals=list(item.get("goals", [])),
            onboarding_complete=bool(item.get("onboarding_complete", False)),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    async def get(self, user_id: str) -> UserProfile | None:
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(self.table.get_item, Key={"user_id": user_id}),
            )
            item = response.get("Item")
            return self._deserialize(item) if item else None
        except ClientError:
            return None

    async def create(self, profile: UserProfile) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.put_item, Item=self._serialize(profile)),
        )

    async def update(self, user_id: str, fields: dict) -> None:
        """Update specific fields. Automatically sets updated_at."""
        fields["updated_at"] = datetime.now(UTC).isoformat()

        set_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        expr_names = {f"#{k}": k for k in fields}
        expr_values = {f":{k}": v for k, v in fields.items()}

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self.table.update_item,
                Key={"user_id": user_id},
                UpdateExpression=set_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            ),
        )

    async def delete(self, user_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.delete_item, Key={"user_id": user_id}),
        )


class MemoryProfileRepository(ProfileRepository):
    """In-memory profile storage for local dev and tests."""

    def __init__(self) -> None:
        self._profiles: dict[str, UserProfile] = {}

    async def get(self, user_id: str) -> UserProfile | None:
        return self._profiles.get(user_id)

    async def create(self, profile: UserProfile) -> None:
        self._profiles[profile.user_id] = profile

    async def update(self, user_id: str, fields: dict) -> None:
        profile = self._profiles.get(user_id)
        if profile is None:
            return
        updated = profile.model_copy(
            update={**fields, "updated_at": datetime.now(UTC)}
        )
        self._profiles[user_id] = updated

    async def delete(self, user_id: str) -> None:
        self._profiles.pop(user_id, None)
