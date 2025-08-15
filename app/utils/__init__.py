"""
Utility modules for CourseWise.

This package contains utility functions and classes that support
the core application functionality.
"""

from .session import DatabaseSessionManager

__all__ = [
    "DatabaseSessionManager",
]