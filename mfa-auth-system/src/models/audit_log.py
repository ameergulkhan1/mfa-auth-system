"""
Audit log model for tracking authentication events
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from src.models.user import Base
import uuid


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    method = Column(String(20), nullable=True)  # sms, totp
    success = Column(Boolean, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(JSON, default={})
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_audit_user_event', 'user_id', 'event_type'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.event_type} user={self.user_id} at {self.timestamp}>"
    
    @classmethod
    def create_log(
        cls,
        user_id: Optional[str],
        event_type: str,
        method: Optional[str] = None,
        success: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Factory method to create audit log entry"""
        return cls(
            user_id=user_id,
            event_type=event_type,
            method=method,
            success=success,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def to_dict(self) -> dict:
        """Convert audit log to dictionary"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "event_type": self.event_type,
            "method": self.method,
            "success": self.success,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def get_recent_failures(cls, user_id: str, minutes: int = 15):
        """Get recent failed attempts for rate limiting"""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return cls.query.filter(
            cls.user_id == user_id,
            cls.success == False,
            cls.timestamp >= cutoff
        ).count()