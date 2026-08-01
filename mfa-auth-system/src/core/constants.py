"""
Application constants
"""
from enum import Enum


class LoginMethod(str, Enum):
    SMS = "sms"
    TOTP = "totp"


class LoginStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    BLOCKED = "blocked"


# PIN related constants
PIN_EXPIRY_SECONDS = 300  # 5 minutes
MAX_ATTEMPTS = 3
PIN_LENGTH = 6

# Cache keys
CACHE_KEY_PIN = "pin:{user_id}"
CACHE_KEY_ATTEMPTS = "attempts:{user_id}"

# Audit event types
EVENT_LOGIN_REQUEST = "login_request"
EVENT_PIN_GENERATED = "pin_generated"
EVENT_PIN_SENT = "pin_sent"
EVENT_PIN_VERIFIED = "pin_verified"
EVENT_PIN_EXPIRED = "pin_expired"
EVENT_PIN_FAILED = "pin_failed"
EVENT_PIN_BLOCKED = "pin_blocked"
EVENT_AUTH_FAILED = "auth_failed"  # Generic auth failure

# Security constants
MIN_SECRET_KEY_LENGTH = 32