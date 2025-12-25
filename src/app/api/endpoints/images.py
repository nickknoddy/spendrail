"""Image upload and categorization endpoints."""

import io
from datetime import datetime

import httpx
from PIL import Image
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.exceptions import NotFoundError
from app.logging_config import get_logger
from app.models.schemas import (
    AsyncTaskResponse,
    FirebaseImageCategorizationRequest,
    ImageCategoryResponse,
    TaskStatusEnum,
    TaskStatusResponse,
    TextClassificationRequest,
)
from app.services.firebase import get_firebase_service
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


@router.post(
    "/categorize/text",
    response_model=ImageCategoryResponse,
    summary="Categorize text",
    description="Classify text into categories (food, fuel, medical) using Gemini AI",
)
async def categorize_text(
    request: TextClassificationRequest,
) -> ImageCategoryResponse:
    """
    Categorize text describing a bill, receipt, transaction, or expense.

    The text is analyzed and classified into categories (food, fuel, medical)
    with the same response structure as image categorization.

    Example input:
    - "Paid Rs. 250 at McDonald's for 2 burgers"
    - "Filled petrol worth 2000 at HP station"
    - "Pharmacy bill: Paracetamol 50, Vitamin C 120"

    Returns category, bill details (amounts, items, vendor) if applicable.
    """
    gemini_service = get_gemini_service()

    result = await gemini_service.categorize_text(request.text)

    logger.info(
        "text_categorized",
        text_length=len(request.text),
        primary_category=result.primary_category,
        category_matched=result.category_matched,
    )

    return result


# ==================== Background Task ====================


async def process_firebase_image(transaction_id: str, image_url: str) -> None:
    """
    Download image from URL and classify it, updating Firebase.
    """
    logger.info(
        "background_image_processing_started",
        transaction_id=transaction_id,
        url=image_url[:100],
    )
    
    try:
        # Download image
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            image_bytes = response.content
            
        # Categorize
        gemini_service = get_gemini_service()
        
        # Convert bytes to PIL Image
        pil_image = Image.open(io.BytesIO(image_bytes))
        
        # Pass filename as "firebase_image.jpg" to hint it's an image
        result = await gemini_service.categorize_image(pil_image, "firebase_image.jpg")
        
        # Fetch current transaction data to compare category
        firebase_service = get_firebase_service()
        transaction = await firebase_service.get_transaction(transaction_id)
        current_category = transaction.get("category") if transaction else None
        
        # Determine status
        status = "transaction_disapproved"
        gemini_category = result.primary_category if result.category_matched else "other"
        
        if result.category_matched:
            # If transaction has a category, check if it matches
            if current_category:
                # Normalize for comparison
                if current_category.lower() == gemini_category.lower():
                    status = "transaction_approved"
                else:
                    status = "transaction_flagged"
            else:
                # No existing category, so we approve the Gemini one
                status = "transaction_approved"
        else:
             status = "transaction_disapproved"

        # Prepare update data
        update_data = {
            "imageCategory": gemini_category,
            "status": status,
            "updatedAt": datetime.now(),
        }
        
        # If bill recognized and amount > 0, update amount
        if result.bill_recognised and result.bill_details and result.bill_details.total_amount > 0:
            update_data["amount"] = result.bill_details.total_amount
            
        # Update Firebase
        success = await firebase_service.update_transaction(transaction_id, update_data)
        
        logger.info(
            "background_image_processing_completed",
            transaction_id=transaction_id,
            image_category=update_data["imageCategory"],
            original_category=current_category,
            status=status,
            success=success,
        )
        
    except httpx.HTTPError as e:
        logger.error(
            "background_image_download_failed",
            transaction_id=transaction_id,
            error=str(e),
        )
    except Exception as e:
        logger.error(
            "background_image_processing_failed",
            transaction_id=transaction_id,
            error=str(e),
        )


@router.post(
    "/categorize/firebase",
    response_model=AsyncTaskResponse,
    summary="Categorize image from Firebase",
    description="Fetch image from Firebase URL and classify it",
)
async def categorize_firebase_image(
    request: FirebaseImageCategorizationRequest,
    background_tasks: BackgroundTasks,
) -> AsyncTaskResponse:
    """
    Start background classification for a Firebase image.
    
    1. Fetches transaction to get imageUrl
    2. Starts background task to download and classify image
    3. Returns immediately
    """
    firebase_service = get_firebase_service()
    
    if not firebase_service.is_configured():
         raise HTTPException(
             status_code=503,
             detail="Firebase is not configured. Please set up credentials.",
         )
         
    # Fetch transaction
    transaction = await firebase_service.get_transaction(request.firebase_id)
    if not transaction:
        raise NotFoundError(
            f"Transaction '{request.firebase_id}' not found",
            details={"firebase_id": request.firebase_id}
        )
        
    image_url = transaction.get("imageUrl")
    if not image_url:
        return AsyncTaskResponse(
            task_id=request.firebase_id,
            status=TaskStatusEnum.FAILED,
            message="No imageUrl found in transaction",
        )
        
    background_tasks.add_task(process_firebase_image, request.firebase_id, image_url)
    
    logger.info(
        "firebase_image_categorization_scheduled",
        transaction_id=request.firebase_id,
    )
    
    return AsyncTaskResponse(
        task_id=request.firebase_id,
        status=TaskStatusEnum.PENDING,
        message="Image classification started",
    )

