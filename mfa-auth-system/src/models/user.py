"""
User model for authentication
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    totp_secret = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_phone_email', 'phone', 'email'),
    )
    
    def __repr__(self):
        return f"<User {self.id}>"  # Don't expose email/phone in repr
    
    def to_dict(self) -> dict:
        """Full user data (for internal use)"""
        return {
            "id": str(self.id),
            "phone": self.phone,
            "email": self.email,
            "is_active": self.is_active,
            "totp_secret": self.totp_secret,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_public_dict(self) -> dict:
        """Public representation - exclude sensitive data"""
        return {
            "id": str(self.id),
            "phone": self._mask_phone(),
            "email": self._mask_email(),
            "is_active": self.is_active
        }
    
    def _mask_phone(self) -> str:
        """Mask phone number for security"""
        if not self.phone:
            return ""
        if len(self.phone) > 4:
            return "***" + self.phone[-4:]
        return "***" + self.phone
    
    def _mask_email(self) -> str:
        """Mask email for security"""
        if not self.email:
            return ""
        local, domain = self.email.split('@')
        if len(local) > 3:
            masked_local = local[:2] + '***' + local[-1]
        else:
            masked_local = '***'
        return f"{masked_local}@{domain}"