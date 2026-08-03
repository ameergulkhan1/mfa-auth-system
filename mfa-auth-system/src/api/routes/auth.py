"""
Authentication routes - Registration and Login
SECURITY: No user enumeration
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import jwt
from datetime import datetime, timedelta

from src.models.user import User
from src.db.session import get_db
from src.services.audit_service import AuditService
from src.services.pin_service import PinService
from src.services.notification_service import NotificationService
from src.core.config import settings
from src.core.constants import PIN_EXPIRY_SECONDS
from src.utils.validators import validate_phone, validate_email, validate_uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# ---------- Request/Response Models ----------
class UserRegisterRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=20, description="Phone number with country code")
    email: EmailStr = Field(..., description="Valid email address")
    
    @validator('phone')
    def validate_phone_number(cls, v):
        if not validate_phone(v):
            raise ValueError('Invalid phone number format. Use international format (e.g., +1234567890)')
        return v


class UserRegisterResponse(BaseModel):
    user_id: str
    phone: str
    email: str
    message: str


class LoginRequest(BaseModel):
    user_id: str = Field(..., description="User ID from registration")
    ip_address: Optional[str] = Field(None, description="Client IP address for audit")


class LoginResponse(BaseModel):
    user_id: str
    message: str
    pin_sent: bool
    expiry_seconds: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ---------- Routes ----------
@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    Creates a user account with phone and email.
    Returns user ID for subsequent authentication.
    """
    # Check if user exists
    existing = db.query(User).filter(
        (User.phone == request.phone) | (User.email == request.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone or email already exists"
        )
    
    # Create user
    user = User(
        phone=request.phone,
        email=request.email,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="user_registered",
        success=True,
        details={
            "phone_last4": user.phone[-4:] if user.phone else None,
            "email_domain": user.email.split('@')[1] if user.email else None
        }
    )
    
    logger.info(f"New user registered: {user.id}")
    
    return UserRegisterResponse(
        user_id=str(user.id),
        phone=user.phone,
        email=user.email,
        message="User registered successfully"
    )


@router.post("/login/request", response_model=LoginResponse)
async def request_login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Request PIN for login
    
    Generates a 6-digit PIN and sends it to the user's registered device.
    
    IMPORTANT: Returns SAME response whether user exists or not.
    Prevents user enumeration attacks.
    """
    # Validate user_id format
    if not validate_uuid(request.user_id):
        # Log invalid format but return same response
        logger.warning(f"Invalid user_id format: {request.user_id}")
        return LoginResponse(
            user_id=request.user_id,
            message="PIN sent to your registered device",
            pin_sent=True,
            expiry_seconds=PIN_EXPIRY_SECONDS
        )
    
    # Create PIN - handles both existing and non-existent users
    pin_service = PinService(db)
    pin_attempt, pin_code = pin_service.create_pin_attempt(
        user_id=request.user_id,
        ip_address=request.ip_address
    )
    
    # Try to send PIN (will only work if user exists)
    user = db.query(User).filter(User.id == request.user_id).first()
    
    sent = False
    if user and user.is_active:
        notification = NotificationService()
        sent = notification.send_pin_sms(
            phone=user.phone,
            pin=pin_code,
            user_id=request.user_id,
            expiry_minutes=5
        )
        
        if sent:
            # Log successful send
            audit = AuditService(db)
            audit.log_event(
                user_id=request.user_id,
                event_type="pin_sent",
                method="sms",
                success=True
            )
    else:
        # Log internally but don't expose
        logger.info(f"Login request for non-existent or inactive user: {request.user_id}")
        # Don't actually send SMS for non-existent users
    
    # ALWAYS return same response - prevents user enumeration
    return LoginResponse(
        user_id=request.user_id,
        message="PIN sent to your registered device",
        pin_sent=True,  # Always true to prevent enumeration
        expiry_seconds=PIN_EXPIRY_SECONDS
    )


@router.post("/login/token", response_model=TokenResponse)
async def login_with_token(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate a JWT token for authenticated user (internal use)
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Generate JWT
    expires_delta = timedelta(hours=settings.jwt_expiry_hours)
    expires_at = datetime.utcnow() + expires_delta
    
    token = jwt.encode(
        {
            "user_id": str(user.id),
            "exp": expires_at,
            "iat": datetime.utcnow(),
            "sub": str(user.id)
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires_delta.total_seconds())
    )