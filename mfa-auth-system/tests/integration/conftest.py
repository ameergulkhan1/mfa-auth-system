"""
Integration test specific fixtures
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from src.main import app


@pytest.fixture
def client():
    """Test client for integration tests"""
    return TestClient(app)


@pytest.fixture
def auth_headers(test_user):
    """Generate auth headers for authenticated requests"""
    # This would need JWT token generation
    # For now, return empty headers
    return {}


@pytest.fixture
def valid_user_data():
    """Valid user registration data"""
    return {
        "phone": "+1234567890",
        "email": "integration@example.com"
    }


@pytest.fixture
def duplicate_user_data(test_user):
    """Duplicate user data"""
    return {
        "phone": test_user.phone,
        "email": test_user.email
    }


@pytest.fixture
def invalid_user_data():
    """Invalid user registration data"""
    return {
        "phone": "invalid-phone",
        "email": "invalid-email"
    }


@pytest.fixture
def valid_pin_data():
    """Valid PIN verification data"""
    return {
        "pin": "123456"
    }


@pytest.fixture
def invalid_pin_data():
    """Invalid PIN verification data"""
    return {
        "pin": "999999"
    }