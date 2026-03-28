"""Journal tools: save and read learning journal entries."""

import logging
import uuid
from datetime import datetime, timezone

from backend.models import JournalEntry
from backend.tools.registry import ToolContext

logger = logging.getLogger(__name__)

SAVE_JOURNAL_SCHEMA = {
    "name": "save_journal",
    "description": "Save a learning journal entry capturing what you learned, tools used, tips, or reflections",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The journal entry text",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags to categorize the entry",
            },
        },
        "required": ["content"],
    },
}

READ_JOURNAL_SCHEMA = {
    "name": "read_journal",
    "description": "Read past journal entries to review progress and learnings",
    "input_schema": {
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date filter in ISO 8601 format (e.g. 2026-01-01)",
            },
            "date_to": {
                "type": "string",
                "description": "End date filter in ISO 8601 format (e.g. 2026-03-31)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of entries to return (default 20)",
                "default": 20,
            },
        },
        "required": [],
    },
}


async def save_journal(
    content: str,
    *,
    context: ToolContext,
    tags: list[str] | None = None,
) -> str:
    repo = context.repos.get("journal")
    if repo is None:
        return "Journal repository not available."

    entry_id = str(uuid.uuid4())
    entry = JournalEntry(
        entry_id=entry_id,
        user_id=context.user_id,
        content=content,
        tags=tags or [],
    )
    await repo.create(entry)

    tag_info = f" Tags: {', '.join(tags)}." if tags else ""
    return f"Journal entry saved (ID: {entry_id}).{tag_info}"


async def read_journal(
    context: ToolContext,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> str:
    repo = context.repos.get("journal")
    if repo is None:
        return "Journal repository not available."

    dt_from: datetime | None = None
    dt_to: datetime | None = None

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        except ValueError:
            return f"Invalid date_from format: '{date_from}'. Use ISO 8601 (e.g. 2026-01-01)."

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
        except ValueError:
            return f"Invalid date_to format: '{date_to}'. Use ISO 8601 (e.g. 2026-03-31)."

    entries = await repo.list(
        user_id=context.user_id,
        date_from=dt_from,
        date_to=dt_to,
        limit=limit,
    )

    if not entries:
        return "No journal entries found."

    lines = [f"{len(entries)} journal entry/entries:\n"]
    for entry in entries:
        date_str = entry.created_at.strftime("%Y-%m-%d %H:%M")
        tag_str = f"  [tags: {', '.join(entry.tags)}]" if entry.tags else ""
        lines.append(f"--- {date_str}{tag_str} (ID: {entry.entry_id}) ---")
        lines.append(entry.content)
        lines.append("")

    return "\n".join(lines)


def register_journal_tools(registry) -> None:
    registry.register(SAVE_JOURNAL_SCHEMA, save_journal)
    registry.register(READ_JOURNAL_SCHEMA, read_journal)
