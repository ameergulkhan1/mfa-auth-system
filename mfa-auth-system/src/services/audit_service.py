"""
Audit logging service
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from src.models.audit_log import AuditLog
from src.core.constants import (
    EVENT_LOGIN_REQUEST,
    EVENT_PIN_GENERATED,
    EVENT_PIN_SENT,
    EVENT_PIN_VERIFIED,
    EVENT_PIN_EXPIRED,
    EVENT_PIN_FAILED,
    EVENT_PIN_BLOCKED,
    EVENT_AUTH_FAILED
)
import logging

logger = logging.getLogger(__name__)


class AuditService:
    """Service for logging authentication events"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_event(
        self,
        user_id: Optional[str],
        event_type: str,
        method: Optional[str] = None,
        success: Optional[bool] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Create an audit log entry
        
        Args:
            user_id: User ID (can be None for non-existent users)
            event_type: Type of event (from constants)
            method: Authentication method (sms, totp)
            success: Whether the event was successful
            details: Additional details
            ip_address: Client IP address
            user_agent: Client user agent
        
        Returns:
            AuditLog: Created audit log entry
        """
        # Validate event_type
        valid_events = [
            EVENT_LOGIN_REQUEST,
            EVENT_PIN_GENERATED,
            EVENT_PIN_SENT,
            EVENT_PIN_VERIFIED,
            EVENT_PIN_EXPIRED,
            EVENT_PIN_FAILED,
            EVENT_PIN_BLOCKED,
            EVENT_AUTH_FAILED,
            "user_registered",
            "user_login",
            "pin_send_failed",
            "pin_verification_failed",
            "pin_request_failed"
        ]
        
        if event_type not in valid_events:
            logger.warning(f"Unknown event type: {event_type}")
        
        # Create log entry
        audit_log = AuditLog.create_log(
            user_id=user_id,
            event_type=event_type,
            method=method,
            success=success,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        # Log to console as well (without exposing sensitive data)
        log_message = f"Audit: {event_type} | User: {user_id or 'anonymous'} | Success: {success}"
        if method:
            log_message += f" | Method: {method}"
        
        if success is False:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        return audit_log
    
    def get_user_audit_trail(
        self,
        user_id: str,
        limit: int = 100,
        event_type: Optional[str] = None
    ) -> List[AuditLog]:
        """
        Get audit trail for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of entries
            event_type: Filter by event type
        
        Returns:
            List[AuditLog]: List of audit logs
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    def get_recent_failures(
        self,
        user_id: str,
        minutes: int = 15,
        max_attempts: int = 5
    ) -> int:
        """
        Get number of recent failed attempts for rate limiting
        
        Args:
            user_id: User ID
            minutes: Time window in minutes
            max_attempts: Maximum attempts before rate limiting
        
        Returns:
            int: Number of recent failures
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        count = self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.success == False,
            AuditLog.timestamp >= cutoff,
            AuditLog.event_type.in_([
                EVENT_PIN_FAILED,
                EVENT_PIN_EXPIRED,
                EVENT_PIN_BLOCKED,
                EVENT_AUTH_FAILED
            ])
        ).count()
        
        return count
    
    def is_rate_limited(
        self,
        user_id: str,
        minutes: int = 15,
        max_attempts: int = 5
    ) -> bool:
        """
        Check if user is rate limited
        
        Args:
            user_id: User ID
            minutes: Time window in minutes
            max_attempts: Maximum attempts before rate limiting
        
        Returns:
            bool: True if rate limited, False otherwise
        """
        failures = self.get_recent_failures(user_id, minutes, max_attempts)
        return failures >= max_attempts
    
    def get_login_metrics(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get login metrics for a user
        
        Args:
            user_id: User ID
            days: Number of days to analyze
        
        Returns:
            Dict: Login metrics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        total_logins = self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.event_type == EVENT_PIN_VERIFIED,
            AuditLog.timestamp >= cutoff
        ).count()
        
        failed_logins = self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id,
            AuditLog.success == False,
            AuditLog.timestamp >= cutoff
        ).count()
        
        return {
            "user_id": user_id,
            "days": days,
            "total_logins": total_logins,
            "failed_logins": failed_logins,
            "success_rate": total_logins / (total_logins + failed_logins) if (total_logins + failed_logins) > 0 else 0
        }
    
    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        Delete audit logs older than specified days
        
        Args:
            days: Number of days to keep
        
        Returns:
            int: Number of deleted records
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = self.db.query(AuditLog).filter(
            AuditLog.timestamp < cutoff
        ).delete(synchronize_session=False)
        self.db.commit()
        
        if deleted:
            logger.info(f"Cleaned up {deleted} audit logs older than {days} days")
        
        return deleted