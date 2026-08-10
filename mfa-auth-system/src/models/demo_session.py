"""
Demo Session Model - For tracking MFA comparison demonstrations
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.user import Base
import uuid


class DemoSession(Base):
    """Track MFA comparison demo sessions"""
    
    __tablename__ = "demo_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Session details
    session_type = Column(String(50), nullable=False)  # 'comparison', 'sms_only', 'totp_only'
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    sms_attempted = Column(Boolean, default=False)
    sms_success = Column(Boolean, default=False)
    sms_time_ms = Column(Float, nullable=True)
    sms_attempts = Column(Integer, default=0)
    
    totp_attempted = Column(Boolean, default=False)
    totp_success = Column(Boolean, default=False)
    totp_time_ms = Column(Float, nullable=True)
    totp_attempts = Column(Integer, default=0)
    
    # Winner
    winner = Column(String(20), nullable=True)  # 'sms', 'totp', 'tie'
    
    # User feedback (optional)
    user_feedback = Column(String(500), nullable=True)
    user_rating = Column(Integer, nullable=True)  # 1-5
    
    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    metadata = Column(JSON, default={})
    
    # Relationship
    user = relationship("User", backref="demo_sessions")
    
    def __repr__(self):
        return f"<DemoSession user={self.user_id} winner={self.winner}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "session_type": self.session_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "sms": {
                "attempted": self.sms_attempted,
                "success": self.sms_success,
                "time_ms": self.sms_time_ms,
                "attempts": self.sms_attempts
            },
            "totp": {
                "attempted": self.totp_attempted,
                "success": self.totp_success,
                "time_ms": self.totp_time_ms,
                "attempts": self.totp_attempts
            },
            "winner": self.winner,
            "rating": self.user_rating,
            "feedback": self.user_feedback
        }