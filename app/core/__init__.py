"""
Core infrastructure layer for CourseWise.

This package contains infrastructure components like database connections,
external API clients, and other low-level services following Clean Architecture principles.
"""

from .database import (
    get_db,
    init_db,
    close_db,
    health_check,
    AsyncSessionLocal,
    engine
)

__all__ = [
    "get_db",
    "init_db", 
    "close_db",
    "health_check",
    "AsyncSessionLocal",
    "engine"
] 