"""
MFA Comparison API Routes - Compare SMS PIN vs TOTP
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
import logging

from src.db.session import get_db
from src.models.user import User
from src.services.mfa_comparison_service import MFAComparisonService
from src.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/comparison", tags=["mfa-comparison"])


# ---------- Request/Response Models ----------
class ComparisonRequest(BaseModel):
    user_id: str = Field(..., description="User ID for comparison")
    sms_pin: Optional[str] = Field(None, description="SMS PIN to verify (optional)")
    totp_code: Optional[str] = Field(None, description="TOTP code to verify (optional)")


class ComparisonResponse(BaseModel):
    user_id: str
    user_email: str
    timestamp: str
    sms: dict
    totp: dict
    winner: str
    summary: str


class DemoSessionRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    session_type: str = Field(..., description="Session type: comparison, sms_only, totp_only")
    rating: Optional[int] = Field(None, ge=1, le=5, description="User rating 1-5")
    feedback: Optional[str] = Field(None, max_length=500, description="User feedback")


# ---------- Routes ----------
@router.post("/run", response_model=ComparisonResponse)
async def run_comparison(
    request: ComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    Run a comparison between SMS PIN and TOTP
    
    Demonstrates the strengths and weaknesses of each method
    """
    # Check if user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Run comparison
    comparison_service = MFAComparisonService(db)
    
    try:
        report = comparison_service.compare_methods(
            user_id=request.user_id,
            sms_pin=request.sms_pin,
            totp_code=request.totp_code
        )
        
        return ComparisonResponse(**report.to_dict())
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}"
        )


@router.get("/history/{user_id}")
async def get_comparison_history(
    user_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get comparison history for a user
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    comparison_service = MFAComparisonService(db)
    history = comparison_service.get_comparison_history(user_id, limit)
    
    return {
        "user_id": user_id,
        "user_email": user.email,
        "history": history
    }


@router.get("/statistics")
async def get_comparison_statistics(
    db: Session = Depends(get_db)
):
    """
    Get overall comparison statistics
    """
    comparison_service = MFAComparisonService(db)
    stats = comparison_service.get_statistics()
    
    return stats


@router.post("/demo-session")
async def create_demo_session(
    request: DemoSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a demo session (for tracking user interactions)
    """
    from src.models.demo_session import DemoSession
    
    # Check if user exists
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create demo session
    demo_session = DemoSession(
        user_id=request.user_id,
        session_type=request.session_type
    )
    
    db.add(demo_session)
    db.commit()
    db.refresh(demo_session)
    
    # Audit log
    audit = AuditService(db)
    audit.log_event(
        user_id=user.id,
        event_type="demo_session_created",
        method="demo",
        success=True,
        details={"session_type": request.session_type}
    )
    
    return {
        "session_id": str(demo_session.id),
        "message": "Demo session created successfully"
    }


@router.post("/demo-session/{session_id}/complete")
async def complete_demo_session(
    session_id: str,
    rating: Optional[int] = None,
    feedback: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Complete a demo session with user feedback
    """
    from src.models.demo_session import DemoSession
    
    session = db.query(DemoSession).filter(DemoSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo session not found"
        )
    
    # Update session
    session.completed_at = datetime.utcnow()
    if rating:
        session.user_rating = rating
    if feedback:
        session.user_feedback = feedback
    
    db.commit()
    
    return {
        "message": "Demo session completed successfully",
        "session_id": str(session.id)
    }


@router.get("/quick-demo")
async def quick_demo(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Quick demo - Shows comparison without actually running it
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return comparison info
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "has_totp": user.is_totp_enabled
        },
        "methods": [
            {
                "method": "sms",
                "description": "SMS PIN - Server-generated, delivered via SMS",
                "pros": ["Simple", "No app needed", "Works on any phone"],
                "cons": ["Delivery issues", "SIM swap attacks", "Network dependent"],
                "status": "available"
            },
            {
                "method": "totp",
                "description": "TOTP - Time-based codes from authenticator app",
                "pros": ["More secure", "Offline", "No delivery issues"],
                "cons": ["Requires app setup", "Time sync needed", "Phone dependency"],
                "status": "enabled" if user.is_totp_enabled else "setup_required"
            }
        ],
        "recommendation": "Use TOTP for security, SMS PIN as backup" if user.is_totp_enabled else "Enable TOTP for better security"
    }