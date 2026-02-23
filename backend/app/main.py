"""FastAPI application setup with lifespan management."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import documents, tags, qa, summaries, quizzes

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
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("AI Study Assistant API starting up")
    logger.info(f"Upload directory: {settings.upload_dir.resolve()}")
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
app.include_router(documents.router)
app.include_router(tags.router)
app.include_router(qa.router)
app.include_router(summaries.router)
app.include_router(quizzes.router)

# CORS – allow React dev server and Streamlit
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


@app.get("/", tags=["health"])
async def root():
    """Health check / API info."""
    return {
        "name": "AI Study Assistant",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    """Detailed health check."""
    from app.database import engine
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "gemini_configured": bool(settings.gemini_api_key),
    }
