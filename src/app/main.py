"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app import __version__
from app.api import api_router, root_router
from app.config import get_settings
from app.logging_config import get_logger, setup_logging
from app.middleware import (
    LoggingMiddleware,
    RequestIDMiddleware,
    setup_cors,
    setup_exception_handlers,
)
from app.tasks.background import get_task_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    logger = get_logger(__name__)
    settings = get_settings()

    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.app_env,
        version=__version__,
    )

    # Ensure upload directory exists
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    logger.info("upload_directory_ready", path=str(upload_path))

    yield

    # Shutdown
    logger.info("application_shutting_down")

    # Cleanup old tasks
    task_store = get_task_store()
    cleaned = await task_store.cleanup_old_tasks(max_age_hours=0)
    logger.info("shutdown_cleanup_complete", tasks_cleaned=cleaned)


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application instance.
    """
    # Setup logging first
    setup_logging()

    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title="Spend-Rail Image Categorization API",
        description=(
            "An API for categorizing images using Google Gemini AI. "
            "Upload images to automatically categorize them into relevant categories "
            "such as receipts, invoices, documents, food, travel, and more."
        ),
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Setup middleware (order matters - first added = outermost layer)
    # Request ID middleware should be outermost for consistent tracking
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)

    # CORS middleware
    setup_cors(app)

    # Exception handlers
    setup_exception_handlers(app)

    # Include routers
    app.include_router(root_router)  # Health checks at root level
    app.include_router(api_router)  # API endpoints under /api/v1

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
    )
