"""
Integration tests for PIN endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import jwt

from src.main import app
from src.db.session import get_db, Base
from src.models.user import User
from src.models.pin_attempt import PinAttempt
from src.core.config import settings

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def override_get_db():
    """Override database dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user():
    """Create test user"""
    db = TestingSessionLocal()
    user = User(
        phone="+1234567890",
        email="test@example.com",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def test_inactive_user():
    """Create inactive test user"""
    db = TestingSessionLocal()
    user = User(
        phone="+1555666777",
        email="inactive@example.com",
        is_active=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_register_user():
    """Test user registration endpoint"""
    response = client.post(
        "/auth/register",
        json={
            "phone": "+1234567890",
            "email": "newuser@example.com"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["phone"] == "+1234567890"
    assert data["email"] == "newuser@example.com"


def test_register_duplicate_user(test_user):
    """Test registering duplicate user"""
    response = client.post(
        "/auth/register",
        json={
            "phone": test_user.phone,
            "email": test_user.email
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_request_pin(test_user):
    """Test requesting PIN"""
    response = client.post(
        "/auth/login/request",
        json={"user_id": str(test_user.id)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(test_user.id)
    assert "PIN sent" in data["message"]
    assert data["expiry_seconds"] == 300
    assert data["pin_sent"] is True


def test_request_pin_invalid_user():
    """Test requesting PIN for non-existent user (should succeed anyway)"""
    response = client.post(
        "/auth/login/request",
        json={"user_id": "123e4567-e89b-12d3-a456-426614174999"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "PIN sent" in data["message"]
    assert data["pin_sent"] is True


def test_verify_pin_success(test_user):
    """Test successful PIN verification"""
    # First, request PIN
    client.post("/auth/login/request", json={"user_id": str(test_user.id)})
    
    # Get the PIN from database
    db = TestingSessionLocal()
    pin_record = db.query(PinAttempt).filter(
        PinAttempt.user_id == test_user.id
    ).first()
    db.close()
    
    assert pin_record is not None
    
    # Verify PIN
    response = client.post(
        "/auth/verify/pin",
        json={
            "user_id": str(test_user.id),
            "pin": pin_record.pin
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert data["token"] is not None
    
    # Verify token is valid
    token = data["token"]
    payload = jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm]
    )
    assert payload["user_id"] == str(test_user.id)


def test_verify_pin_invalid(test_user):
    """Test invalid PIN verification"""
    # Request PIN
    client.post("/auth/login/request", json={"user_id": str(test_user.id)})
    
    # Wrong PIN
    response = client.post(
        "/auth/verify/pin",
        json={
            "user_id": str(test_user.id),
            "pin": "999999"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "attempts_left" in data
    assert data["attempts_left"] == 2


def test_verify_pin_expired(test_user):
    """Test expired PIN verification"""
    db = TestingSessionLocal()
    
    # Create expired PIN directly
    pin_attempt = PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
        attempts=0
    )
    db.add(pin_attempt)
    db.commit()
    db.close()
    
    response = client.post(
        "/auth/verify/pin",
        json={
            "user_id": str(test_user.id),
            "pin": "123456"
        }
    )
    
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_verify_pin_blocked(test_user):
    """Test blocked PIN verification (max attempts)"""
    db = TestingSessionLocal()
    
    # Create blocked PIN
    pin_attempt = PinAttempt(
        user_id=test_user.id,
        pin="123456",
        expires_at=datetime.utcnow() + timedelta(minutes=5),
        attempts=3  # Max attempts
    )
    db.add(pin_attempt)
    db.commit()
    db.close()
    
    response = client.post(
        "/auth/verify/pin",
        json={
            "user_id": str(test_user.id),
            "pin": "123456"
        }
    )
    
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


def test_pin_status(test_user):
    """Test PIN status endpoint"""
    # Request PIN
    client.post("/auth/login/request", json={"user_id": str(test_user.id)})
    
    response = client.get(f"/auth/pin/status/{test_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_pin"] is True
    assert data["expires_in"] > 0
    assert data["attempts_used"] == 0
    assert data["attempts_left"] == 3


def test_pin_status_no_pin(test_user):
    """Test PIN status when no PIN exists"""
    response = client.get(f"/auth/pin/status/{test_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["has_active_pin"] is False
    assert data["expires_in"] is None
    assert data["attempts_used"] is None
    assert data["attempts_left"] is None


def test_resend_pin(test_user):
    """Test resending PIN"""
    # First request
    client.post("/auth/login/request", json={"user_id": str(test_user.id)})
    
    # Resend
    response = client.post(f"/auth/pin/resend?user_id={test_user.id}")
    assert response.status_code == 200
    data = response.json()
    assert "PIN resent" in data["message"]
    assert data["expires_in"] == 300


def test_resend_pin_invalid_user():
    """Test resending PIN for invalid user"""
    response = client.post(
        "/auth/pin/resend?user_id=123e4567-e89b-12d3-a456-426614174999"
    )
    assert response.status_code == 200
    data = response.json()
    assert "PIN resent" in data["message"]


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "mfa-auth-system"
    assert data["version"] == "1.0.0"
    assert data["database"]["status"] == "healthy"


def test_health_ready():
    """Test readiness check"""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_health_live():
    """Test liveness check"""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "MFA Authentication System"
    assert data["version"] == "1.0.0"