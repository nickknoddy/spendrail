"""API router aggregation."""

from fastapi import APIRouter

from app.api.endpoints import health_router, images_router

# Main API router
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(images_router)

# Root-level routers (health checks don't need /api/v1 prefix)
root_router = APIRouter()
root_router.include_router(health_router)
