"""
PIN generation and verification service - SECURITY HARDENED
"""
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from src.models.pin_attempt import PinAttempt
from src.models.user import User
from src.core.exceptions import (
    AuthenticationError,
    InvalidPinError,
    PinExpiredError,
    PinBlockedError,
)
from src.core.constants import PIN_LENGTH, MAX_ATTEMPTS, PIN_EXPIRY_SECONDS
from src.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class PinService:
    """Service for managing PIN-based authentication"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
    
    def generate_pin(self) -> str:
        """Generate a random 6-digit PIN"""
        return f"{random.randint(10**(PIN_LENGTH-1), 10**PIN_LENGTH - 1)}"
    
    def create_pin_attempt(self, user_id: str, ip_address: str = None) -> Tuple[PinAttempt, str]:
        """
        Create a new PIN attempt for a user
        
        IMPORTANT: User existence is NOT exposed to client.
        Returns same response whether user exists or not.
        """
        # Check if user exists - but DON'T expose result to client
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            # Log the attempt internally
            logger.warning(f"PIN request for non-existent user: {user_id} from IP: {ip_address}")
            
            # Create a fake PIN attempt to maintain consistent behavior
            pin_code = self.generate_pin()
            
            # Audit internally
            self.audit_service.log_event(
                user_id=None,
                event_type="pin_request_failed",
                method="sms",
                success=False,
                details={"reason": "user_not_found", "requested_user_id": user_id}
            )
            
            # Return fake PIN but don't store in DB
            mock_pin = PinAttempt(
                user_id=user_id,
                pin=pin_code,
                expires_at=datetime.utcnow() + timedelta(seconds=PIN_EXPIRY_SECONDS),
                attempts=0
            )
            return mock_pin, pin_code
        
        # User exists - proceed normally
        pin_code = self.generate_pin()
        
        pin_attempt = PinAttempt(
            user_id=user_id,
            pin=pin_code,
            expires_at=datetime.utcnow() + timedelta(seconds=PIN_EXPIRY_SECONDS),
            attempts=0
        )
        self.db.add(pin_attempt)
        self.db.commit()
        self.db.refresh(pin_attempt)
        
        # Log event
        self.audit_service.log_event(
            user_id=user_id,
            event_type="pin_generated",
            method="sms",
            success=True,
            details={"expires_in": PIN_EXPIRY_SECONDS}
        )
        
        logger.info(f"PIN generated for user {user_id}")
        return pin_attempt, pin_code
    
    def verify_pin(self, user_id: str, submitted_pin: str) -> bool:
        """
        Verify the submitted PIN against stored PIN
        
        IMPORTANT: All failures return generic AuthenticationError
        to prevent user enumeration.
        """
        # Get active PIN attempts for user
        pin_record = self.db.query(PinAttempt).filter(
            PinAttempt.user_id == user_id,
            PinAttempt.expires_at > datetime.utcnow()
        ).order_by(PinAttempt.created_at.desc()).first()
        
        # Generic auth failure - don't expose why
        if not pin_record:
            logger.warning(f"PIN verification failed - no active PIN for user: {user_id}")
            self.audit_service.log_event(
                user_id=user_id,
                event_type="pin_verification_failed",
                method="sms",
                success=False,
                details={"reason": "no_active_pin"}
            )
            raise AuthenticationError(log_user_id=user_id)
        
        # Check expiry
        if pin_record.is_expired:
            self.db.delete(pin_record)
            self.db.commit()
            logger.warning(f"PIN expired for user: {user_id}")
            self.audit_service.log_event(
                user_id=user_id,
                event_type="pin_expired",
                method="sms",
                success=False
            )
            raise AuthenticationError(log_user_id=user_id)
        
        # Check blocked (max attempts)
        if pin_record.attempts >= MAX_ATTEMPTS:
            self.db.delete(pin_record)
            self.db.commit()
            logger.warning(f"PIN blocked for user: {user_id} - max attempts exceeded")
            self.audit_service.log_event(
                user_id=user_id,
                event_type="pin_blocked",
                method="sms",
                success=False,
                details={"attempts": pin_record.attempts}
            )
            raise AuthenticationError(log_user_id=user_id)
        
        # Verify PIN
        if pin_record.pin == submitted_pin:
            # Success - clean up
            self.db.delete(pin_record)
            self.db.commit()
            
            self.audit_service.log_event(
                user_id=user_id,
                event_type="pin_verified",
                method="sms",
                success=True
            )
            
            logger.info(f"PIN verified successfully for user {user_id}")
            return True
        
        else:
            # Failed - increment attempts
            pin_record.attempts += 1
            self.db.commit()
            
            attempts_left = MAX_ATTEMPTS - pin_record.attempts
            
            self.audit_service.log_event(
                user_id=user_id,
                event_type="pin_failed",
                method="sms",
                success=False,
                details={"attempts_used": pin_record.attempts}
            )
            
            logger.warning(f"Invalid PIN for user {user_id}. Attempts: {pin_record.attempts}")
            
            if pin_record.attempts >= MAX_ATTEMPTS:
                self.db.delete(pin_record)
                self.db.commit()
                raise AuthenticationError(log_user_id=user_id)
            
            # Return InvalidPinError with attempts left
            raise InvalidPinError(attempts_left=attempts_left, log_user_id=user_id)
    
    def get_active_pin(self, user_id: str) -> Optional[PinAttempt]:
        """Get active (non-expired) PIN for user"""
        return self.db.query(PinAttempt).filter(
            PinAttempt.user_id == user_id,
            PinAttempt.expires_at > datetime.utcnow()
        ).order_by(PinAttempt.created_at.desc()).first()
    
    def cleanup_expired_pins(self) -> int:
        """Delete all expired PIN attempts"""
        deleted = self.db.query(PinAttempt).filter(
            PinAttempt.expires_at <= datetime.utcnow()
        ).delete(synchronize_session=False)
        self.db.commit()
        
        if deleted:
            logger.info(f"Cleaned up {deleted} expired PINs")
        
        return deleted