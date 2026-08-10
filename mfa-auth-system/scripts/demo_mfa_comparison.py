"""
MFA Comparison Demo Script
Run this to see a side-by-side comparison of SMS PIN vs TOTP
"""
import sys
import os
import time
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.session import SessionLocal
from src.models.user import User
from src.services.pin_service import PinService
from src.services.totp_service import TOTPService
from src.services.mfa_comparison_service import MFAComparisonService
from src.utils.logger import setup_logging

setup_logging()


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_result(method: str, success: bool, time_ms: float, error: str = None):
    """Print formatted result"""
    status = "✅ SUCCESS" if success else "❌ FAILED"
    print(f"\n  {method.upper()}: {status}")
    print(f"  Time: {time_ms:.2f}ms")
    if error:
        print(f"  Error: {error}")


def run_demo():
    """Run the MFA comparison demo"""
    print_header("MFA COMPARISON DEMO")
    print("Comparing SMS PIN vs TOTP Authentication")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Get a user
        user = db.query(User).filter(User.email == "alice@example.com").first()
        if not user:
            print("❌ User not found. Please seed the database first.")
            print("   Run: python scripts/seed_data.py")
            return
        
        print(f"\n📋 User: {user.email} (ID: {user.id})")
        print(f"   TOTP Enabled: {'✅' if user.is_totp_enabled else '❌'}")
        
        if not user.is_totp_enabled:
            print("\n⚠️  TOTP is not enabled for this user.")
            print("   Please enable TOTP first using the setup endpoint.")
            return
        
        print("\n" + "-" * 60)
        print("RUNNING COMPARISON...")
        print("-" * 60)
        
        # Run comparison
        comparison_service = MFAComparisonService(db)
        
        # Get SMS PIN (generate and show)
        pin_service = PinService(db)
        pin_attempt, sms_pin = pin_service.create_pin_attempt(str(user.id))
        print(f"\n📱 SMS PIN generated: {sms_pin}")
        
        # Get TOTP code
        totp_code = TOTPService.get_current_code(user.totp_secret)
        print(f"🔐 TOTP Code: {totp_code}")
        
        print("\n⏳ Verifying both methods...")
        time.sleep(1)
        
        # Run comparison
        report = comparison_service.compare_methods(
            user_id=str(user.id),
            sms_pin=sms_pin,
            totp_code=totp_code
        )
        
        # Print results
        print_header("RESULTS")
        
        print_result(
            "SMS PIN",
            report.sms_result.success,
            report.sms_result.time_taken_ms,
            report.sms_result.error
        )
        
        print_result(
            "TOTP",
            report.totp_result.success,
            report.totp_result.time_taken_ms,
            report.totp_result.error
        )
        
        print("\n" + "-" * 60)
        print(f"🏆 WINNER: {report.winner}")
        print("-" * 60)
        
        # Print summary
        print("\n📊 SUMMARY:")
        print(report.summary)
        
        # Recommendations
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        
        if report.sms_result.success and report.totp_result.success:
            print("✅ Both methods work!")
            print("\n💡 Use TOTP as primary authentication:")
            print("   - More secure (time-based, no delivery issues)")
            print("   - Works offline")
            print("   - No SMS delivery delays")
            print("\n💡 Keep SMS PIN as backup:")
            print("   - In case user loses authenticator app")
            print("   - Simple fallback method")
        elif report.sms_result.success:
            print("⚠️ SMS PIN works, but TOTP failed")
            print("\n💡 Enable TOTP for better security")
            print("   - TOTP is not vulnerable to SIM swap")
            print("   - No dependency on cellular network")
        elif report.totp_result.success:
            print("⚠️ TOTP works, but SMS PIN failed")
            print("\n💡 Check SMS delivery issues:")
            print("   - Verify phone number is correct")
            print("   - Check if SMS gateway is working")
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        
        # Save to JSON
        output_file = f"comparison_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\n💾 Report saved to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


def quick_stats():
    """Show quick statistics about MFA methods"""
    print_header("MFA QUICK STATS")
    
    # SMS PIN stats
    print("\n📱 SMS PIN:")
    print("   - Generated by server")
    print("   - Sent via SMS/Email")
    print("   - Expires in 5 minutes")
    print("   - 3 attempt limit")
    print("   - ⚠️  Vulnerability: SIM swap, delivery issues")
    
    # TOTP stats
    print("\n🔐 TOTP:")
    print("   - Generated by authenticator app")
    print("   - Time-based (30 second windows)")
    print("   - No delivery required")
    print("   - No expiry (unless reset)")
    print("   - ✅ More secure, offline capable")
    
    print("\n📊 Comparison:")
    print("   - SMS: Simple, any phone, but less secure")
    print("   - TOTP: More secure, but requires app setup")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MFA Comparison Demo")
    parser.add_argument("--stats", action="store_true", help="Show quick stats only")
    args = parser.parse_args()
    
    if args.stats:
        quick_stats()
    else:
        run_demo()