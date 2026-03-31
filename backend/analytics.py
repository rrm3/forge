"""PostHog analytics helpers.

Initialises a PostHog client when a project API key is configured.
All public functions no-op gracefully when analytics is disabled (e.g. in dev).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

_client = None

if settings.posthog_api_key:
    from posthog import Posthog

    _client = Posthog(
        project_api_key=settings.posthog_api_key,
        host=settings.posthog_host,
    )
    logger.info("PostHog analytics enabled (host=%s)", settings.posthog_host)


def track(
    distinct_id: str,
    event: str,
    properties: dict[str, Any] | None = None,
    groups: dict[str, str] | None = None,
) -> None:
    if _client is None:
        return
    kwargs: dict[str, Any] = {}
    if properties:
        kwargs["properties"] = properties
    if groups:
        kwargs["groups"] = groups
    _client.capture(distinct_id=distinct_id, event=event, **kwargs)


def identify(
    distinct_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    if _client is None:
        return
    _client.set(distinct_id=distinct_id, properties=properties or {})


def group_identify(
    group_type: str,
    group_key: str,
    properties: dict[str, Any] | None = None,
) -> None:
    if _client is None:
        return
    _client.group_identify(
        group_type=group_type,
        group_key=group_key,
        properties=properties or {},
    )


def capture_exception(
    exc: Exception,
    distinct_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    if _client is None:
        return
    import traceback

    props: dict[str, Any] = {
        "$exception_type": type(exc).__name__,
        "$exception_message": str(exc),
        "$exception_stack_trace_raw": "".join(traceback.format_exception(exc)),
    }
    if properties:
        props.update(properties)
    _client.capture(
        distinct_id=distinct_id or "server",
        event="$exception",
        properties=props,
    )


def flush() -> None:
    if _client is None:
        return
    _client.flush()


def shutdown() -> None:
    if _client is None:
        return
    _client.shutdown()
