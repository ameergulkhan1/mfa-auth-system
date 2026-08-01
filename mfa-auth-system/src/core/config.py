"""
Application configuration using Pydantic Settings
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field, ValidationError
import os


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/mfa_db",
        description="PostgreSQL connection string"
    )
    
    # Security - REQUIRED from environment
    secret_key: SecretStr = Field(
        ...,
        description="JWT signing key - MUST be set in environment",
        min_length=32
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    jwt_expiry_hours: int = Field(
        default=24,
        description="JWT token expiry in hours"
    )
    
    # MFA Settings
    pin_expiry_minutes: int = Field(
        default=5,
        description="PIN expiry duration in minutes"
    )
    max_pin_attempts: int = Field(
        default=3,
        description="Maximum PIN verification attempts"
    )
    pin_length: int = Field(
        default=6,
        description="PIN code length"
    )
    
    # Server
    host: str = Field(
        default="0.0.0.0",
        description="Server host"
    )
    port: int = Field(
        default=8000,
        description="Server port"
    )
    environment: str = Field(
        default="development",
        description="Environment (development/test/production)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Firebase (mock for now)
    firebase_credentials: Optional[str] = Field(
        default=None,
        description="Path to Firebase service account JSON"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        
        @classmethod
        def validate_secret_key(cls, v):
            """Ensure secret_key is set in production"""
            if not v or len(str(v)) < 32:
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters long "
                    "and set in environment"
                )
            return v


# Initialize settings
try:
    settings = Settings()
except ValidationError as e:
    print("❌ Configuration Error:")
    print("Please set SECRET_KEY in your .env file or environment")
    print("Example: SECRET_KEY=your-strong-secret-key-min-32-chars")
    raise