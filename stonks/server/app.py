"""FastAPI application factory for stonks."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from stonks.config import resolve_db_path
from stonks.server.dependencies import init_db_manager
from stonks.server.routes.experiments import router as experiments_router
from stonks.server.routes.metrics import router as metrics_router
from stonks.server.routes.runs import router as runs_router
from stonks.server.routes.stream import router as stream_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the SQLite database file. If None, resolves from
            STONKS_DB env var or the default location.

    Returns:
        Configured FastAPI application.
    """
    if db_path is None:
        db_path = str(resolve_db_path(None))
    app = FastAPI(title="stonks", version="0.1.0", description="ML experiment tracking dashboard")

    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db_manager(db_path)

    app.include_router(experiments_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(metrics_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
        logger.debug(f"Mounted static files from {STATIC_DIR}")

    logger.info(f"Stonks server initialized with database at {db_path}")
    return app
