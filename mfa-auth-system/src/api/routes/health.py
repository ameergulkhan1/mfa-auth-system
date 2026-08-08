"""
Health check endpoints for monitoring
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import sys
from typing import Optional

from src.db.session import get_db, get_db_status
from src.core.config import settings
from src.services.cleanup_service import CleanupService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Global reference for cleanup service (will be set in main)
_cleanup_service: Optional[CleanupService] = None


def set_cleanup_service(service: CleanupService):
    """Set cleanup service reference for health metrics"""
    global _cleanup_service
    _cleanup_service = service


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for monitoring
    
    Returns:
        dict: Health status with database and service information
    """
    # Check database connection
    db_status = get_db_status()
    
    return {
        "status": "healthy" if db_status["status"] == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "service": "mfa-auth-system",
        "version": "1.0.0",
        "environment": settings.environment,
        "python_version": sys.version.split()[0]
    }


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe for orchestration (Kubernetes, etc.)
    
    Checks if the service is ready to accept traffic
    """
    # Check database
    db_status = get_db_status()
    
    if db_status["status"] != "healthy":
        return {
            "status": "not ready",
            "reason": "database unavailable",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe for orchestration (Kubernetes, etc.)
    
    Checks if the service is still running
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/metrics")
async def get_metrics():
    """
    Get service metrics
    
    Returns:
        dict: Service metrics including cleanup statistics
    """
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "uptime": "unknown",  # Would need startup time tracking
        "cleanup": {}
    }
    
    # Get cleanup stats if available
    if _cleanup_service:
        try:
            metrics["cleanup"] = _cleanup_service.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get cleanup stats: {e}")
    
    return metrics