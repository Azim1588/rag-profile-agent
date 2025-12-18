"""Health check endpoints."""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Check database and Redis connections
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/live")
async def liveness_check():
    """Liveness check endpoint."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }

