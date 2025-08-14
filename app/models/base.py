"""
Base SQLAlchemy models for CourseWise.

This module provides the declarative base and common model functionality
following SQLAlchemy 2.0 async patterns and Clean Architecture principles.
"""

from datetime import datetime
from typing import Any, Dict, Optional, TypeVar, Type
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Type variable for generic model operations
ModelType = TypeVar("ModelType", bound="Base")


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    Provides common fields and utility methods for all domain models.
    Uses AsyncAttrs for async relationship loading.
    """
    
    # Common primary key for all models
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Primary key for the table"
    )
    
    # Timestamp fields for audit tracking
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the model
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Update model instance from dictionary.
        
        Args:
            data: Dictionary with field names and values to update
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ('id', 'created_at'):
                setattr(self, key, value)
    
    @classmethod
    def get_table_name(cls) -> str:
        """
        Get the table name for this model.
        
        Returns:
            str: Table name
        """
        return cls.__tablename__
    
    def __repr__(self) -> str:
        """
        String representation of the model.
        
        Returns:
            str: Human-readable representation
        """
        return f"<{self.__class__.__name__}(id={self.id})>"


class TimestampMixin:
    """
    Mixin for models that need only timestamp fields without primary key.
    
    Useful for association tables or models with custom primary keys.
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Record creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Record last update timestamp"
    ) 