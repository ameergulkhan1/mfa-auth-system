"""
Background cleanup service for expired PINs
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from src.db.session import SessionLocal
from src.models.pin_attempt import PinAttempt

logger = logging.getLogger(__name__)


class CleanupService:
    """Background service to clean up expired PIN attempts"""
    
    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self._cleanup_count = 0
    
    async def start(self):
        """Start the cleanup background task"""
        if self.running:
            logger.warning("Cleanup service already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Cleanup service started (interval: {self.interval_seconds}s)")
    
    async def stop(self):
        """Stop the cleanup background task"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("Cleanup service stopped")
    
    async def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.running:
            try:
                await self._cleanup()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _cleanup(self):
        """Perform the actual cleanup"""
        db: Optional[Session] = None
        try:
            db = SessionLocal()
            
            # Delete expired PINs
            deleted = db.query(PinAttempt).filter(
                PinAttempt.expires_at <= datetime.utcnow()
            ).delete(synchronize_session=False)
            
            # Also clean very old entries (older than 1 hour)
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            old_deleted = db.query(PinAttempt).filter(
                PinAttempt.created_at <= one_hour_ago
            ).delete(synchronize_session=False)
            
            db.commit()
            
            total_deleted = deleted + old_deleted
            if total_deleted > 0:
                self._cleanup_count += total_deleted
                logger.info(f"Cleaned up {total_deleted} PIN attempts (expired: {deleted}, old: {old_deleted})")
            
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Cleanup failed: {e}")
            raise
        finally:
            if db:
                db.close()
    
    async def manual_cleanup(self) -> int:
        """Manually trigger cleanup and return count"""
        await self._cleanup()
        return self._cleanup_count
    
    def get_stats(self) -> dict:
        """Get cleanup service statistics"""
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "total_cleaned": self._cleanup_count,
            "task_active": self.task is not None and not self.task.done()
        }