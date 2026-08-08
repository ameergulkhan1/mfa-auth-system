"""
TOTP (Time-Based One-Time Password) Service
"""
import pyotp
import qrcode
from typing import Optional, Tuple, Dict
from datetime import datetime
import logging
from src.core.qr_generator import QRGenerator

logger = logging.getLogger(__name__)


class TOTPService:
    """Service for TOTP authentication"""
    
    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret key
        
        Returns:
            str: Base32 encoded secret
        """
        secret = pyotp.random_base32()
        logger.info("TOTP secret generated")
        return secret
    
    @staticmethod
    def get_totp_uri(secret: str, email: str, issuer: str = "MFA System") -> str:
        """
        Generate OTP authentication URI for QR code
        
        Args:
            secret: TOTP secret key
            email: User's email (used as account name)
            issuer: Service name
            
        Returns:
            str: OTP authentication URI (otpauth://)
        """
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=email, issuer_name=issuer)
        logger.info(f"TOTP URI generated for {email}")
        return uri
    
    @staticmethod
    def generate_qr_code_data(secret: str, email: str, issuer: str = "MFA System") -> Dict[str, str]:
        """
        Generate QR code for TOTP setup
        
        Args:
            secret: TOTP secret key
            email: User's email
            issuer: Service name
            
        Returns:
            dict: Contains QR code data URI and secret
        """
        uri = TOTPService.get_totp_uri(secret, email, issuer)
        qr_data_uri = QRGenerator.generate_qr_code_data_uri(uri)
        
        return {
            "qr_code": qr_data_uri,
            "secret": secret,
            "uri": uri
        }
    
    @staticmethod
    def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verify TOTP code
        
        Args:
            secret: TOTP secret key
            code: 6-digit code from authenticator app
            valid_window: Number of time steps before/after current time to accept
            
        Returns:
            bool: True if code is valid
        """
        if not secret or not code:
            logger.warning("Missing secret or code for TOTP verification")
            return False
        
        try:
            totp = pyotp.TOTP(secret)
            is_valid = totp.verify(code, valid_window=valid_window)
            
            if is_valid:
                logger.info("TOTP code verified successfully")
            else:
                logger.warning("Invalid TOTP code attempted")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False
    
    @staticmethod
    def get_current_code(secret: str) -> str:
        """
        Get current TOTP code (for testing)
        
        Args:
            secret: TOTP secret key
            
        Returns:
            str: Current 6-digit TOTP code
        """
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    @staticmethod
    def get_provisioning_uri(secret: str, email: str, issuer: str = "MFA System") -> str:
        """
        Get provisioning URI for manual entry
        
        Args:
            secret: TOTP secret key
            email: User's email
            issuer: Service name
            
        Returns:
            str: OTP authentication URI
        """
        return TOTPService.get_totp_uri(secret, email, issuer)
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> list:
        """
        Generate backup codes for account recovery
        
        Args:
            count: Number of backup codes to generate
            
        Returns:
            list: List of backup codes
        """
        import random
        import string
        
        codes = []
        for _ in range(count):
            code = ''.join(random.choices(string.digits, k=8))
            codes.append(code)
        
        logger.info(f"Generated {count} backup codes")
        return codes
    
    @staticmethod
    def format_secret_for_display(secret: str) -> str:
        """
        Format secret for display (add spaces every 4 characters)
        
        Args:
            secret: TOTP secret key
            
        Returns:
            str: Formatted secret
        """
        if not secret:
            return ""
        return ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])