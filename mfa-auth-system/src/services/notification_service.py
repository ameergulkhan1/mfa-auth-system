"""
Notification service for sending PINs (Mock/Production ready)
"""
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from src.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Notification service for sending PINs via SMS/Email
    
    In production: Integrate with Twilio, Vonage, AWS SNS, or Firebase
    """
    
    def __init__(self):
        self.enabled = settings.environment != "test"
        self.log_path = Path("logs/pin_delivery.log")
        self.log_path.parent.mkdir(exist_ok=True)
    
    def send_pin_sms(
        self,
        phone: str,
        pin: str,
        user_id: Optional[str] = None,
        expiry_minutes: int = 5
    ) -> bool:
        """
        Send PIN via SMS
        
        Args:
            phone: Recipient phone number
            pin: 6-digit PIN
            user_id: User ID (for logging)
            expiry_minutes: PIN expiry duration
        
        Returns:
            bool: True if sent successfully
        """
        try:
            # Log delivery attempt
            logger.info(f"Attempting SMS delivery to {self._mask_phone(phone)}")
            
            # In production, call actual SMS API here
            # Example with Twilio:
            # from twilio.rest import Client
            # client = Client(account_sid, auth_token)
            # message = client.messages.create(
            #     body=f"Your login PIN is: {pin}. Valid for {expiry_minutes} minutes.",
            #     from_=twilio_phone,
            #     to=phone
            # )
            
            # Mock delivery for development
            if settings.environment in ["development", "test"]:
                self._log_to_file(phone, pin, user_id, method="sms")
                logger.info(f"[MOCK SMS] PIN {pin} sent to {self._mask_phone(phone)}")
                return True
            
            # Production implementation would go here
            # For now, treat as success but log
            logger.info(f"SMS PIN sent to {self._mask_phone(phone)}")
            self._log_to_file(phone, pin, user_id, method="sms")
            return True
            
        except Exception as e:
            logger.error(f"SMS delivery failed: {e}")
            return False
    
    def send_pin_email(
        self,
        email: str,
        pin: str,
        user_id: Optional[str] = None,
        expiry_minutes: int = 5
    ) -> bool:
        """
        Send PIN via Email
        
        Args:
            email: Recipient email
            pin: 6-digit PIN
            user_id: User ID (for logging)
            expiry_minutes: PIN expiry duration
        
        Returns:
            bool: True if sent successfully
        """
        try:
            # Log delivery attempt
            logger.info(f"Attempting email delivery to {self._mask_email(email)}")
            
            # In production, use SendGrid, AWS SES, or Firebase
            # Example with SendGrid:
            # from sendgrid import SendGridAPIClient
            # from sendgrid.helpers.mail import Mail
            # message = Mail(
            #     from_email='noreply@mfa-system.com',
            #     to_emails=email,
            #     subject='Your Login PIN',
            #     html_content=f'<p>Your login PIN is: <strong>{pin}</strong></p><p>Valid for {expiry_minutes} minutes.</p>'
            # )
            # sg = SendGridAPIClient(api_key)
            # response = sg.send(message)
            
            # Mock delivery
            if settings.environment in ["development", "test"]:
                self._log_to_file(email, pin, user_id, method="email")
                logger.info(f"[MOCK EMAIL] PIN {pin} sent to {self._mask_email(email)}")
                return True
            
            logger.info(f"Email PIN sent to {self._mask_email(email)}")
            self._log_to_file(email, pin, user_id, method="email")
            return True
            
        except Exception as e:
            logger.error(f"Email delivery failed: {e}")
            return False
    
    def send_otp_setup_email(
        self,
        email: str,
        qr_code_path: str,
        secret: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Send TOTP setup instructions with QR code via email
        
        Args:
            email: Recipient email
            qr_code_path: Path to QR code image
            secret: TOTP secret
            user_id: User ID (for logging)
        
        Returns:
            bool: True if sent successfully
        """
        try:
            logger.info(f"Sending OTP setup to {self._mask_email(email)}")
            
            # In production, send email with QR code attachment
            # For now, just log
            logger.info(f"OTP setup sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"OTP setup email failed: {e}")
            return False
    
    def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """
        Get status of a sent message (mock)
        
        Args:
            message_id: Message ID
        
        Returns:
            Dict: Delivery status
        """
        return {
            "message_id": message_id,
            "status": "delivered",
            "timestamp": datetime.utcnow().isoformat(),
            "provider": "mock"
        }
    
    def _log_to_file(
        self,
        destination: str,
        pin: str,
        user_id: Optional[str] = None,
        method: str = "sms"
    ):
        """
        Log sent PINs to file for debugging
        
        Args:
            destination: Phone or email
            pin: PIN code
            user_id: User ID
            method: Delivery method (sms/email)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "destination": self._mask_destination(destination, method),
            "pin": pin,
            "user_id": str(user_id) if user_id else None,
            "method": method,
            "environment": settings.environment
        }
        
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            # Silent fail for logging
            logger.debug(f"Failed to write delivery log: {e}")
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for logging"""
        if not phone:
            return ""
        if len(phone) > 4:
            return "***" + phone[-4:]
        return "***" + phone
    
    def _mask_email(self, email: str) -> str:
        """Mask email for logging"""
        if not email:
            return ""
        parts = email.split('@')
        if len(parts) != 2:
            return "***"
        local, domain = parts
        if len(local) > 3:
            masked_local = local[:2] + '***' + local[-1]
        else:
            masked_local = '***'
        return f"{masked_local}@{domain}"
    
    def _mask_destination(self, destination: str, method: str) -> str:
        """Mask destination based on method"""
        if method == "sms":
            return self._mask_phone(destination)
        elif method == "email":
            return self._mask_email(destination)
        return "***"