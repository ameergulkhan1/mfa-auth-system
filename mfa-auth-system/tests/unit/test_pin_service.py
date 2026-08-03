"""
Unit tests for PIN service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from src.services.pin_service import PinService
from src.models.pin_attempt import PinAttempt
from src.models.user import User
from src.core.exceptions import (
    InvalidPinError,
    AuthenticationError
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def pin_service(mock_db):
    """Pin service instance"""
    return PinService(mock_db)


@pytest.fixture
def test_user():
    """Test user fixture"""
    user = User(
        id="123e4567-e89b-12d3-a456-426614174000",
        phone="+1234567890",
        email="test@example.com",
        is_active=True
    )
    return user


@pytest.fixture
def test_pin_attempt(test_user):
    """Test PIN attempt fixture"""
    return PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        attempts=0
    )


def test_generate_pin(pin_service):
    """Test PIN generation"""
    pin = pin_service.generate_pin()
    assert len(pin) == 6
    assert pin.isdigit()
    # Test multiple generations
    pins = {pin_service.generate_pin() for _ in range(100)}
    assert len(pins) > 1  # Should generate different pins


def test_create_pin_attempt_success(pin_service, mock_db, test_user):
    """Test creating a PIN attempt for existing user"""
    # Mock user query
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first.return_value = test_user
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    pin_attempt, pin_code = pin_service.create_pin_attempt(str(test_user.id))
    
    assert pin_attempt.user_id == test_user.id
    assert len(pin_code) == 6
    assert pin_attempt.attempts == 0
    assert pin_attempt.expires_at > datetime.utcnow()
    assert pin_attempt.pin == pin_code
    
    # Verify database operations
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


def test_create_pin_attempt_user_not_found(pin_service, mock_db):
    """Test creating PIN for non-existent user (should return mock)"""
    # Mock user query returns None
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter.first.return_value = None
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    pin_attempt, pin_code = pin_service.create_pin_attempt("non-existent-user")
    
    # Should still return a mock PIN
    assert pin_attempt is not None
    assert len(pin_code) == 6
    # Should NOT add to database
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


def test_verify_pin_success(pin_service, mock_db, test_user, test_pin_attempt):
    """Test successful PIN verification"""
    # Mock PIN query
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = test_pin_attempt
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    # Verify
    result = pin_service.verify_pin(str(test_user.id), "123456")
    
    assert result is True
    mock_db.delete.assert_called_once()
    mock_db.commit.assert_called()


def test_verify_pin_no_active_pin(pin_service, mock_db, test_user):
    """Test verification when no active PIN exists"""
    # Mock query returns None
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = None
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    with pytest.raises(AuthenticationError):
        pin_service.verify_pin(str(test_user.id), "123456")


def test_verify_pin_expired(pin_service, mock_db, test_user):
    """Test verifying expired PIN"""
    # Create expired PIN
    expired_pin = PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        attempts=0
    )
    
    # Mock query returns expired PIN
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = expired_pin
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    with pytest.raises(AuthenticationError):
        pin_service.verify_pin(str(test_user.id), "123456")
    
    # Should delete expired PIN
    mock_db.delete.assert_called_once()
    mock_db.commit.assert_called()


def test_verify_pin_blocked(pin_service, mock_db, test_user):
    """Test verifying blocked PIN (max attempts exceeded)"""
    # Create blocked PIN
    blocked_pin = PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        attempts=3  # Max attempts reached
    )
    
    # Mock query returns blocked PIN
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = blocked_pin
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    with pytest.raises(AuthenticationError):
        pin_service.verify_pin(str(test_user.id), "123456")
    
    # Should delete blocked PIN
    mock_db.delete.assert_called_once()
    mock_db.commit.assert_called()


def test_verify_pin_invalid(pin_service, mock_db, test_user, test_pin_attempt):
    """Test verifying invalid PIN"""
    # Mock query returns PIN
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = test_pin_attempt
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    with pytest.raises(InvalidPinError) as exc_info:
        pin_service.verify_pin(str(test_user.id), "999999")
    
    assert test_pin_attempt.attempts == 1
    mock_db.commit.assert_called()
    assert exc_info.value.details["attempts_left"] == 2


def test_verify_pin_max_attempts(pin_service, mock_db, test_user):
    """Test verification when max attempts reached"""
    # Create PIN with 2 attempts (one more will reach max)
    pin_attempt = PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        attempts=2
    )
    
    # Mock query returns PIN
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = pin_attempt
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    with pytest.raises(AuthenticationError):
        pin_service.verify_pin(str(test_user.id), "999999")
    
    assert pin_attempt.attempts == 3
    mock_db.delete.assert_called_once()
    mock_db.commit.assert_called()


def test_cleanup_expired_pins(pin_service, mock_db):
    """Test cleanup of expired PINs"""
    # Mock delete returns 5
    mock_delete = Mock()
    mock_delete.delete.return_value = 5
    mock_db.query.return_value = mock_delete
    
    deleted = pin_service.cleanup_expired_pins()
    
    assert deleted == 5
    mock_db.commit.assert_called()


def test_get_active_pin(pin_service, mock_db, test_pin_attempt):
    """Test getting active PIN"""
    mock_query = Mock()
    mock_filter = Mock()
    mock_order = Mock()
    mock_order.first.return_value = test_pin_attempt
    mock_filter.order_by.return_value = mock_order
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    
    result = pin_service.get_active_pin(str(test_pin_attempt.user_id))
    
    assert result == test_pin_attempt