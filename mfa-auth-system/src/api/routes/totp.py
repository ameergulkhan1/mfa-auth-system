"""
TOTP Authentication Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
import jwt
from datetime import datetime, timedelta

from src.db.session import get_db
from src.models.user import User
from src.services.totp_service import TOTPService
from src.services.audit_service import AuditService
from src.core.config import settings
from src.api.dependencies.database import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/totp", tags=["totp-authentication"])


# ---------- Request/Response Models ----------
class TOTPSetupRequest(BaseModel):
    email: str = Field(..., description="User email for QR code generation")


class TOTPSetupResponse(BaseModel):
    user_id: str
    secret: str
    secret_formatted: str
    qr_code: str
    provisioning_uri: str
    backup_codes: list


class TOTPVerifyRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class TOTPVerifyResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


class TOTPLoginRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    totp_code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")
    ip_address: Optional[str] = None


class TOTPDisableRequest(BaseModel):
    user_id: str = Field(..., description="User ID")


# ---------- Routes ----------
@router.post("/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    request: TOTPSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Setup TOTP for a user - Generates QR code and secret
    
    Returns:
        - QR code as data URI
        - Secret key (for manual entry)
        - Backup codes
    """
    # Check if user exists
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate TOTP secret
    secret = TOTPService.generate_secret()
    
    # Generate QR code
    qr_data = TOTPService.generate_qr_code_data(
        secret=secret,
        email=user.email,
        issuer="MFA System"
    )
    
    # Generate backup codes
    backup_codes = TOTPService.generate_backup_codes(10)
    
    # Store secret temporarily (user must verify first)
    # We'll verify before enabling
    user.totp_secret = secret
    db.commit()
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="totp_setup_initiated",
        method="totp",
        success=True
    )
    
    logger.info(f"TOTP setup initiated for user {user.id}")
    
    return TOTPSetupResponse(
        user_id=str(user.id),
        secret=secret,
        secret_formatted=TOTPService.format_secret_for_display(secret),
        qr_code=qr_data["qr_code"],
        provisioning_uri=qr_data["uri"],
        backup_codes=backup_codes
    )


@router.post("/verify", response_model=TOTPVerifyResponse)
async def verify_totp_setup(
    request: TOTPVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verify TOTP setup - Enables TOTP for user after successful verification
    """
    # Check if user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not set up for this user"
        )
    
    # Verify TOTP code
    is_valid = TOTPService.verify_totp(user.totp_secret, request.code)
    
    if not is_valid:
        audit = AuditService(db)
        audit.log_event(
            user_id=user.id,
            event_type="totp_verification_failed",
            method="totp",
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code"
        )
    
    # Enable TOTP for user
    user.is_totp_enabled = True
    db.commit()
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="totp_enabled",
        method="totp",
        success=True
    )
    
    logger.info(f"TOTP enabled for user {user.id}")
    
    return TOTPVerifyResponse(
        success=True,
        message="TOTP enabled successfully"
    )


@router.post("/login", response_model=TOTPVerifyResponse)
async def login_with_totp(
    request: TOTPLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login using TOTP code (as a standalone method or as second factor)
    """
    # Check if user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check if TOTP is enabled
    if not user.is_totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not enabled for this user"
        )
    
    # Verify TOTP code
    is_valid = TOTPService.verify_totp(user.totp_secret, request.totp_code)
    
    if not is_valid:
        audit = AuditService(db)
        audit.log_event(
            user_id=user.id,
            event_type="totp_login_failed",
            method="totp",
            success=False,
            details={"ip": request.ip_address}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP code"
        )
    
    # Generate JWT token
    expires_delta = timedelta(hours=settings.jwt_expiry_hours)
    expires_at = datetime.utcnow() + expires_delta
    
    token = jwt.encode(
        {
            "user_id": str(user.id),
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "sub": str(user.id),
            "method": "totp"
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm
    )
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="totp_login_success",
        method="totp",
        success=True,
        details={"ip": request.ip_address}
    )
    
    logger.info(f"TOTP login successful for user {user.id}")
    
    return TOTPVerifyResponse(
        success=True,
        message="Login successful",
        token=token
    )


@router.post("/disable")
async def disable_totp(
    request: TOTPDisableRequest,
    db: Session = Depends(get_db)
):
    """
    Disable TOTP for a user (requires backup code or admin)
    """
    # Check if user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Disable TOTP
    user.disable_totp()
    db.commit()
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="totp_disabled",
        method="totp",
        success=True
    )
    
    logger.info(f"TOTP disabled for user {user.id}")
    
    return {
        "success": True,
        "message": "TOTP disabled successfully"
    }


@router.get("/status/{user_id}")
async def get_totp_status(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Check TOTP status for a user
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "user_id": str(user.id),
        "totp_enabled": user.is_totp_enabled,
        "has_secret": bool(user.totp_secret)
    }


@router.post("/backup-codes")
async def generate_backup_codes(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate new backup codes (requires TOTP verification first)
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not enabled for this user"
        )
    
    # Generate new backup codes
    backup_codes = TOTPService.generate_backup_codes(10)
    user.backup_codes = ','.join(backup_codes)
    db.commit()
    
    logger.info(f"New backup codes generated for user {user.id}")
    
    return {
        "success": True,
        "backup_codes": backup_codes
    }