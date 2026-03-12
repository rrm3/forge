"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router as chat_router
from backend.api.chat import set_chat_deps
from backend.api.ideas import router as ideas_router
from backend.api.ideas import set_ideas_deps
from backend.api.journal import router as journal_router
from backend.api.journal import set_journal_deps
from backend.api.profile import router as profile_router
from backend.api.profile import set_profile_deps
from backend.api.sessions import router as sessions_router
from backend.api.sessions import set_sessions_deps
from backend.config import settings
from backend.repository.ideas import MemoryIdeaRepository
from backend.repository.journal import MemoryJournalRepository
from backend.repository.profiles import MemoryProfileRepository
from backend.repository.sessions import MemorySessionRepository
from backend.storage import LocalStorage
from backend.tools.curriculum import register_curriculum_tools
from backend.tools.ideas import register_ideas_tools
from backend.tools.journal import register_journal_tools
from backend.tools.profile import register_profile_tools
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


def _build_tool_registry() -> ToolRegistry:
    """Create tool registry and register all tools."""
    registry = ToolRegistry()
    register_curriculum_tools(registry)
    register_ideas_tools(registry)
    register_journal_tools(registry)
    register_profile_tools(registry)
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(
        "Forge starting up: dev_mode=%s, model=%s",
        settings.dev_mode,
        settings.llm_model,
    )
    yield
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
            "https://forge.digital-science.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Build dependencies
repos = _build_repos()
storage = _build_storage()
tool_registry = _build_tool_registry()

# Wire up API routers
set_chat_deps(
    sessions_repo=repos["sessions"],
    profiles_repo=repos["profiles"],
    journal_repo=repos["journal"],
    ideas_repo=repos["ideas"],
    storage=storage,
    tool_registry=tool_registry,
)
set_sessions_deps(repos["sessions"], storage)
set_profile_deps(repos["profiles"])
set_journal_deps(repos["journal"])
set_ideas_deps(repos["ideas"])

# Include routers under /api prefix
app.include_router(chat_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(journal_router, prefix="/api")
app.include_router(ideas_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
