"""Shared dependency construction for FastAPI app and Lambda handler.

Both main.py (FastAPI/uvicorn) and lambda_ws.py (raw Lambda handler)
use these functions to build repos, storage, tools, and orgchart.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentDeps:
    """Bundle of all dependencies needed by the agent executor."""
    sessions_repo: Any = None
    profiles_repo: Any = None
    journal_repo: Any = None
    ideas_repo: Any = None
    tips_repo: Any = None
    user_ideas_repo: Any = None
    storage: Any = None
    tool_registry: Any = None
    orgchart: Any = None


def build_repos() -> dict:
    """Build repository instances based on config."""
    if settings.dev_mode:
        from backend.repository.ideas import MemoryIdeaRepository
        from backend.repository.journal import MemoryJournalRepository
        from backend.repository.profiles import MemoryProfileRepository
        from backend.repository.sessions import MemorySessionRepository
        from backend.repository.tips import MemoryTipRepository
        from backend.repository.user_ideas import MemoryUserIdeaRepository
        persist_dir = "/tmp/forge-storage/repos"
        return {
            "sessions": MemorySessionRepository(persist_path=f"{persist_dir}/sessions.json"),
            "profiles": MemoryProfileRepository(persist_path=f"{persist_dir}/profiles.json"),
            "journal": MemoryJournalRepository(persist_path=f"{persist_dir}/journal.json"),
            "ideas": MemoryIdeaRepository(persist_path=f"{persist_dir}/ideas.json"),
            "tips": MemoryTipRepository(persist_path=f"{persist_dir}/tips.json"),
            "user_ideas": MemoryUserIdeaRepository(persist_path=f"{persist_dir}/user_ideas.json"),
        }

    from backend.repository.ideas import DynamoDBIdeaRepository
    from backend.repository.journal import DynamoDBJournalRepository
    from backend.repository.profiles import DynamoDBProfileRepository
    from backend.repository.sessions import DynamoDBSessionRepository
    from backend.repository.tips import DynamoDBTipRepository
    from backend.repository.user_ideas import DynamoDBUserIdeaRepository

    prefix = settings.dynamodb_table_prefix
    region = settings.aws_region
    return {
        "sessions": DynamoDBSessionRepository(f"{prefix}-sessions", region),
        "profiles": DynamoDBProfileRepository(f"{prefix}-profiles", region),
        "journal": DynamoDBJournalRepository(f"{prefix}-journal", region),
        "ideas": DynamoDBIdeaRepository(f"{prefix}-ideas", region),
        "tips": DynamoDBTipRepository(f"{prefix}-tips", f"{prefix}-tip-votes", f"{prefix}-tip-comments", region),
        "user_ideas": DynamoDBUserIdeaRepository(f"{prefix}-user-ideas", region),
    }


def build_storage():
    """Build storage backend based on config."""
    if settings.dev_mode:
        from backend.storage import LocalStorage
        local_path = Path("/tmp/forge-storage")
        local_path.mkdir(parents=True, exist_ok=True)
        return LocalStorage(local_path)

    from backend.storage import S3Storage
    return S3Storage(settings.s3_bucket, settings.aws_region)


def build_orgchart():
    """Load org chart from local file or S3."""
    from backend.orgchart import load_orgchart_from_s3, load_orgchart_local

    if settings.dev_mode:
        if settings.orgchart_local_path:
            return load_orgchart_local(settings.orgchart_local_path)
        # Fall back to standard local storage path
        default_path = Path("/tmp/forge-storage/orgchart/org-chart.db")
        if default_path.exists():
            return load_orgchart_local(str(default_path))
        logger.info("No org chart found for dev mode (set ORGCHART_LOCAL_PATH or place at %s)", default_path)
        return None

    return load_orgchart_from_s3(settings.s3_bucket, settings.orgchart_s3_key)


def build_tool_registry():
    """Create tool registry and register all tools."""
    from backend.tools.analyze import register_analyze_tools
    from backend.tools.ideas import register_ideas_tools
    from backend.tools.journal import register_journal_tools
    from backend.tools.profile import register_profile_tools
    from backend.tools.registry import ToolRegistry
    from backend.tools.search import register_search_tools
    from backend.tools.tips import register_tips_tools
    from backend.tools.user_ideas import register_user_ideas_tools

    registry = ToolRegistry()
    register_search_tools(registry)
    register_ideas_tools(registry)
    register_journal_tools(registry)
    register_profile_tools(registry)
    register_analyze_tools(registry)
    register_tips_tools(registry)
    register_user_ideas_tools(registry)
    return registry


def build_agent_deps(repos: dict, storage, tool_registry, orgchart=None) -> AgentDeps:
    """Construct AgentDeps from individual components."""
    return AgentDeps(
        sessions_repo=repos["sessions"],
        profiles_repo=repos["profiles"],
        journal_repo=repos["journal"],
        ideas_repo=repos["ideas"],
        tips_repo=repos.get("tips"),
        user_ideas_repo=repos.get("user_ideas"),
        storage=storage,
        tool_registry=tool_registry,
        orgchart=orgchart,
    )
