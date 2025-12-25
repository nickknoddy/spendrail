"""Pydantic schemas for request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatusEnum(str, Enum):
    """Background task status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


# ==================== Base Config ====================


class ResponseModel(BaseModel):
    """Base model that always includes all fields, even if null."""

    model_config = ConfigDict(
        # Always serialize all fields, never exclude None
        ser_json_inf_nan="null",
    )

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Override to always include all fields."""
        kwargs.setdefault("exclude_none", False)
        return super().model_dump(**kwargs)


# ==================== Response Models ====================


class ImageCategory(ResponseModel):
    """A single image category with confidence score."""

    name: str = Field(default="", description="Category name")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score (0-1)")
    description: str = Field(default="", description="Category description")


class BillItem(ResponseModel):
    """A single line item from a bill/receipt."""

    name: str = Field(default="", description="Item name/description")
    quantity: int = Field(default=1, description="Quantity of item")
    price: float = Field(default=0.0, description="Price of this item")
    currency: str = Field(default="INR", description="Currency code (e.g., INR, USD)")


class BillDetails(ResponseModel):
    """Extracted bill/receipt details with prices."""

    total_amount: float = Field(default=0.0, description="Total bill amount")
    currency: str = Field(default="INR", description="Currency code (e.g., INR, USD)")
    items: list[BillItem] = Field(default_factory=list, description="Individual line items")
    tax: float = Field(default=0.0, description="Tax amount if detected")
    vendor_name: str = Field(default="", description="Merchant/vendor name")
    date: str = Field(default="", description="Bill date if detected")


class ImageCategoryResponse(ResponseModel):
    """Response for synchronous image categorization."""

    success: bool = Field(default=True)
    filename: str = Field(default="", description="Original filename")
    categories: list[ImageCategory] = Field(default_factory=list, description="List of detected categories")
    primary_category: str = Field(default="", description="Most likely category")
    category_matched: bool = Field(default=False, description="Whether image matches allowed categories (food, fuel, medical)")
    raw_analysis: str = Field(default="", description="Raw Gemini response")
    bill_recognised: bool = Field(default=False, description="Whether image is a bill/receipt")
    bill_details: BillDetails = Field(default_factory=BillDetails, description="Extracted bill details")
    processed_at: datetime = Field(default_factory=datetime.now)


class AsyncTaskResponse(ResponseModel):
    """Response for async task submission."""

    success: bool = Field(default=True)
    task_id: str = Field(default="", description="Unique task identifier")
    status: TaskStatusEnum = Field(default=TaskStatusEnum.PENDING, description="Current task status")
    message: str = Field(default="", description="Status message")


class TaskStatusResponse(ResponseModel):
    """Response for task status check."""

    success: bool = Field(default=True)
    task_id: str = Field(default="", description="Unique task identifier")
    status: TaskStatusEnum = Field(default=TaskStatusEnum.PENDING, description="Current task status")
    result: ImageCategoryResponse | None = Field(default=None, description="Result if completed")
    error: str = Field(default="", description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.now, description="Task creation time")
    completed_at: datetime | None = Field(default=None, description="Task completion time")


class HealthResponse(ResponseModel):
    """Health check response."""

    status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="Overall health status")
    version: str = Field(default="", description="Application version")
    timestamp: datetime = Field(default_factory=datetime.now)
    checks: dict[str, bool] = Field(default_factory=dict, description="Individual service checks")


class ErrorDetail(ResponseModel):
    """Error detail for validation errors."""

    field: str = Field(default="")
    message: str = Field(default="")
    type: str = Field(default="")


class ErrorResponse(ResponseModel):
    """Standardized error response."""

    success: bool = Field(default=False)
    error: dict[str, Any] = Field(default_factory=dict, description="Error information")
    request_id: str = Field(default="", description="Request tracking ID")
