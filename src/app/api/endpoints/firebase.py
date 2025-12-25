"""Firebase related endpoints."""

from pydantic import BaseModel, Field

from fastapi import APIRouter

from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/firebase", tags=["Firebase"])


class FirebaseIdRequest(BaseModel):
    """Request with Firebase ID."""
    
    firebase_id: str = Field(..., min_length=1, description="Firebase user ID")


class FirebaseIdResponse(BaseModel):
    """Response for Firebase ID validation."""
    
    success: bool = True
    message: str = "OK"
    firebase_id: str = ""


@router.post(
    "/validate",
    response_model=FirebaseIdResponse,
    summary="Validate Firebase ID",
    description="Accepts a Firebase ID and returns 200 OK",
)
async def validate_firebase_id(request: FirebaseIdRequest) -> FirebaseIdResponse:
    """
    Accept a Firebase ID and return 200 OK.
    
    This endpoint can be used to verify connectivity or validate
    that a Firebase ID has been received.
    """
    logger.info(
        "firebase_id_received",
        firebase_id=request.firebase_id,
    )
    
    return FirebaseIdResponse(
        success=True,
        message="OK",
        firebase_id=request.firebase_id,
    )
