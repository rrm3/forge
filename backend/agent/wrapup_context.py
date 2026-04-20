"""Load the at-session-start context bundle for wrapup sessions.

Wrapup sessions need to reference what the user set out to do this morning
(intake responses), what they actually captured during the day (journal
entries), and what happened last week (the prior digest). We load all three
in parallel at the top of ``run_agent_session`` and pass the result into
``build_system_prompt`` so the agent has the context without issuing tool
calls on every turn.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from backend.models import UserProfile, effective_program_week, make_plan_objective
from backend.repository.journal import JournalRepository
from backend.storage import (
    StorageBackend,
    load_intake_responses,
    load_pulse_config,
    load_pulse_responses,
)

logger = logging.getLogger(__name__)

_JOURNAL_CONTENT_TRUNCATION = 500
_JOURNAL_LIMIT = 10


def questions_to_ask(config: list[dict], answers: list[dict]) -> list[dict]:
    """Return the pulse questions that still need answers at the current version.

    A question is "already answered" when the user's log has at least one
    record with a matching ``(question_id, version)`` pair. Malformed records
    in the log are ignored (a user should not be blocked from being asked
    because of a corrupt row written by some future version of the app).
    """
    answered: set[tuple[str, str]] = set()
    for record in answers or []:
        if not isinstance(record, dict):
            continue
        qid = record.get("question_id")
        ver = record.get("version")
        if isinstance(qid, str) and isinstance(ver, str):
            answered.add((qid, ver))

    remaining: list[dict] = []
    for question in config or []:
        if not isinstance(question, dict):
            continue
        qid = question.get("id")
        ver = question.get("version")
        if not isinstance(qid, str) or not isinstance(ver, str):
            continue
        if (qid, ver) in answered:
            continue
        remaining.append(question)
    return remaining


def _today_range(timezone: str | None) -> tuple[datetime, datetime]:
    """Compute [today_start, today_end) as UTC datetimes for a user timezone.

    Falls back to UTC if the timezone string is missing or invalid.
    """
    tz = None
    if timezone:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(timezone)
        except Exception:
            tz = None

    if tz is not None:
        local_now = datetime.now(tz)
        local_today = local_now.date()
        start_local = datetime.combine(local_today, time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)

    today = datetime.now(UTC).date()
    start = datetime.combine(today, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _in_today(captured_at_str: str, start: datetime, end: datetime) -> bool:
    """Return True if a stored ``captured_at`` ISO string falls within today."""
    if not captured_at_str:
        return False
    try:
        dt = datetime.fromisoformat(captured_at_str)
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return start <= dt < end


def _select_todays_intake(
    all_responses: dict[str, Any],
    today_start: datetime,
    today_end: datetime,
    current_week: int,
    merged_objectives: list[dict] | None,
) -> list[dict]:
    """Filter intake responses to ones captured today, preserving label order.

    Returns a list of ``{"id", "label", "value"}`` dicts. The synthetic
    ``plan-day{N}`` objective is always rendered first when present.
    """
    plan_key = f"plan-day{current_week}"

    # Build a label map from merged_objectives if we have it; otherwise fall
    # back to the response's "label" key (older responses store labels inline).
    labels: dict[str, str] = {}
    if merged_objectives:
        for obj in merged_objectives:
            obj_id = obj.get("id", "")
            if obj_id:
                labels[obj_id] = obj.get("label", obj_id)

    # Make sure the synthetic plan objective has a label even if it wasn't in
    # the merged list (e.g., injected later in the turn).
    if plan_key not in labels:
        labels[plan_key] = make_plan_objective(current_week).get("label", plan_key)

    today_items: list[tuple[str, str, str]] = []
    for obj_id, resp in (all_responses or {}).items():
        if not isinstance(resp, dict):
            continue
        captured_at = resp.get("captured_at", "")
        if not _in_today(captured_at, today_start, today_end):
            continue
        value = resp.get("value", "")
        if value in (None, ""):
            continue
        label = labels.get(obj_id) or resp.get("label") or obj_id
        today_items.append((obj_id, label, str(value)))

    # Sort: plan-day{N} first if present, then stable by id.
    today_items.sort(key=lambda item: (0 if item[0] == plan_key else 1, item[0]))
    return [{"id": item[0], "label": item[1], "value": item[2]} for item in today_items]


async def _load_todays_intake(
    storage: StorageBackend,
    user_id: str,
    today_start: datetime,
    today_end: datetime,
    current_week: int,
    merged_objectives: list[dict] | None,
) -> list[dict]:
    try:
        responses = await load_intake_responses(storage, user_id)
    except Exception:
        logger.warning("Failed to load intake responses for wrapup context (user=%s)", user_id, exc_info=True)
        return []
    return _select_todays_intake(responses, today_start, today_end, current_week, merged_objectives)


async def _load_todays_journal(
    journal_repo: JournalRepository | None,
    user_id: str,
    today_start: datetime,
    today_end: datetime,
    user_timezone: str | None,
) -> list[dict]:
    if journal_repo is None:
        return []
    try:
        entries = await journal_repo.list(
            user_id,
            date_from=today_start,
            date_to=today_end,
            limit=_JOURNAL_LIMIT,
        )
    except Exception:
        logger.warning("Failed to load journal entries for wrapup context (user=%s)", user_id, exc_info=True)
        return []

    # Render in the user's timezone where possible so the [HH:MM] matches
    # what they'd expect to see in their journal.
    tz = None
    if user_timezone:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(user_timezone)
        except Exception:
            tz = None

    items: list[dict] = []
    for entry in entries:
        content = entry.content or ""
        if len(content) > _JOURNAL_CONTENT_TRUNCATION:
            content = content[: _JOURNAL_CONTENT_TRUNCATION - 3] + "..."
        created = entry.created_at
        if created is None:
            timestamp = ""
        else:
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            local = created.astimezone(tz) if tz else created
            timestamp = local.strftime("%H:%M")
        items.append({"timestamp": timestamp, "content": content})
    # JournalRepository.list already returns newest-first; keep that order.
    return items


async def _load_previous_digest(
    storage: StorageBackend,
    user_id: str,
    current_week: int,
) -> str:
    if current_week <= 1:
        return ""
    key = f"profiles/{user_id}/digest-week{current_week - 1}.md"
    try:
        data = await storage.read(key)
    except Exception:
        logger.warning("Failed to load previous-week digest for wrapup context (user=%s)", user_id, exc_info=True)
        return ""
    if data is None:
        return ""
    return data.decode()


async def _load_pulse_to_ask(
    storage: StorageBackend,
    user_id: str,
) -> list[dict]:
    config = load_pulse_config()
    if not config:
        return []
    try:
        answers = await load_pulse_responses(storage, user_id)
    except Exception:
        logger.warning("Failed to load pulse responses for wrapup context (user=%s)", user_id, exc_info=True)
        answers = []
    return questions_to_ask(config, answers)


async def load_wrapup_context(
    storage: StorageBackend,
    journal_repo: JournalRepository | None,
    profile: UserProfile | None,
    user_id: str,
    merged_objectives: list[dict] | None = None,
) -> dict:
    """Load today's intake + journal, the previous digest, and pulse to-ask.

    Runs the I/O in parallel via ``asyncio.gather``. All failures are swallowed
    so a single slow or missing source cannot break the session — the caller
    receives the partial dict it can pass into ``build_system_prompt``.
    """
    tz = profile.timezone if profile else None
    today_start, today_end = _today_range(tz)
    current_week = effective_program_week(profile) if profile else 1

    intake_task = _load_todays_intake(
        storage, user_id, today_start, today_end, current_week, merged_objectives,
    )
    journal_task = _load_todays_journal(journal_repo, user_id, today_start, today_end, tz)
    digest_task = _load_previous_digest(storage, user_id, current_week)
    pulse_task = _load_pulse_to_ask(storage, user_id)

    intake_items, journal_items, digest_text, pulse_items = await asyncio.gather(
        intake_task, journal_task, digest_task, pulse_task,
    )

    return {
        "intake_today": intake_items,
        "journal_today": journal_items,
        "previous_digest": digest_text,
        "pulse_to_ask": pulse_items,
    }


def wrapup_context_is_empty(wrapup_context: dict | None) -> bool:
    """Return True when every wrapup-context subsection is empty."""
    if not wrapup_context:
        return True
    return not (
        wrapup_context.get("intake_today")
        or wrapup_context.get("journal_today")
        or wrapup_context.get("previous_digest")
        or wrapup_context.get("pulse_to_ask")
    )
