"""
Custom exceptions for the application
"""
from typing import Optional


class MFAException(Exception):
    """Base exception for MFA system"""
    def __init__(self, message: str, status_code: int = 400, details: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class InvalidPinError(MFAException):
    """Raised when PIN is invalid"""
    def __init__(self, attempts_left: int, message: str = "Invalid PIN"):
        super().__init__(
            message=message,
            status_code=401,
            details={"attempts_left": attempts_left}
        )


class PinExpiredError(MFAException):
    """Raised when PIN has expired"""
    def __init__(self, message: str = "PIN has expired. Request a new one."):
        super().__init__(message=message, status_code=400)


class PinBlockedError(MFAException):
    """Raised when max attempts exceeded"""
    def __init__(self, message: str = "Too many failed attempts. Request a new PIN."):
        super().__init__(message=message, status_code=403)


class UserNotFoundError(MFAException):
    """Raised when user not found"""
    def __init__(self, user_id: str):
        super().__init__(
            message=f"User {user_id} not found",
            status_code=404
        )


class RateLimitExceededError(MFAException):
    """Raised when rate limit exceeded"""
    def __init__(self, message: str = "Too many requests. Please wait."):
        super().__init__(message=message, status_code=429)