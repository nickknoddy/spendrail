"""Custom exceptions for the application."""

from typing import Any


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(AppError):
    """Validation error for request data."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=422, details=details)


class NotFoundError(AppError):
    """Resource not found error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=404, details=details)


class GeminiAPIError(AppError):
    """Error communicating with Gemini API."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=502, details=details)


class FileTooLargeError(ValidationError):
    """File exceeds maximum allowed size."""

    def __init__(self, max_size_mb: int, actual_size_mb: float) -> None:
        super().__init__(
            message=f"File size ({actual_size_mb:.2f} MB) exceeds maximum allowed size ({max_size_mb} MB)",
            details={"max_size_mb": max_size_mb, "actual_size_mb": actual_size_mb},
        )


class UnsupportedFileTypeError(ValidationError):
    """File type is not supported."""

    def __init__(self, file_type: str, allowed_types: list[str]) -> None:
        super().__init__(
            message=f"File type '{file_type}' is not supported",
            details={"file_type": file_type, "allowed_types": allowed_types},
        )
