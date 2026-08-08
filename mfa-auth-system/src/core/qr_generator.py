"""
QR Code Generator for TOTP Setup
"""
import qrcode
from qrcode.image.pil import PilImage
from io import BytesIO
import base64
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class QRGenerator:
    """Generate QR codes for TOTP authenticator setup"""
    
    @staticmethod
    def generate_qr_code(otp_uri: str, size: int = 300) -> str:
        """
        Generate QR code as base64 encoded image
        
        Args:
            otp_uri: OTP authentication URI (otpauth://)
            size: QR code size in pixels
            
        Returns:
            str: Base64 encoded PNG image
        """
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(otp_uri)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            logger.info("QR code generated successfully")
            return img_str
            
        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            raise
    
    @staticmethod
    def generate_qr_code_data_uri(otp_uri: str, size: int = 300) -> str:
        """
        Generate QR code as data URI for direct display in HTML
        
        Args:
            otp_uri: OTP authentication URI
            size: QR code size in pixels
            
        Returns:
            str: Data URI (data:image/png;base64,...)
        """
        img_base64 = QRGenerator.generate_qr_code(otp_uri, size)
        return f"data:image/png;base64,{img_base64}"
    
    @staticmethod
    def save_qr_code(otp_uri: str, filepath: str, size: int = 300) -> str:
        """
        Save QR code to file
        
        Args:
            otp_uri: OTP authentication URI
            filepath: Path to save the QR code
            size: QR code size in pixels
            
        Returns:
            str: File path where QR code was saved
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(otp_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(filepath, "PNG")
            
            logger.info(f"QR code saved to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save QR code: {e}")
            raise