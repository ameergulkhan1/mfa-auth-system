"""
PIN verification routes - SECURITY HARDENED
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import jwt
from datetime import datetime, timedelta

from src.db.session import get_db
from src.services.pin_service import PinService
from src.services.notification_service import NotificationService
from src.core.exceptions import (
    InvalidPinError,
    AuthenticationError
)
from src.core.config import settings
from src.core.constants import MAX_ATTEMPTS, PIN_EXPIRY_SECONDS
from src.models.user import User
from src.utils.validators import validate_pin, validate_uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["pin-verification"])


# ---------- Request/Response Models ----------
class VerifyPinRequest(BaseModel):
    user_id: str = Field(..., description="User ID from registration")
    pin: str = Field(..., min_length=6, max_length=6, description="6-digit PIN")
    ip_address: Optional[str] = Field(None, description="Client IP for audit")
    
    @field_validator('pin')
    @classmethod
    def validate_pin_format(cls, v: str) -> str:
        if not validate_pin(v):
            raise ValueError('PIN must be exactly 6 digits')
        return v


class VerifyPinResponse(BaseModel):
    success: bool
    message: str
    attempts_left: Optional[int] = None
    token: Optional[str] = None


class PinStatusResponse(BaseModel):
    has_active_pin: bool
    expires_in: Optional[int] = None
    attempts_used: Optional[int] = None
    attempts_left: Optional[int] = None


class ResendPinResponse(BaseModel):
    message: str
    expires_in: int


# ---------- Routes ----------
@router.post("/verify/pin", response_model=VerifyPinResponse)
async def verify_pin(
    request: VerifyPinRequest,
    db: Session = Depends(get_db)
):
    """
    Verify the submitted PIN
    
    - Valid PIN within 5 minutes → success with JWT token
    - Invalid PIN → retry allowed (3 attempts)
    - 5 minutes elapsed → expired (generic error)
    - 3 failed attempts → blocked (generic error)
    
    All failures return generic authentication responses
    to prevent user enumeration.
    """
    # Validate user_id format
    if not validate_uuid(request.user_id):
        logger.warning(f"Invalid user_id format in PIN verification: {request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or authentication failed"
        )
    
    pin_service = PinService(db)
    
    try:
        # Attempt verification
        success = pin_service.verify_pin(
            user_id=request.user_id,
            submitted_pin=request.pin
        )
        
        # Generate JWT token
        expires_delta = timedelta(hours=settings.jwt_expiry_hours)
        expires_at = datetime.utcnow() + expires_delta
        
        token = jwt.encode(
            {
                "user_id": request.user_id,
                "exp": expires_at,
                "iat": datetime.utcnow(),
                "sub": request.user_id
            },
            settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm
        )
        
        return VerifyPinResponse(
            success=True,
            message="Login successful",
            token=token
        )
        
    except InvalidPinError as e:
        return VerifyPinResponse(
            success=False,
            message=e.message,
            attempts_left=e.details.get("attempts_left")
        )
        
    except AuthenticationError as e:
        # Generic error - don't expose details
        raise HTTPException(
            status_code=e.status_code,
            detail="Invalid credentials or authentication failed"
        )
        
    except Exception as e:
        # Catch-all - return generic error
        logger.error(f"Unexpected error during PIN verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or authentication failed"
        )


@router.get("/pin/status/{user_id}", response_model=PinStatusResponse)
async def get_pin_status(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get status of current PIN for a user
    
    Returns generic response for non-existent users
    to prevent user enumeration.
    """
    # Validate user_id format
    if not validate_uuid(user_id):
        return PinStatusResponse(
            has_active_pin=False,
            expires_in=None,
            attempts_used=None,
            attempts_left=None
        )
    
    # Check if user exists - don't expose
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Return same response as no PIN
        return PinStatusResponse(
            has_active_pin=False,
            expires_in=None,
            attempts_used=None,
            attempts_left=None
        )
    
    pin_service = PinService(db)
    pin_attempt = pin_service.get_active_pin(user_id)
    
    if not pin_attempt:
        return PinStatusResponse(
            has_active_pin=False,
            expires_in=None,
            attempts_used=None,
            attempts_left=None
        )
    
    return PinStatusResponse(
        has_active_pin=True,
        expires_in=pin_attempt.time_remaining,
        attempts_used=pin_attempt.attempts,
        attempts_left=MAX_ATTEMPTS - pin_attempt.attempts
    )


@router.post("/pin/resend", response_model=ResendPinResponse)
async def resend_pin(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Resend PIN to user's device
    
    Returns same response for existing and non-existent users
    to prevent user enumeration.
    """
    # Validate user_id format
    if not validate_uuid(user_id):
        logger.warning(f"Invalid user_id format in resend: {user_id}")
        return ResendPinResponse(
            message="PIN resent to your device",
            expires_in=PIN_EXPIRY_SECONDS
        )
    
    # Check if user exists (don't expose)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        logger.info(f"Resend PIN request for non-existent/inactive user: {user_id}")
        # Return success anyway to prevent enumeration
        return ResendPinResponse(
            message="PIN resent to your device",
            expires_in=PIN_EXPIRY_SECONDS
        )
    
    # Get or create new PIN
    pin_service = PinService(db)
    existing_pin = pin_service.get_active_pin(user_id)
    
    if existing_pin:
        pin_code = existing_pin.pin
        # Reset expiry
        from datetime import datetime, timedelta
        existing_pin.expires_at = datetime.utcnow() + timedelta(seconds=PIN_EXPIRY_SECONDS)
        db.commit()
    else:
        pin_attempt, pin_code = pin_service.create_pin_attempt(user_id)
    
    # Resend
    notification = NotificationService()
    notification.send_pin_sms(
        phone=user.phone,
        pin=pin_code,
        user_id=user_id,
        expiry_minutes=5
    )
    
    return ResendPinResponse(
        message="PIN resent to your device",
        expires_in=PIN_EXPIRY_SECONDS
    )


@router.post("/pin/refresh")
async def refresh_pin(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate a new PIN and invalidate the old one
    
    Useful if user didn't receive the first PIN
    """
    # Validate user_id format
    if not validate_uuid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete old PINs
    pin_service = PinService(db)
    pin_service.cleanup_expired_pins()
    
    # Create new PIN
    pin_attempt, pin_code = pin_service.create_pin_attempt(user_id)
    
    # Send new PIN
    notification = NotificationService()
    notification.send_pin_sms(
        phone=user.phone,
        pin=pin_code,
        user_id=user_id,
        expiry_minutes=5
    )
    
    return {
        "message": "New PIN generated and sent",
        "expires_in": PIN_EXPIRY_SECONDS
    }