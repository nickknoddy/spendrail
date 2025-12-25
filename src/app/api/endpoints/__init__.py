"""Endpoints module exports."""

from app.api.endpoints.firebase import router as firebase_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.images import router as images_router

__all__ = [
    "firebase_router",
    "health_router",
    "images_router",
]

