"""
Custom exceptions for the application
"""
from typing import Optional, Dict, Any


class MFAException(Exception):
    """Base exception for MFA system"""
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        log_user_id: Optional[str] = None  # For server-side logging only
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.log_user_id = log_user_id  # Never exposed to client
        super().__init__(message)


class AuthenticationError(MFAException):
    """
    Generic authentication error - same response for all failures
    Prevents user enumeration attacks
    """
    def __init__(self, log_user_id: Optional[str] = None):
        super().__init__(
            message="Invalid credentials or authentication failed",
            status_code=401,
            details={},
            log_user_id=log_user_id
        )


class InvalidPinError(MFAException):
    """Raised when PIN is invalid"""
    def __init__(self, attempts_left: int, log_user_id: Optional[str] = None):
        # Generic message - don't expose attempt count in production
        super().__init__(
            message="Invalid PIN. Please try again.",
            status_code=401,
            details={"attempts_left": attempts_left},  # Safe to expose
            log_user_id=log_user_id
        )


class PinExpiredError(MFAException):
    """Raised when PIN has expired"""
    def __init__(self, log_user_id: Optional[str] = None):
        super().__init__(
            message="PIN has expired. Please request a new one.",
            status_code=401,  # Use 401 not 400
            log_user_id=log_user_id
        )


class PinBlockedError(MFAException):
    """Raised when max attempts exceeded"""
    def __init__(self, log_user_id: Optional[str] = None):
        super().__init__(
            message="Too many failed attempts. Please request a new PIN.",
            status_code=401,  # Use 401 not 403
            log_user_id=log_user_id
        )


# REMOVED: UserNotFoundError - replaced with generic AuthenticationError
# to prevent user enumeration


class RateLimitExceededError(MFAException):
    """Raised when rate limit exceeded"""
    def __init__(self, message: str = "Too many requests. Please wait."):
        super().__init__(
            message=message,
            status_code=429
        )