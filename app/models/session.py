"""
User session models for CourseWise.

This module contains session-related SQLAlchemy models for managing
bot conversation state and temporary data with database persistence.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger, String, DateTime, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UserSession(Base):
    """
    User session model for bot conversation state management.
    
    Stores temporary interaction data with database persistence,
    supporting multi-instance bot deployment and restart recovery.
    """
    
    __tablename__ = "user_sessions"
    
    # User identification
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        unique=True,
        index=True,
        comment="Telegram user ID for session identification"
    )
    
    # Session state management
    current_step: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="start",
        comment="Current conversation step (start, waiting_grades, etc.)"
    )
    
    # Flexible session data storage
    session_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Flexible JSON storage for session-specific data"
    )
    
    # Session lifecycle
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Session expiration timestamp"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        Index("idx_session_telegram_user", "telegram_user_id"),
        Index("idx_session_expires", "expires_at"), 
        Index("idx_session_step", "current_step"),
        Index("idx_session_active", "telegram_user_id", "expires_at"),
        CheckConstraint(
            "expires_at > created_at",
            name="check_valid_expiration"
        ),
        CheckConstraint(
            "current_step IN ('start', 'waiting_student_number', 'waiting_major_semester', 'confirming_registration', 'waiting_grades', 'confirming_grades', 'waiting_preferences', 'showing_recommendation', 'completed')",
            name="check_valid_step"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<UserSession(telegram_user_id={self.telegram_user_id}, step='{self.current_step}', expires_at='{self.expires_at}')>"
    
    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def extend_session(self, minutes: int = 30) -> None:
        """
        Extend session expiration time.
        
        Args:
            minutes: Number of minutes to extend (default: 30)
        """
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """
        Get value from session data.
        
        Args:
            key: Data key to retrieve
            default: Default value if key not found
            
        Returns:
            Value from session data or default
        """
        if not self.session_data:
            return default
        return self.session_data.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """
        Set value in session data.
        
        Args:
            key: Data key to set
            value: Value to store (must be JSON-serializable)
        """
        if not self.session_data:
            self.session_data = {}
        
        # Create a new dict to trigger SQLAlchemy change detection
        new_data = dict(self.session_data)
        new_data[key] = value
        self.session_data = new_data
    
    def remove_data(self, key: str) -> bool:
        """
        Remove key from session data.
        
        Args:
            key: Data key to remove
            
        Returns:
            True if key was removed, False if not found
        """
        if not self.session_data or key not in self.session_data:
            return False
        
        # Create a new dict to trigger SQLAlchemy change detection
        new_data = dict(self.session_data)
        del new_data[key]
        self.session_data = new_data
        return True
    
    def clear_data(self) -> None:
        """Clear all session data."""
        self.session_data = {}
    
    def get_data_summary(self) -> str:
        """
        Get summary of session data for debugging.
        
        Returns:
            String summary of session data keys and types
        """
        if not self.session_data:
            return "No session data"
        
        summary = []
        for key, value in self.session_data.items():
            value_type = type(value).__name__
            if isinstance(value, (str, int, float, bool)):
                summary.append(f"{key}: {value_type}({value})")
            elif isinstance(value, (list, dict)):
                summary.append(f"{key}: {value_type}(len={len(value)})")
            else:
                summary.append(f"{key}: {value_type}")
        
        return ", ".join(summary)
    
    @classmethod
    def create_new_session(cls, telegram_user_id: int, initial_step: str = "start", 
                          expiry_minutes: int = 30) -> "UserSession":
        """
        Create a new session instance.
        
        Args:
            telegram_user_id: Telegram user ID
            initial_step: Initial conversation step
            expiry_minutes: Session expiry time in minutes
            
        Returns:
            New UserSession instance
        """
        return cls(
            telegram_user_id=telegram_user_id,
            current_step=initial_step,
            session_data={},
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary for logging/debugging.
        
        Returns:
            Dictionary representation of session
        """
        base_dict = super().to_dict()
        base_dict.update({
            "is_expired": self.is_expired,
            "data_summary": self.get_data_summary()
        })
        return base_dict