"""Image upload and categorization endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.exceptions import NotFoundError
from app.logging_config import get_logger
from app.models.schemas import (
    AsyncTaskResponse,
    ImageCategoryResponse,
    TaskStatusEnum,
    TaskStatusResponse,
)
from app.services.gemini import get_gemini_service
from app.services.image_processor import get_image_processor
from app.tasks.background import get_task_status, schedule_image_processing

logger = get_logger(__name__)

router = APIRouter(prefix="/images", tags=["Images"])


@router.post(
    "/categorize",
    response_model=ImageCategoryResponse,
    summary="Categorize an image",
    description="Upload an image and receive immediate categorization results using Gemini AI",
)
async def categorize_image(
    file: UploadFile = File(..., description="Image file to categorize"),
) -> ImageCategoryResponse:
    """
    Synchronously categorize an uploaded image.

    The image is processed immediately and the categorization results
    are returned in the response. Use this for small files when you
    need immediate results.

    Supported formats: JPEG, PNG, WebP, HEIC, HEIF
    Maximum file size: 10MB (configurable)
    """
    image_processor = get_image_processor()
    gemini_service = get_gemini_service()

    # Validate and process the upload
    image, filename, _ = await image_processor.process_upload(file)

    # Categorize with Gemini
    result = await gemini_service.categorize_image(image, filename)

    logger.info(
        "image_categorized",
        filename=filename,
        primary_category=result.primary_category,
    )

    return result


@router.post(
    "/categorize/async",
    response_model=AsyncTaskResponse,
    summary="Categorize an image asynchronously",
    description="Upload an image for background categorization. Returns a task ID for status polling.",
)
async def categorize_image_async(
    file: UploadFile = File(..., description="Image file to categorize"),
) -> AsyncTaskResponse:
    """
    Asynchronously categorize an uploaded image.

    The image is queued for background processing. Use the returned
    task_id to poll for results using the /task/{task_id} endpoint.

    This is useful for larger files or when you want non-blocking uploads.

    Supported formats: JPEG, PNG, WebP, HEIC, HEIF
    Maximum file size: 10MB (configurable)
    """
    image_processor = get_image_processor()

    # Validate file type and size
    filename = file.filename or "unknown"
    image_processor.validate_file_type(filename)
    await image_processor.validate_file_size(file)

    # Read file content for background processing
    content = await file.read()

    # Schedule background task
    task_id = schedule_image_processing(content, filename)

    logger.info(
        "async_categorization_scheduled",
        task_id=task_id,
        filename=filename,
    )

    return AsyncTaskResponse(
        task_id=task_id,
        status=TaskStatusEnum.PENDING,
        message=f"Image '{filename}' queued for processing",
    )


@router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Check the status of an async categorization task",
)
async def get_categorization_status(task_id: str) -> TaskStatusResponse:
    """
    Get the status of an async categorization task.

    Possible statuses:
    - pending: Task is queued but not started
    - processing: Task is currently being processed
    - completed: Task finished successfully (result included)
    - failed: Task failed (error message included)
    """
    result = await get_task_status(task_id)

    if result is None:
        raise NotFoundError(
            f"Task '{task_id}' not found",
            details={"task_id": task_id},
        )

    return result
