"""
Input validation utilities
"""
import re
import uuid
from typing import Optional, Union
from datetime import datetime


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format
    Supports: +1234567890, 1234567890
    
    Args:
        phone: Phone number string
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone:
        return False
    
    # Remove spaces and special characters
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    # E.164 format: +[country code][number]
    # Minimum 10 digits, maximum 15 digits
    pattern = r'^\+?[1-9]\d{1,14}$'
    return bool(re.match(pattern, cleaned))


def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email string
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_pin(pin: str) -> bool:
    """
    Validate PIN format (6 digits)
    
    Args:
        pin: PIN string
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not pin:
        return False
    return bool(re.match(r'^\d{6}$', pin))


def validate_uuid(user_id: str) -> bool:
    """
    Validate UUID format
    
    Args:
        user_id: UUID string
    
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        uuid.UUID(user_id)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def sanitize_user_id(user_id: str) -> Optional[str]:
    """
    Sanitize and validate UUID, return None if invalid
    
    Args:
        user_id: UUID string
    
    Returns:
        Optional[str]: Validated UUID or None
    """
    try:
        uid = uuid.UUID(user_id)
        return str(uid)
    except (ValueError, AttributeError, TypeError):
        return None


def validate_ip_address(ip: str) -> bool:
    """
    Validate IPv4 or IPv6 address
    
    Args:
        ip: IP address string
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not ip:
        return False
    
    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip):
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    # IPv6 pattern (simplified)
    ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    if re.match(ipv6_pattern, ip):
        return True
    
    return False


def validate_required_string(value: str, min_length: int = 1, max_length: int = 255) -> bool:
    """
    Validate required string with length constraints
    
    Args:
        value: String to validate
        min_length: Minimum length
        max_length: Maximum length
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not value or not isinstance(value, str):
        return False
    return min_length <= len(value.strip()) <= max_length


def validate_expiry(expiry_minutes: int) -> bool:
    """
    Validate expiry minutes (must be between 1 and 60)
    
    Args:
        expiry_minutes: Expiry in minutes
    
    Returns:
        bool: True if valid, False otherwise
    """
    return 1 <= expiry_minutes <= 60


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data (e.g., phone, email)
    
    Args:
        data: String to mask
        visible_chars: Number of characters to show at the end
    
    Returns:
        str: Masked string
    """
    if not data:
        return ""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]