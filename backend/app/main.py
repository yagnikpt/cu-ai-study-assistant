"""FastAPI application setup with lifespan management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    analytics,
    auth,
    documents,
    flashcards,
    qa,
    quizzes,
    spaces,
    study_plans,
    summaries,
    tags,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown logic."""
    # Startup
    logger.info("AI Study Assistant API starting up")
    logger.info(f"Generation model: {settings.generation_model}")
    logger.info(f"Embedding model: {settings.embedding_model}")

    yield

    # Shutdown
    from app.database import engine

    await engine.dispose()
    logger.info("AI Study Assistant API shut down")


app = FastAPI(
    title="AI Study Assistant",
    description=(
        "An AI-powered study assistant that helps you learn from your course materials. "
        "Upload PDFs, ask questions, generate summaries, and take quizzes - all grounded "
        "in your actual study materials with proper source citations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth.router)
app.include_router(spaces.router)
app.include_router(documents.router)
app.include_router(tags.router)
app.include_router(qa.router)
app.include_router(summaries.router)
app.include_router(quizzes.router)
app.include_router(flashcards.router)
app.include_router(study_plans.router)
app.include_router(analytics.router)

# CORS – only needed for local dev (in production frontend is same-origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # CRA / other dev server
        "http://localhost:8501",  # Streamlit
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    """Detailed health check."""
    from sqlalchemy import text

    from app.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "gemini_configured": bool(settings.gcp_project_id),
    }


# ---------------------------------------------------------------------------
# Serve the frontend SPA in production
# ---------------------------------------------------------------------------
if settings.static_dir:
    _static_dir = Path(settings.static_dir)

    if _static_dir.is_dir():
        # Serve hashed assets (JS/CSS/images) under /assets
        _assets_dir = _static_dir / "assets"
        if _assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(_assets_dir)),
                name="static-assets",
            )

        # Serve other root-level static files (favicon.ico, etc.)
        app.mount(
            "/static",
            StaticFiles(directory=str(_static_dir)),
            name="static-root",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(request: Request, full_path: str):
            """SPA fallback: serve index.html for any non-API route."""
            # Try to serve an exact file match first (e.g. favicon.ico)
            file_path = _static_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(str(file_path))
            # Otherwise return the SPA entry point
            return FileResponse(str(_static_dir / "index.html"))

        logger.info("Serving frontend SPA from %s", _static_dir)
