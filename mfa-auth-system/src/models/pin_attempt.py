"""
PIN Attempt model for storing temporary PINs
"""
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.user import Base
import uuid


class PinAttempt(Base):
    __tablename__ = "pin_attempts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pin = Column(String(6), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)  # Added nullable=False
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", backref="pin_attempts")
    
    # Composite index for faster queries
    __table_args__ = (
        Index('idx_pin_user_expires', 'user_id', 'expires_at'),
    )
    
    def __init__(self, **kwargs):
        # Ensure attempts has a default value
        if 'attempts' not in kwargs:
            kwargs['attempts'] = 0
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    @property
    def is_expired(self) -> bool:
        """Check if PIN has expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_blocked(self) -> bool:
        """Check if attempts exceeded"""
        return self.attempts >= 3
    
    @property
    def time_remaining(self) -> int:
        """Seconds remaining before expiry"""
        remaining = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    @property
    def attempts_left(self) -> int:
        """Number of attempts remaining"""
        attempts = self.attempts or 0  # Handle None case
        return max(0, 3 - attempts)
    
    def increment_attempts(self) -> int:
        """Increment attempt counter and return new count"""
        self.attempts = (self.attempts or 0) + 1
        return self.attempts
    
    def can_retry(self) -> bool:
        """Check if user can retry"""
        return not self.is_expired and not self.is_blocked
    
    def __repr__(self):
        return f"<PinAttempt user={self.user_id} expires={self.expires_at} attempts={self.attempts}>"