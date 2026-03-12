import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from backend.models import Message

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    async def read(self, key: str) -> bytes | None:
        """Return file contents, or None if the key does not exist."""

    @abstractmethod
    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Write data to key, creating intermediate paths as needed."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key. No-op if key does not exist."""

    @abstractmethod
    async def list_keys(self, prefix: str) -> list[str]:
        """Return all keys that start with prefix."""


class S3Storage(StorageBackend):
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.bucket = bucket
        self._client = boto3.client("s3", region_name=region)

    def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def read(self, key: str) -> bytes | None:
        try:
            response = await self._run(self._client.get_object, Bucket=self.bucket, Key=key)
            return await self._run(response["Body"].read)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        await self._run(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def delete(self, key: str) -> None:
        try:
            await self._run(self._client.delete_object, Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                raise

    async def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        pages = await self._run(
            paginator.paginate,
            Bucket=self.bucket,
            Prefix=prefix,
        )
        for page in pages:
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)

    def _full_path(self, key: str) -> Path:
        # Strip leading slash so Path join works correctly
        return self.base_path / key.lstrip("/")

    async def read(self, key: str) -> bytes | None:
        path = self._full_path(key)
        if not path.exists():
            return None
        return path.read_bytes()

    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def delete(self, key: str) -> None:
        path = self._full_path(key)
        if path.exists():
            path.unlink()

    async def list_keys(self, prefix: str) -> list[str]:
        search_path = self._full_path(prefix)
        # If prefix points to a directory, list everything under it.
        # If not, treat the last component as a filename prefix.
        if search_path.is_dir():
            parent = search_path
            name_prefix = ""
        else:
            parent = search_path.parent
            name_prefix = search_path.name

        if not parent.exists():
            return []

        keys: list[str] = []
        for p in sorted(parent.rglob("*")):
            if p.is_file() and p.name.startswith(name_prefix):
                relative = p.relative_to(self.base_path)
                keys.append(str(relative))
        return keys


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------

def _transcript_key(user_id: str, session_id: str) -> str:
    return f"sessions/{user_id}/{session_id}.json"


async def save_transcript(
    storage: StorageBackend,
    user_id: str,
    session_id: str,
    messages: list[Message],
) -> None:
    key = _transcript_key(user_id, session_id)
    data = json.dumps([m.model_dump(mode="json") for m in messages], default=str).encode()
    await storage.write(key, data, content_type="application/json")


async def load_transcript(
    storage: StorageBackend,
    user_id: str,
    session_id: str,
) -> list[Message] | None:
    key = _transcript_key(user_id, session_id)
    data = await storage.read(key)
    if data is None:
        return None
    raw = json.loads(data.decode())
    return [Message.model_validate(item) for item in raw]


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def _memory_key(user_id: str) -> str:
    return f"memory/{user_id}/memory.md"


async def load_memory(storage: StorageBackend, user_id: str) -> str | None:
    key = _memory_key(user_id)
    data = await storage.read(key)
    if data is None:
        return None
    return data.decode()


async def save_memory(storage: StorageBackend, user_id: str, content: str) -> None:
    key = _memory_key(user_id)
    await storage.write(key, content.encode(), content_type="text/markdown")
