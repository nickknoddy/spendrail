"""Firebase related endpoints."""

import asyncio
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.logging_config import get_logger
from app.services.firebase import get_firebase_service
from app.services.gemini import get_gemini_service

logger = get_logger(__name__)

router = APIRouter(prefix="/firebase", tags=["Firebase"])


# ==================== Request/Response Models ====================


class TransactionValidateRequest(BaseModel):
    """Request to validate and process a transaction."""
    
    firebase_id: str = Field(..., min_length=1, description="Transaction document ID")


class TransactionValidateResponse(BaseModel):
    """Response for transaction validation."""
    
    success: bool = True
    message: str = "OK"
    transaction_id: str = ""
    note: str = ""
    status: str = "processing"


class TransactionUpdateRequest(BaseModel):
    """Request to update a transaction document."""
    
    transaction_id: str = Field(..., min_length=1, description="Transaction document ID")
    category: str | None = Field(None, description="Updated category")
    amount: float | None = Field(None, description="Updated amount")
    status: str | None = Field(None, description="Updated status")
    note: str | None = Field(None, description="Updated note")


class TransactionUpdateResponse(BaseModel):
    """Response for transaction update."""
    
    success: bool = True
    message: str = "OK"
    transaction_id: str = ""
    updated_fields: list[str] = Field(default_factory=list)


# ==================== Background Task ====================


async def process_transaction_classification(transaction_id: str, note: str) -> None:
    """
    Background task to classify transaction note and update Firestore.
    """
    logger.info(
        "background_classification_started",
        transaction_id=transaction_id,
        note_length=len(note),
    )
    
    try:
        gemini_service = get_gemini_service()
        firebase_service = get_firebase_service()
        
        # Classify the note text
        result = await gemini_service.categorize_text(note)
        
        # Prepare update data
        update_data: dict[str, Any] = {
            "category": result.primary_category if result.category_matched else "other",
            "status": "transaction_approved" if result.category_matched else "transaction_disapproved",
            "updatedAt": datetime.now(),
        }
        
        # If bill was recognized and has amount, update it
        if result.bill_recognised and result.bill_details.total_amount > 0:
            update_data["amount"] = result.bill_details.total_amount
        
        # Update Firestore
        success = await firebase_service.update_transaction(
            transaction_id=transaction_id,
            data=update_data,
        )
        
        logger.info(
            "background_classification_completed",
            transaction_id=transaction_id,
            category=update_data["category"],
            category_matched=result.category_matched,
            status=update_data["status"],
            success=success,
        )
        
    except Exception as e:
        logger.error(
            "background_classification_failed",
            transaction_id=transaction_id,
            error=str(e),
        )
        # Update status to failed
        try:
            firebase_service = get_firebase_service()
            await firebase_service.update_transaction(
                transaction_id=transaction_id,
                data={"status": "failed", "updatedAt": datetime.now()},
            )
        except Exception:
            pass


# ==================== Endpoints ====================


@router.post(
    "/validate",
    response_model=TransactionValidateResponse,
    summary="Validate and process transaction",
    description="Fetch transaction by ID and start background classification using the note",
)
async def validate_transaction(
    request: TransactionValidateRequest,
    background_tasks: BackgroundTasks,
) -> TransactionValidateResponse:
    """
    Validate a transaction and start background classification.
    
    1. Fetches the transaction document from Firestore using firebase_id
    2. Extracts the 'note' field from the document
    3. Starts a background job for text classification
    4. Returns immediately with 200 OK
    """
    firebase_service = get_firebase_service()
    
    if not firebase_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Firebase is not configured. Please set up credentials.",
        )
    
    # Fetch the transaction document
    transaction = await firebase_service.get_transaction(request.firebase_id)
    
    if transaction is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{request.firebase_id}' not found",
        )
    
    # Extract the note
    note = transaction.get("note", "")
    
    if not note:
        logger.warning(
            "transaction_no_note",
            transaction_id=request.firebase_id,
        )
        return TransactionValidateResponse(
            success=True,
            message="Transaction found but no note to classify",
            transaction_id=request.firebase_id,
            note="",
            status=transaction.get("status", "processing"),
        )
    
    # Start background classification task
    background_tasks.add_task(
        process_transaction_classification,
        request.firebase_id,
        note,
    )
    
    logger.info(
        "transaction_validation_started",
        transaction_id=request.firebase_id,
        note=note[:100],  # Log first 100 chars
    )
    
    return TransactionValidateResponse(
        success=True,
        message="Transaction validation started, classification in progress",
        transaction_id=request.firebase_id,
        note=note,
        status="processing",
    )


@router.post(
    "/transaction/update",
    response_model=TransactionUpdateResponse,
    summary="Update a transaction",
    description="Update specific fields in a transaction document",
)
async def update_transaction(request: TransactionUpdateRequest) -> TransactionUpdateResponse:
    """
    Update a transaction document in Firestore.
    
    Only updates the fields that are provided in the request.
    Automatically sets 'updatedAt' to current timestamp.
    """
    firebase_service = get_firebase_service()
    
    if not firebase_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Firebase is not configured. Please set up credentials.",
        )
    
    # Build update data from provided fields
    update_data: dict[str, Any] = {
        "updatedAt": datetime.now(),
    }
    updated_fields = ["updatedAt"]
    
    if request.category is not None:
        update_data["category"] = request.category
        updated_fields.append("category")
    
    if request.amount is not None:
        update_data["amount"] = request.amount
        updated_fields.append("amount")
    
    if request.status is not None:
        update_data["status"] = request.status
        updated_fields.append("status")
    
    if request.note is not None:
        update_data["note"] = request.note
        updated_fields.append("note")
    
    success = await firebase_service.update_transaction(
        transaction_id=request.transaction_id,
        data=update_data,
    )
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update transaction '{request.transaction_id}'",
        )
    
    logger.info(
        "transaction_updated_via_api",
        transaction_id=request.transaction_id,
        updated_fields=updated_fields,
    )
    
    return TransactionUpdateResponse(
        success=True,
        message="Transaction updated successfully",
        transaction_id=request.transaction_id,
        updated_fields=updated_fields,
    )
