"""
Unit tests for TOTP service
"""
import pytest
from unittest.mock import Mock, patch
from src.services.totp_service import TOTPService
from src.core.qr_generator import QRGenerator


class TestTOTPService:
    """Test TOTP service functionality"""
    
    def test_generate_secret(self):
        """Test TOTP secret generation"""
        secret = TOTPService.generate_secret()
        assert secret is not None
        assert len(secret) >= 16
        assert secret.isalnum()
    
    def test_get_totp_uri(self):
        """Test TOTP URI generation"""
        secret = TOTPService.generate_secret()
        email = "test@example.com"
        issuer = "TestApp"
        
        uri = TOTPService.get_totp_uri(secret, email, issuer)
        
        assert "otpauth://totp/" in uri
        assert email in uri
        assert issuer in uri
        assert "secret=" + secret in uri
    
    def test_verify_totp_valid(self):
        """Test valid TOTP verification"""
        secret = TOTPService.generate_secret()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        
        result = TOTPService.verify_totp(secret, current_code)
        assert result is True
    
    def test_verify_totp_invalid(self):
        """Test invalid TOTP verification"""
        secret = TOTPService.generate_secret()
        result = TOTPService.verify_totp(secret, "999999")
        assert result is False
    
    def test_verify_totp_empty_secret(self):
        """Test TOTP verification with empty secret"""
        result = TOTPService.verify_totp("", "123456")
        assert result is False
    
    def test_verify_totp_empty_code(self):
        """Test TOTP verification with empty code"""
        secret = TOTPService.generate_secret()
        result = TOTPService.verify_totp(secret, "")
        assert result is False
    
    def test_get_current_code(self):
        """Test getting current TOTP code"""
        secret = TOTPService.generate_secret()
        code = TOTPService.get_current_code(secret)
        assert code is not None
        assert len(code) == 6
        assert code.isdigit()
    
    def test_generate_backup_codes(self):
        """Test backup code generation"""
        codes = TOTPService.generate_backup_codes(10)
        assert len(codes) == 10
        for code in codes:
            assert len(code) == 8
            assert code.isdigit()
    
    def test_format_secret_for_display(self):
        """Test secret formatting"""
        secret = "ABCDEFGHIJKLMNOP"
        formatted = TOTPService.format_secret_for_display(secret)
        assert formatted == "ABCD EFGH IJKL MNOP"
    
    def test_format_secret_empty(self):
        """Test formatting empty secret"""
        formatted = TOTPService.format_secret_for_display("")
        assert formatted == ""


class TestQRGenerator:
    """Test QR code generator"""
    
    def test_generate_qr_code(self):
        """Test QR code generation"""
        uri = "otpauth://totp/test@example.com?secret=ABCDEFGHIJKLMNOP"
        qr_data = QRGenerator.generate_qr_code(uri)
        assert qr_data is not None
        assert len(qr_data) > 0
    
    def test_generate_qr_code_data_uri(self):
        """Test QR code data URI generation"""
        uri = "otpauth://totp/test@example.com?secret=ABCDEFGHIJKLMNOP"
        data_uri = QRGenerator.generate_qr_code_data_uri(uri)
        assert data_uri.startswith("data:image/png;base64,")
        assert len(data_uri) > 100