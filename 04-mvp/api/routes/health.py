"""Health check routes."""
from fastapi import APIRouter
from api.services.health_check import check_health

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    """System health check endpoint."""
    return check_health()
