"""
Unit test specific fixtures
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from src.services.pin_service import PinService
from src.models.user import User
from src.models.pin_attempt import PinAttempt


@pytest.fixture
def mock_db():
    """Mock database session for unit tests"""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Mock user for unit tests"""
    user = Mock(spec=User)
    user.id = "123e4567-e89b-12d3-a456-426614174000"
    user.phone = "+1234567890"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def mock_pin_attempt(mock_user):
    """Mock PIN attempt for unit tests"""
    from datetime import datetime, timedelta
    
    pin = Mock(spec=PinAttempt)
    pin.user_id = mock_user.id
    pin.pin = "123456"
    pin.attempts = 0
    pin.expires_at = datetime.utcnow() + timedelta(minutes=5)
    pin.is_expired = False
    pin.is_blocked = False
    pin.time_remaining = 300
    pin.attempts_left = 3
    pin.can_retry = True
    return pin


@pytest.fixture
def pin_service(mock_db):
    """Pin service instance for unit tests"""
    return PinService(mock_db)


@pytest.fixture
def valid_user_id():
    """Valid UUID for testing"""
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def invalid_user_id():
    """Invalid UUID for testing"""
    return "invalid-uuid"


@pytest.fixture
def valid_pin():
    """Valid 6-digit PIN"""
    return "123456"


@pytest.fixture
def invalid_pin():
    """Invalid PIN"""
    return "999999"


@pytest.fixture
def short_pin():
    """Short PIN (invalid)"""
    return "12345"


@pytest.fixture
def long_pin():
    """Long PIN (invalid)"""
    return "1234567"