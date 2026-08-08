"""
Main FastAPI application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging
import os

from src.core.config import settings
from src.db.session import init_db
from src.api.routes import auth, pin, health, totp  # ADDED: totp
from src.services.cleanup_service import CleanupService
from src.utils.logger import setup_logging

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)

# Initialize cleanup service
cleanup_service = CleanupService(interval_seconds=30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    
    Handles startup and shutdown events
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting MFA Authentication System...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Version: 1.0.0")
    logger.info("=" * 60)
    
    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Start cleanup service
    await cleanup_service.start()
    logger.info("✅ Cleanup service started")
    
    logger.info("🚀 Application is ready to accept requests")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("Shutting down MFA Authentication System...")
    
    await cleanup_service.stop()
    logger.info("✅ Cleanup service stopped")
    
    logger.info("👋 Goodbye!")
    logger.info("=" * 60)


# Create FastAPI app
app = FastAPI(
    title="MFA Authentication System",
    description="Multi-Factor Authentication with SMS PIN and TOTP",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# Security middleware
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure properly in production
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment != "production" else [],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(pin.router)
app.include_router(health.router)
app.include_router(totp.router)  # ADDED: TOTP router


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "message": "MFA Authentication System",
        "version": "1.0.0",
        "environment": settings.environment,
        "features": ["sms_pin", "totp_qr"],  # ADDED: TOTP feature
        "docs": "/docs" if settings.environment != "production" else None,
        "health": "/health"
    }


@app.get("/version")
async def version():
    """Get service version"""
    return {
        "version": "1.0.0",
        "environment": settings.environment,
        "python_version": "3.11+",
        "features": ["sms_pin", "totp_qr"]  # ADDED
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )