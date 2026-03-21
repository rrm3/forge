"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.sessions import router as sessions_router
from backend.api.sessions import set_sessions_deps
from backend.api.profile import router as profile_router
from backend.api.profile import set_profile_deps
from backend.api.journal import router as journal_router
from backend.api.journal import set_journal_deps
from backend.api.ideas import router as ideas_router
from backend.api.ideas import set_ideas_deps
from backend.api.websocket import router as ws_router
from backend.api.websocket import set_ws_deps
from backend.config import settings
from backend.orgchart import load_orgchart_from_s3, load_orgchart_local
from backend.repository.ideas import MemoryIdeaRepository
from backend.repository.journal import MemoryJournalRepository
from backend.repository.profiles import MemoryProfileRepository
from backend.repository.sessions import MemorySessionRepository
from backend.storage import LocalStorage
from backend.tools.ideas import register_ideas_tools
from backend.tools.journal import register_journal_tools
from backend.tools.profile import register_profile_tools
from backend.tools.search import register_search_tools
from backend.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _build_repos():
    """Build repository instances based on config."""
    if settings.dev_mode:
        return {
            "sessions": MemorySessionRepository(),
            "profiles": MemoryProfileRepository(),
            "journal": MemoryJournalRepository(),
            "ideas": MemoryIdeaRepository(),
        }

    # Production: DynamoDB
    from backend.repository.ideas import DynamoDBIdeaRepository
    from backend.repository.journal import DynamoDBJournalRepository
    from backend.repository.profiles import DynamoDBProfileRepository
    from backend.repository.sessions import DynamoDBSessionRepository

    prefix = settings.dynamodb_table_prefix
    region = settings.aws_region
    return {
        "sessions": DynamoDBSessionRepository(f"{prefix}-sessions", region),
        "profiles": DynamoDBProfileRepository(f"{prefix}-profiles", region),
        "journal": DynamoDBJournalRepository(f"{prefix}-journal", region),
        "ideas": DynamoDBIdeaRepository(f"{prefix}-ideas", region),
    }


def _build_storage():
    """Build storage backend based on config."""
    if settings.dev_mode:
        local_path = Path("/tmp/forge-storage")
        local_path.mkdir(parents=True, exist_ok=True)
        return LocalStorage(local_path)

    from backend.storage import S3Storage
    return S3Storage(settings.s3_bucket, settings.aws_region)


def _build_orgchart():
    """Load org chart from local file or S3."""
    if settings.dev_mode:
        if settings.orgchart_local_path:
            return load_orgchart_local(settings.orgchart_local_path)
        logger.info("No org chart configured for dev mode (set ORGCHART_LOCAL_PATH)")
        return None

    return load_orgchart_from_s3(settings.s3_bucket, settings.orgchart_s3_key)


def _build_tool_registry() -> ToolRegistry:
    """Create tool registry and register all tools."""
    registry = ToolRegistry()
    register_search_tools(registry)
    register_ideas_tools(registry)
    register_journal_tools(registry)
    register_profile_tools(registry)
    return registry


# Build dependencies at module level (keep lightweight - no S3 calls)
repos = _build_repos()
storage = _build_storage()
tool_registry = _build_tool_registry()

# Org chart loaded during startup (not at import time to avoid Lambda init timeout)
orgchart = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global orgchart
    import asyncio
    orgchart = await asyncio.get_event_loop().run_in_executor(None, _build_orgchart)

    # Wire orgchart into deps now that it's loaded
    set_profile_deps(repos["profiles"], orgchart)
    set_ws_deps(
        sessions_repo=repos["sessions"],
        profiles_repo=repos["profiles"],
        journal_repo=repos["journal"],
        ideas_repo=repos["ideas"],
        storage=storage,
        tool_registry=tool_registry,
        orgchart=orgchart,
    )

    logger.info(
        "Forge started: dev_mode=%s, model=%s, orgchart=%s",
        settings.dev_mode,
        settings.llm_model,
        f"{orgchart.count()} people" if orgchart else "not loaded",
    )
    yield
    if orgchart:
        orgchart.close()
    logger.info("Forge shutting down")


app = FastAPI(
    title="Forge",
    description="AI Tuesdays - Digital Science internal chat and RAG application",
    lifespan=lifespan,
)

# CORS
if settings.dev_mode:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://aituesday.digitalscience.ai",
            "https://aituesday-staging.digitalscience.ai",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Wire up deps before lifespan (orgchart will be None but that's fine for import-time)
set_ws_deps(
    sessions_repo=repos["sessions"],
    profiles_repo=repos["profiles"],
    journal_repo=repos["journal"],
    ideas_repo=repos["ideas"],
    storage=storage,
    tool_registry=tool_registry,
    orgchart=orgchart,
)
set_sessions_deps(repos["sessions"], storage)
set_profile_deps(repos["profiles"], orgchart)
set_journal_deps(repos["journal"])
set_ideas_deps(repos["ideas"])

# Include REST routers under /api prefix
app.include_router(sessions_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(journal_router, prefix="/api")
app.include_router(ideas_router, prefix="/api")

# WebSocket endpoint (no /api prefix - at root /ws)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
