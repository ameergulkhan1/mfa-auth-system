"""
Database initialization script - Fixed version
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.db.session import engine, Base
from src.models.user import User
from src.models.pin_attempt import PinAttempt
from src.models.audit_log import AuditLog
from src.core.config import settings
from src.utils.logger import setup_logging
import logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def setup_database():
    """Initialize database with all tables"""
    print("=" * 60)
    print("MFA Authentication System - Database Setup")
    print("=" * 60)
    print(f"Database URL: {settings.database_url}")
    print()
    
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        
        # Verify connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✅ Database connection verified")
        
        # Show tables
        with engine.connect() as conn:
            tables = conn.execute(
                text("SELECT table_name FROM information_schema.tables "
                     "WHERE table_schema = 'public'")
            )
            table_names = [row[0] for row in tables]
            print(f"\n📊 Tables created: {', '.join(table_names) if table_names else 'No tables found!'}")
        
        print()
        print("=" * 60)
        print("✅ Database setup complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        logger.error(f"Database setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    setup_database()