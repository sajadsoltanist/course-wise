"""
CourseWise SQLAlchemy Models Package.

This package contains all domain models for the CourseWise application
following Clean Architecture principles and SQLAlchemy 2.0 async patterns.

All models are exported from this module for easy importing throughout the application.
"""

# Import base classes
from .base import Base, TimestampMixin

# Import all domain models
from .student import Student, StudentGrade, StudentSpecialization
from .course import Course, CoursePrerequisite
from .elective import ElectiveGroup, GroupCourse

# Export metadata for Alembic migrations
metadata = Base.metadata

# Export all models for easy importing
__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "metadata",
    
    # Student models
    "Student",
    "StudentGrade", 
    "StudentSpecialization",
    
    # Course models
    "Course",
    "CoursePrerequisite",
    
    # Elective models
    "ElectiveGroup",
    "GroupCourse",
]

# Model registry for dynamic access
MODEL_REGISTRY = {
    "Student": Student,
    "StudentGrade": StudentGrade,
    "StudentSpecialization": StudentSpecialization,
    "Course": Course,
    "CoursePrerequisite": CoursePrerequisite,
    "ElectiveGroup": ElectiveGroup,
    "GroupCourse": GroupCourse,
}

def get_model_by_name(model_name: str):
    """
    Get model class by name.
    
    Args:
        model_name: Name of the model class
        
    Returns:
        Model class or None if not found
    """
    return MODEL_REGISTRY.get(model_name)

def get_all_model_names() -> list[str]:
    """
    Get list of all available model names.
    
    Returns:
        List of model class names
    """
    return list(MODEL_REGISTRY.keys())

def get_table_names() -> list[str]:
    """
    Get list of all table names.
    
    Returns:
        List of database table names
    """
    return [model.__tablename__ for model in MODEL_REGISTRY.values()]
