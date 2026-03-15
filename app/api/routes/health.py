"""
Health check endpoint (no auth). For Render and local readiness probes.
"""
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """
    Liveness/readiness check. Returns 200 when the app is up.
    No authentication required.
    """
    return {
        "status": "ok",
        "env": settings.app_env,
    }
