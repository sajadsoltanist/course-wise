"""
CourseWise SQLAlchemy Models Package - Simplified.

Contains only essential models for LLM-based course recommendations.
"""

# Import base classes
from .base import Base, TimestampMixin

# Import simplified models
from .student import Student
from .session import UserSession

# Export metadata for Alembic migrations
metadata = Base.metadata

# Export simplified models
__all__ = [
    # Base classes
    "Base",
    "TimestampMixin", 
    "metadata",
    
    # Essential models
    "Student",
    "UserSession",
]
