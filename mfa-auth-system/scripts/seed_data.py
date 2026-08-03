"""
Seed test data into database
"""
import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.db.session import SessionLocal, init_db, engine
from src.models.user import User
from src.models.pin_attempt import PinAttempt
from src.models.audit_log import AuditLog
from src.core.config import settings
from src.utils.logger import setup_logging
import logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def seed_users():
    """Add test users"""
    print("=" * 60)
    print("Seeding Test Data")
    print("=" * 60)
    
    db = SessionLocal()
    
    test_users = [
        {
            "phone": "+1234567890",
            "email": "alice@example.com",
            "is_active": True
        },
        {
            "phone": "+1987654321",
            "email": "bob@example.com",
            "is_active": True
        },
        {
            "phone": "+1122334455",
            "email": "charlie@example.com",
            "is_active": True
        },
        {
            "phone": "+1555666777",
            "email": "diana@example.com",
            "is_active": False  # Inactive user for testing
        }
    ]
    
    created = 0
    for user_data in test_users:
        # Check if user already exists
        existing = db.query(User).filter(
            (User.phone == user_data["phone"]) | 
            (User.email == user_data["email"])
        ).first()
        
        if existing:
            print(f"⏭️  Skipping existing user: {user_data['email']}")
            continue
        
        user = User(**user_data)
        db.add(user)
        created += 1
    
    db.commit()
    
    if created > 0:
        print(f"✅ Created {created} test users")
    else:
        print("ℹ️  No new users to create")
    
    # Show existing users
    users = db.query(User).all()
    print(f"\n📊 Total users in database: {len(users)}")
    for user in users:
        status = "Active" if user.is_active else "Inactive"
        print(f"   - {user.email} ({user.phone}) - {status}")
    
    db.close()
    return created


def seed_audit_logs():
    """Add sample audit logs for testing"""
    db = SessionLocal()
    
    # Get existing users
    users = db.query(User).limit(2).all()
    if not users:
        print("ℹ️  No users found to create audit logs")
        db.close()
        return 0
    
    created = 0
    for user in users:
        # Create sample logs
        sample_logs = [
            {
                "user_id": user.id,
                "event_type": "user_login",
                "success": True,
                "details": {"ip": "192.168.1.1"}
            },
            {
                "user_id": user.id,
                "event_type": "pin_generated",
                "success": True,
                "details": {"expires_in": 300}
            },
            {
                "user_id": user.id,
                "event_type": "pin_verified",
                "success": True,
                "details": {"attempts_used": 1}
            },
            {
                "user_id": user.id,
                "event_type": "pin_failed",
                "success": False,
                "details": {"attempts_used": 1}
            }
        ]
        
        for log_data in sample_logs:
            log = AuditLog(**log_data)
            db.add(log)
            created += 1
    
    db.commit()
    db.close()
    
    if created > 0:
        print(f"✅ Created {created} sample audit logs")
    
    return created


def cleanup_database():
    """Delete all test data (use with caution)"""
    print("\n⚠️  This will delete all data from the database!")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() != 'yes':
        print("❌ Cleanup cancelled")
        return
    
    db = SessionLocal()
    
    # Delete in correct order (due to foreign keys)
    count_pins = db.query(PinAttempt).delete()
    count_logs = db.query(AuditLog).delete()
    count_users = db.query(User).delete()
    
    db.commit()
    db.close()
    
    print(f"✅ Cleaned up: {count_users} users, {count_pins} PINs, {count_logs} logs")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MFA Authentication System - Data Seeder")
    print("=" * 60)
    
    # Ensure database exists
    try:
        init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)
    
    # Seed data
    seed_users()
    seed_audit_logs()
    
    print("\n" + "=" * 60)
    print("✅ Seeding complete!")
    print("=" * 60)
    
    # Optional cleanup
    print("\nPress Ctrl+C to exit, or run with --cleanup to delete data")