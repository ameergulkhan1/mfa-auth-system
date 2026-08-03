"""
Structured logging setup
"""
import logging
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from src.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


def setup_logging(level: Optional[str] = None):
    """
    Configure application logging
    """
    log_level = level or settings.log_level
    
    # Create logs directory if not exists
    Path("logs").mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (JSON format in production, readable in development)
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.environment == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
    root_logger.addHandler(console_handler)
    
    # File handler (always JSON format)
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler('logs/error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # Set third-party log levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at {log_level} level")
    logger.info(f"Environment: {settings.environment}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


def log_with_extra(logger: logging.Logger, level: str, message: str, extra: Dict[str, Any]):
    """Log with extra structured data"""
    if hasattr(logging, level.upper()):
        log_level = getattr(logging, level.upper())
        logger.log(log_level, message, extra={"extra": extra})