"""Global error handling middleware and exception handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.logging_config import get_logger

logger = get_logger(__name__)


def create_error_response(
    status_code: int,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Create a standardized error response."""
    content: dict[str, Any] = {
        "success": False,
        "error": {
            "message": message,
            "status_code": status_code,
        },
    }

    if details:
        content["error"]["details"] = details

    if request_id:
        content["request_id"] = request_id

    return JSONResponse(status_code=status_code, content=content)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom application errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.warning(
        "app_error",
        error_type=type(exc).__name__,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )

    return create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions."""
    request_id = getattr(request.state, "request_id", None)

    logger.warning(
        "http_error",
        status_code=exc.status_code,
        detail=exc.detail,
    )

    return create_error_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        request_id=request_id,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors."""
    request_id = getattr(request.state, "request_id", None)

    # Format validation errors
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning(
        "validation_error",
        errors=errors,
    )

    return create_error_response(
        status_code=422,
        message="Validation error",
        details={"errors": errors},
        request_id=request_id,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    request_id = getattr(request.state, "request_id", None)

    logger.exception(
        "unhandled_error",
        error_type=type(exc).__name__,
        error=str(exc),
    )

    return create_error_response(
        status_code=500,
        message="Internal server error",
        request_id=request_id,
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
