"""Background task management for async image processing."""

import asyncio
import io
import uuid
from datetime import datetime
from typing import Any

from PIL import Image

from app.logging_config import get_logger
from app.models.schemas import ImageCategoryResponse, TaskStatusEnum, TaskStatusResponse
from app.services.gemini import get_gemini_service

logger = get_logger(__name__)


class TaskStore:
    """
    In-memory task storage.

    Note: For production, replace with Redis or a database for persistence
    across restarts and horizontal scaling.
    """

    def __init__(self) -> None:
        """Initialize task store."""
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_task(self, task_id: str, filename: str) -> None:
        """Create a new task entry."""
        async with self._lock:
            self._tasks[task_id] = {
                "status": TaskStatusEnum.PENDING,
                "filename": filename,
                "result": None,
                "error": None,
                "created_at": datetime.now(),
                "completed_at": None,
            }

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get task by ID."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        status: TaskStatusEnum,
        result: ImageCategoryResponse | None = None,
        error: str | None = None,
    ) -> None:
        """Update task status and result."""
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = status
                if result is not None:
                    self._tasks[task_id]["result"] = result
                if error is not None:
                    self._tasks[task_id]["error"] = error
                if status in (TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED):
                    self._tasks[task_id]["completed_at"] = datetime.now()

    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove tasks older than specified age."""
        cutoff = datetime.now()
        removed = 0

        async with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                age_hours = (cutoff - task["created_at"]).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]
                removed += 1

        if removed:
            logger.info("tasks_cleaned_up", count=removed)

        return removed

    @property
    def task_count(self) -> int:
        """Get current number of tasks."""
        return len(self._tasks)


# Global task store instance
_task_store: TaskStore | None = None


def get_task_store() -> TaskStore:
    """Get or create task store singleton."""
    global _task_store
    if _task_store is None:
        _task_store = TaskStore()
    return _task_store


async def process_image_task(
    task_id: str,
    image_bytes: bytes,
    filename: str,
) -> None:
    """
    Background task to process an image for categorization.

    Args:
        task_id: Unique task identifier
        image_bytes: Image file bytes
        filename: Original filename
    """
    task_store = get_task_store()
    gemini_service = get_gemini_service()

    try:
        # Update status to processing
        await task_store.update_task(task_id, TaskStatusEnum.PROCESSING)

        logger.info(
            "background_task_started",
            task_id=task_id,
            filename=filename,
        )

        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Perform categorization
        result = await gemini_service.categorize_image(image, filename)

        # Update with result
        await task_store.update_task(
            task_id,
            TaskStatusEnum.COMPLETED,
            result=result,
        )

        logger.info(
            "background_task_completed",
            task_id=task_id,
            filename=filename,
            primary_category=result.primary_category,
        )

    except Exception as e:
        error_msg = str(e)
        await task_store.update_task(
            task_id,
            TaskStatusEnum.FAILED,
            error=error_msg,
        )

        logger.exception(
            "background_task_failed",
            task_id=task_id,
            filename=filename,
            error=error_msg,
        )


def schedule_image_processing(
    image_bytes: bytes,
    filename: str,
) -> str:
    """
    Schedule an image for background processing.

    Args:
        image_bytes: Image file bytes
        filename: Original filename

    Returns:
        Task ID for status tracking
    """
    task_id = str(uuid.uuid4())
    task_store = get_task_store()

    # Create task entry synchronously
    asyncio.create_task(task_store.create_task(task_id, filename))

    # Schedule processing
    asyncio.create_task(process_image_task(task_id, image_bytes, filename))

    logger.info(
        "task_scheduled",
        task_id=task_id,
        filename=filename,
    )

    return task_id


async def get_task_status(task_id: str) -> TaskStatusResponse | None:
    """
    Get the current status of a background task.

    Args:
        task_id: Task identifier

    Returns:
        TaskStatusResponse or None if task not found
    """
    task_store = get_task_store()
    task = await task_store.get_task(task_id)

    if task is None:
        return None

    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        result=task.get("result"),
        error=task.get("error"),
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
    )
