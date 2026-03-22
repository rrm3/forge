"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

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
from backend.api.tips import router as tips_router
from backend.api.tips import set_tips_deps
from backend.api.admin import router as admin_router
from backend.api.admin import set_admin_deps
from backend.api.transcription import router as transcription_router
from backend.api.websocket import router as ws_router
from backend.api.websocket import set_ws_deps
from backend.config import settings
from backend.deps import build_repos, build_storage, build_tool_registry, build_orgchart
from backend.repository.department_config import DepartmentConfigRepository

logger = logging.getLogger(__name__)


# Build dependencies at module level (keep lightweight - no S3 calls)
repos = build_repos()
storage = build_storage()
tool_registry = build_tool_registry()

# Org chart loaded during startup (not at import time to avoid Lambda init timeout)
orgchart = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global orgchart
    import asyncio
    orgchart = await asyncio.get_event_loop().run_in_executor(None, build_orgchart)

    # Wire orgchart into deps now that it's loaded
    set_profile_deps(repos["profiles"], orgchart)
    set_ws_deps(
        sessions_repo=repos["sessions"],
        profiles_repo=repos["profiles"],
        journal_repo=repos["journal"],
        ideas_repo=repos["ideas"],
        tips_repo=repos["tips"],
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
    tips_repo=repos["tips"],
    storage=storage,
    tool_registry=tool_registry,
    orgchart=orgchart,
)
set_sessions_deps(repos["sessions"], storage)
set_profile_deps(repos["profiles"], orgchart)
set_journal_deps(repos["journal"])
set_ideas_deps(repos["ideas"])
set_tips_deps(repos["tips"])
set_admin_deps(DepartmentConfigRepository(storage))

# Include REST routers under /api prefix
app.include_router(sessions_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(journal_router, prefix="/api")
app.include_router(ideas_router, prefix="/api")
app.include_router(tips_router, prefix="/api")
app.include_router(transcription_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

# WebSocket endpoint (no /api prefix - at root /ws)
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
