"""
Database initialization script
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.session import init_db, engine
from src.models.user import Base
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
        init_db()
        print("✅ Database tables created successfully")
        
        # Verify connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print("✅ Database connection verified")
        
        # Show tables
        with engine.connect() as conn:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            table_names = [row[0] for row in tables]
            print(f"\n📊 Tables created: {', '.join(table_names)}")
        
        print()
        print("=" * 60)
        print("✅ Database setup complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        logger.error(f"Database setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_database()