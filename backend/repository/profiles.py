"""Profile repositories - abstract base, DynamoDB, and in-memory implementations."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

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

    @abstractmethod
    async def list_all(self) -> list[UserProfile]:
        """List all profiles (admin use only)."""
        pass


class DynamoDBProfileRepository(ProfileRepository):
    """DynamoDB profile storage. One item per user (PK=user_id)."""

    def __init__(self, table_name: str, region: str = "us-east-1") -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _serialize(self, profile: UserProfile) -> dict:
        data = {
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
            "avatar_url": profile.avatar_url,
            "location": profile.location,
            "start_date": profile.start_date,
            "work_summary": profile.work_summary,
            "onboarding_complete": profile.onboarding_complete,
            "products": profile.products,
            "daily_tasks": profile.daily_tasks,
            "core_skills": profile.core_skills,
            "learning_goals": profile.learning_goals,
            "ai_tools_used": profile.ai_tools_used,
            "ai_superpower": profile.ai_superpower,
            "ai_proficiency": profile.ai_proficiency.model_dump() if profile.ai_proficiency else None,
            "intake_summary": profile.intake_summary,
            "intake_fields_captured": profile.intake_fields_captured,
            "intake_completed_at": profile.intake_completed_at.isoformat() if profile.intake_completed_at else None,
            "is_department_admin": profile.is_department_admin,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }
        # DynamoDB doesn't support None values in items - remove them
        return {k: v for k, v in data.items() if v is not None}

    def _deserialize(self, item: dict) -> UserProfile:
        from backend.models import AIProficiency
        ai_prof = item.get("ai_proficiency")
        if isinstance(ai_prof, dict):
            ai_prof = AIProficiency(**ai_prof)
        else:
            ai_prof = None

        intake_completed = item.get("intake_completed_at")
        if isinstance(intake_completed, str):
            intake_completed = datetime.fromisoformat(intake_completed)

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
            avatar_url=item.get("avatar_url", ""),
            location=item.get("location", ""),
            start_date=item.get("start_date", ""),
            work_summary=item.get("work_summary", ""),
            onboarding_complete=bool(item.get("onboarding_complete", False)),
            products=list(item.get("products", [])),
            daily_tasks=item.get("daily_tasks", ""),
            core_skills=list(item.get("core_skills", [])),
            learning_goals=list(item.get("learning_goals", [])),
            ai_tools_used=list(item.get("ai_tools_used", [])),
            ai_superpower=item.get("ai_superpower", ""),
            ai_proficiency=ai_prof,
            intake_summary=item.get("intake_summary", ""),
            intake_fields_captured=list(item.get("intake_fields_captured", [])),
            intake_completed_at=intake_completed,
            is_department_admin=bool(item.get("is_department_admin", False)),
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
        """Update specific fields. Automatically sets updated_at.

        None values are translated to DynamoDB REMOVE expressions.
        """
        fields["updated_at"] = datetime.now(UTC).isoformat()

        # Split into SET (non-None) and REMOVE (None) fields
        set_fields = {k: v for k, v in fields.items() if v is not None}
        remove_fields = [k for k, v in fields.items() if v is None]

        parts = []
        expr_names: dict[str, str] = {}
        expr_values: dict[str, object] = {}

        if set_fields:
            parts.append("SET " + ", ".join(f"#{k} = :{k}" for k in set_fields))
            expr_names.update({f"#{k}": k for k in set_fields})
            expr_values.update({f":{k}": v for k, v in set_fields.items()})

        if remove_fields:
            parts.append("REMOVE " + ", ".join(f"#{k}" for k in remove_fields))
            expr_names.update({f"#{k}": k for k in remove_fields})

        kwargs: dict = {
            "Key": {"user_id": user_id},
            "UpdateExpression": " ".join(parts),
            "ExpressionAttributeNames": expr_names,
        }
        if expr_values:
            kwargs["ExpressionAttributeValues"] = expr_values

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.update_item, **kwargs),
        )

    async def delete(self, user_id: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self.table.delete_item, Key={"user_id": user_id}),
        )

    async def list_all(self) -> list[UserProfile]:
        loop = asyncio.get_event_loop()
        profiles = []
        last_key = None
        while True:
            kwargs: dict = {}
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            response = await loop.run_in_executor(
                None, partial(self.table.scan, **kwargs)
            )
            for item in response.get("Items", []):
                profiles.append(self._deserialize(item))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
        return profiles


class MemoryProfileRepository(ProfileRepository):
    """In-memory profile storage for local dev and tests."""

    def __init__(self, persist_path: str | None = None) -> None:
        self._profiles: dict[str, UserProfile] = {}
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
                    p = UserProfile.model_validate(item)
                    self._profiles[p.user_id] = p
        except Exception:
            pass

    def _save(self) -> None:
        if not self._persist_path:
            return
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [p.model_dump(mode="json") for p in self._profiles.values()]
        path.write_text(json.dumps(data, default=str))

    async def get(self, user_id: str) -> UserProfile | None:
        return self._profiles.get(user_id)

    async def create(self, profile: UserProfile) -> None:
        self._profiles[profile.user_id] = profile
        self._save()

    async def update(self, user_id: str, fields: dict) -> None:
        profile = self._profiles.get(user_id)
        if profile is None:
            return
        # Use model_validate on the merged dict to ensure type coercion
        # (e.g., string datetimes get parsed, dicts become nested models)
        merged = {**profile.model_dump(), **fields, "updated_at": datetime.now(UTC).isoformat()}
        updated = UserProfile.model_validate(merged)
        self._profiles[user_id] = updated
        self._save()

    async def delete(self, user_id: str) -> None:
        self._profiles.pop(user_id, None)
        self._save()

    async def list_all(self) -> list[UserProfile]:
        return list(self._profiles.values())
