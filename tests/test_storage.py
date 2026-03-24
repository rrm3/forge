"""Tests for LocalStorage and the transcript/memory helpers."""
import pytest

from backend.models import Message
from backend.storage import (
    LocalStorage,
    load_memory,
    load_transcript,
    save_memory,
    save_transcript,
)


# ---------------------------------------------------------------------------
# LocalStorage
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return LocalStorage(tmp_path)


@pytest.mark.asyncio
async def test_write_and_read(store):
    await store.write("foo/bar.txt", b"hello")
    result = await store.read("foo/bar.txt")
    assert result == b"hello"


@pytest.mark.asyncio
async def test_read_missing_returns_none(store):
    assert await store.read("does/not/exist.txt") is None


@pytest.mark.asyncio
async def test_write_creates_intermediate_dirs(store, tmp_path):
    await store.write("a/b/c/file.bin", b"\x00\x01")
    assert (tmp_path / "a" / "b" / "c" / "file.bin").exists()


@pytest.mark.asyncio
async def test_delete_existing(store):
    await store.write("to_delete.txt", b"bye")
    await store.delete("to_delete.txt")
    assert await store.read("to_delete.txt") is None


@pytest.mark.asyncio
async def test_delete_missing_is_noop(store):
    # Should not raise
    await store.delete("never/existed.txt")


@pytest.mark.asyncio
async def test_list_keys_by_directory_prefix(store):
    await store.write("sessions/user1/a.json", b"1")
    await store.write("sessions/user1/b.json", b"2")
    await store.write("sessions/user2/c.json", b"3")

    keys = await store.list_keys("sessions/user1")
    assert sorted(keys) == ["sessions/user1/a.json", "sessions/user1/b.json"]


@pytest.mark.asyncio
async def test_list_keys_by_filename_prefix(store):
    await store.write("data/alpha.txt", b"a")
    await store.write("data/alpha2.txt", b"aa")
    await store.write("data/beta.txt", b"b")

    keys = await store.list_keys("data/alpha")
    assert sorted(keys) == ["data/alpha.txt", "data/alpha2.txt"]


@pytest.mark.asyncio
async def test_list_keys_empty_prefix(store):
    assert await store.list_keys("nonexistent/") == []


@pytest.mark.asyncio
async def test_overwrite(store):
    await store.write("key.txt", b"v1")
    await store.write("key.txt", b"v2")
    assert await store.read("key.txt") == b"v2"


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------


def _make_messages():
    return [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there"),
    ]


@pytest.mark.asyncio
async def test_save_and_load_transcript(store):
    messages = _make_messages()
    await save_transcript(store, "u1", "s1", messages)
    loaded = await load_transcript(store, "u1", "s1")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].role == "user"
    assert loaded[0].content == "Hello"
    assert loaded[1].role == "assistant"


@pytest.mark.asyncio
async def test_load_transcript_missing_returns_none(store):
    result = await load_transcript(store, "u1", "no_such_session")
    assert result is None


@pytest.mark.asyncio
async def test_transcript_stored_at_correct_key(store, tmp_path):
    await save_transcript(store, "user42", "sess99", _make_messages())
    expected = tmp_path / "sessions" / "user42" / "sess99.json"
    assert expected.exists()


@pytest.mark.asyncio
async def test_transcript_roundtrip_preserves_tool_fields(store):
    messages = [
        Message(role="tool_call", content='{"name":"search_internal"}', tool_name="search_internal", tool_call_id="tc1"),
        Message(role="tool_result", content="results here", tool_call_id="tc1"),
    ]
    await save_transcript(store, "u2", "s2", messages)
    loaded = await load_transcript(store, "u2", "s2")
    assert loaded[0].tool_name == "search_internal"
    assert loaded[0].tool_call_id == "tc1"
    assert loaded[1].tool_call_id == "tc1"


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_load_memory(store):
    await save_memory(store, "u1", "# My notes\n\nSome content.")
    content = await load_memory(store, "u1")
    assert content == "# My notes\n\nSome content."


@pytest.mark.asyncio
async def test_load_memory_missing_returns_none(store):
    result = await load_memory(store, "no_such_user")
    assert result is None


@pytest.mark.asyncio
async def test_memory_stored_at_correct_key(store, tmp_path):
    await save_memory(store, "userXYZ", "hello")
    expected = tmp_path / "memory" / "userXYZ" / "memory.md"
    assert expected.exists()


@pytest.mark.asyncio
async def test_overwrite_memory(store):
    await save_memory(store, "u3", "v1")
    await save_memory(store, "u3", "v2")
    content = await load_memory(store, "u3")
    assert content == "v2"
