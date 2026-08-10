"""
MFA Comparison Service - Compare SMS PIN vs TOTP
"""
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session

from src.services.pin_service import PinService
from src.services.totp_service import TOTPService
from src.services.audit_service import AuditService
from src.models.user import User
from src.models.pin_attempt import PinAttempt

logger = logging.getLogger(__name__)


@dataclass
class MFAComparisonResult:
    """Comparison result for a single method"""
    method: str
    success: bool
    time_taken_ms: float
    attempts: int
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class MFAComparisonReport:
    """Full comparison report"""
    user_id: str
    user_email: str
    sms_result: MFAComparisonResult
    totp_result: MFAComparisonResult
    winner: str
    summary: str
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "user_email": self.user_email,
            "timestamp": self.timestamp,
            "sms": asdict(self.sms_result),
            "totp": asdict(self.totp_result),
            "winner": self.winner,
            "summary": self.summary
        }


class MFAComparisonService:
    """Service to compare SMS PIN vs TOTP authentication"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pin_service = PinService(db)
        self.audit_service = AuditService(db)
    
    def compare_methods(
        self,
        user_id: str,
        sms_pin: str = None,
        totp_code: str = None
    ) -> MFAComparisonReport:
        """
        Compare SMS PIN and TOTP methods for a user
        
        Args:
            user_id: User ID
            sms_pin: SMS PIN to verify (if None, will simulate)
            totp_code: TOTP code to verify (if None, will simulate)
            
        Returns:
            MFAComparisonReport: Comparison results
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Test SMS PIN
        sms_result = self._test_sms_pin(user, sms_pin)
        
        # Test TOTP
        totp_result = self._test_totp(user, totp_code)
        
        # Determine winner
        winner = self._determine_winner(sms_result, totp_result)
        
        # Generate summary
        summary = self._generate_summary(sms_result, totp_result, user)
        
        report = MFAComparisonReport(
            user_id=str(user.id),
            user_email=user.email,
            sms_result=sms_result,
            totp_result=totp_result,
            winner=winner,
            summary=summary
        )
        
        # Audit log
        self.audit_service.log_event(
            user_id=user.id,
            event_type="mfa_comparison",
            method="comparison",
            success=True,
            details={
                "sms_success": sms_result.success,
                "totp_success": totp_result.success,
                "winner": winner,
                "sms_time_ms": sms_result.time_taken_ms,
                "totp_time_ms": totp_result.time_taken_ms
            }
        )
        
        logger.info(f"MFA comparison completed for user {user.id}, winner: {winner}")
        return report
    
    def _test_sms_pin(self, user: User, pin: Optional[str] = None) -> MFAComparisonResult:
        """Test SMS PIN authentication"""
        start_time = time.time()
        attempts = 0
        
        try:
            # Generate PIN if not provided
            if not pin:
                pin_attempt, pin = self.pin_service.create_pin_attempt(str(user.id))
                # In a real demo, we would show this PIN to the user
                logger.info(f"[DEMO] SMS PIN for {user.id}: {pin}")
            
            # Verify PIN
            success = self.pin_service.verify_pin(str(user.id), pin)
            
            return MFAComparisonResult(
                method="sms",
                success=success,
                time_taken_ms=(time.time() - start_time) * 1000,
                attempts=1
            )
            
        except Exception as e:
            return MFAComparisonResult(
                method="sms",
                success=False,
                time_taken_ms=(time.time() - start_time) * 1000,
                attempts=attempts,
                error=str(e)
            )
    
    def _test_totp(self, user: User, code: Optional[str] = None) -> MFAComparisonResult:
        """Test TOTP authentication"""
        start_time = time.time()
        attempts = 0
        
        try:
            if not user.is_totp_enabled or not user.totp_secret:
                return MFAComparisonResult(
                    method="totp",
                    success=False,
                    time_taken_ms=(time.time() - start_time) * 1000,
                    attempts=0,
                    error="TOTP not enabled for this user"
                )
            
            # Generate code if not provided
            if not code:
                code = TOTPService.get_current_code(user.totp_secret)
                logger.info(f"[DEMO] TOTP code for {user.id}: {code}")
            
            # Verify TOTP
            success = TOTPService.verify_totp(user.totp_secret, code)
            
            return MFAComparisonResult(
                method="totp",
                success=success,
                time_taken_ms=(time.time() - start_time) * 1000,
                attempts=1
            )
            
        except Exception as e:
            return MFAComparisonResult(
                method="totp",
                success=False,
                time_taken_ms=(time.time() - start_time) * 1000,
                attempts=attempts,
                error=str(e)
            )
    
    def _determine_winner(
        self,
        sms_result: MFAComparisonResult,
        totp_result: MFAComparisonResult
    ) -> str:
        """Determine which method performed better"""
        if sms_result.success and not totp_result.success:
            return "sms"
        elif totp_result.success and not sms_result.success:
            return "totp"
        elif not sms_result.success and not totp_result.success:
            return "none"
        else:
            # Both succeeded - compare speed
            if sms_result.time_taken_ms < totp_result.time_taken_ms:
                return "sms (faster)"
            elif totp_result.time_taken_ms < sms_result.time_taken_ms:
                return "totp (faster)"
            else:
                return "tie"
    
    def _generate_summary(
        self,
        sms_result: MFAComparisonResult,
        totp_result: MFAComparisonResult,
        user: User
    ) -> str:
        """Generate human-readable summary"""
        lines = []
        lines.append(f"MFA Comparison Report for {user.email}")
        lines.append("-" * 50)
        
        # SMS results
        lines.append(f"SMS PIN: {'✅ SUCCESS' if sms_result.success else '❌ FAILED'}")
        lines.append(f"  Time: {sms_result.time_taken_ms:.2f}ms")
        if sms_result.error:
            lines.append(f"  Error: {sms_result.error}")
        
        # TOTP results
        lines.append(f"TOTP: {'✅ SUCCESS' if totp_result.success else '❌ FAILED'}")
        lines.append(f"  Time: {totp_result.time_taken_ms:.2f}ms")
        if totp_result.error:
            lines.append(f"  Error: {totp_result.error}")
        
        # Winner
        lines.append("-" * 50)
        lines.append(f"🏆 Winner: {self._determine_winner(sms_result, totp_result)}")
        
        # Analysis
        if sms_result.success and totp_result.success:
            lines.append("✅ Both methods work!")
            lines.append("💡 SMS PIN is simpler but less secure (delivery issues)")
            lines.append("💡 TOTP is more secure but requires app setup")
        elif sms_result.success:
            lines.append("⚠️ SMS PIN works, TOTP failed")
            lines.append("💡 Consider enabling TOTP for better security")
        elif totp_result.success:
            lines.append("⚠️ TOTP works, SMS PIN failed")
            lines.append("💡 SMS delivery may have issues, TOTP is reliable")
        else:
            lines.append("❌ Both methods failed. Check user configuration.")
        
        return "\n".join(lines)
    
    def get_comparison_history(self, user_id: str, limit: int = 10) -> List[dict]:
        """Get comparison history for a user"""
        # This would query audit logs for comparison events
        logs = self.audit_service.get_user_audit_trail(
            user_id=user_id,
            limit=limit,
            event_type="mfa_comparison"
        )
        return [log.to_dict() for log in logs]
    
    def get_statistics(self) -> dict:
        """Get overall comparison statistics"""
        # This would aggregate data from audit logs
        return {
            "total_comparisons": 0,
            "sms_success_rate": 0.0,
            "totp_success_rate": 0.0,
            "faster_method": "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }