"""
Configuration management for CourseWise Telegram Bot.

This module provides type-safe configuration loading from environment variables
using Pydantic BaseSettings with proper validation and error handling.
"""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from loguru import logger


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses Pydantic BaseSettings to automatically load and validate
    environment variables with proper type conversion and validation.
    """
    
    # Telegram Bot Configuration
    telegram_bot_token: str = Field(
        ...,
        description="Telegram Bot API token from @BotFather",
        min_length=10
    )
    
    # OpenAI API Configuration
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for Pydantic AI integration",
        min_length=10
    )
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://coursewise:coursewise@localhost:5432/coursewise",
        description="PostgreSQL database connection URL"
    )
    
    # Application Settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode for development"
    )
    
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    log_file_path: Optional[str] = Field(
        default=None,
        description="Optional log file path for file logging"
    )
    
    # Database Pool Settings
    db_pool_size: int = Field(
        default=5,
        description="Database connection pool size",
        ge=1,
        le=20
    )
    
    db_max_overflow: int = Field(
        default=10,
        description="Maximum overflow connections in pool",
        ge=0,
        le=50
    )
    
    db_pool_timeout: int = Field(
        default=30,
        description="Timeout for getting connection from pool (seconds)",
        ge=1,
        le=300
    )
    
    db_pool_recycle: int = Field(
        default=3600,
        description="Connection recycle time in seconds",
        ge=300,
        le=86400
    )
    
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level is one of the supported levels."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'log_level must be one of: {", ".join(valid_levels)}')
        return v.upper()
    
    @field_validator('telegram_bot_token')
    def validate_telegram_token(cls, v):
        """Validate Telegram bot token format."""
        if not v or len(v) < 40:
            raise ValueError('Invalid Telegram bot token format')
        if ':' not in v:
            raise ValueError('Telegram bot token should contain a colon (:)')
        return v
    
    @field_validator('openai_api_key')
    def validate_openai_key(cls, v):
        """Validate OpenAI API key format."""
        if not v or not v.startswith(('sk-', 'sk-proj-')):
            raise ValueError('OpenAI API key should start with "sk-" or "sk-proj-"')
        return v
    
    @field_validator('database_url')
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(('postgresql://', 'postgresql+asyncpg://')):
            raise ValueError('Database URL must be a PostgreSQL connection string')
        return v
    
    class Config:
        """Pydantic configuration for Settings class."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        extra = "ignore"  # Ignore extra environment variables


def load_settings() -> Settings:
    """
    Load and validate application settings.
    
    Returns:
        Settings: Validated settings instance
        
    Raises:
        ValueError: If required environment variables are missing or invalid
        FileNotFoundError: If .env file is specified but not found
    """
    try:
        # Check if .env file exists
        env_file_path = ".env"
        if os.path.exists(env_file_path):
            logger.info(f"Loading environment variables from {env_file_path}")
        else:
            logger.warning(f"No .env file found at {env_file_path}, using system environment variables")
        
        settings = Settings()
        
        # Log successful configuration load (without sensitive data)
        logger.info("Configuration loaded successfully")
        logger.debug(f"Debug mode: {settings.debug}")
        logger.debug(f"Log level: {settings.log_level}")
        logger.debug(f"Database URL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'}")
        
        return settings
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise ValueError(f"Configuration error: {e}") from e





settings = load_settings()



# Export the settings instance for easy importing
__all__ = ["settings", "Settings", "load_settings"]
