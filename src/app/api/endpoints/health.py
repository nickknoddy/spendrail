"""Health check endpoints."""

from fastapi import APIRouter

from app import __version__
from app.models.schemas import HealthResponse, HealthStatus
from app.services.gemini import get_gemini_service

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic health check",
    description="Check if the application is running",
)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=__version__,
        checks={"app": True},
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness check",
    description="Check if the application and all dependencies are ready",
)
async def readiness_check() -> HealthResponse:
    """
    Readiness check including external dependencies.

    Checks:
    - Application is running
    - Gemini API is accessible (if configured)
    """
    gemini_service = get_gemini_service()

    checks = {
        "app": True,
        "gemini_configured": gemini_service.is_configured(),
    }

    # Check Gemini API connectivity if configured
    if gemini_service.is_configured():
        checks["gemini_api"] = await gemini_service.check_health()
    else:
        checks["gemini_api"] = False

    # Determine overall status
    if all(checks.values()):
        status = HealthStatus.HEALTHY
    elif checks["app"]:
        status = HealthStatus.DEGRADED
    else:
        status = HealthStatus.UNHEALTHY

    return HealthResponse(
        status=status,
        version=__version__,
        checks=checks,
    )
