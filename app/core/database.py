"""
Database infrastructure layer for CourseWise.

This module provides async SQLAlchemy setup with proper connection pooling,
session management, and health checks following Clean Architecture principles.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from loguru import logger

from app.config import settings


# Global variables for database infrastructure
engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def create_database_engine() -> AsyncEngine:
    """
    Create and configure async SQLAlchemy engine with connection pooling.
    
    Returns:
        AsyncEngine: Configured database engine
    """
    # Ensure we're using asyncpg driver
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("Database URL must use postgresql+asyncpg:// for async operations")
    
    logger.info(f"Creating database engine for: {database_url.split('@')[-1] if '@' in database_url else 'local'}")
    
    engine = create_async_engine(
        database_url,
        # Connection pool settings
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,  # Verify connections before use
        
        # Async settings
        echo=settings.debug,  # Log SQL queries in debug mode
        echo_pool=settings.debug,  # Log pool events in debug mode
        
        # Connection arguments for asyncpg
        connect_args={
            "server_settings": {
                "application_name": "coursewise_bot",
            }
        }
    )
    
    logger.info("Database engine created successfully")
    return engine


async def init_db() -> None:
    """
    Initialize database connection and session factory.
    
    This function should be called during application startup.
    
    Raises:
        SQLAlchemyError: If database connection fails
    """
    global engine, AsyncSessionLocal
    
    try:
        logger.info("Initializing database connection...")
        
        # Create engine
        engine = create_database_engine()
        
        # Create session factory
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
        
        # Test connection
        await health_check()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """
    Close database connections and clean up resources.
    
    This function should be called during application shutdown.
    """
    global engine, AsyncSessionLocal
    
    try:
        if engine:
            logger.info("Closing database connections...")
            await engine.dispose()
            logger.info("Database connections closed successfully")
        
        engine = None
        AsyncSessionLocal = None
        
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection function to get database session.
    
    Use this in services for database operations:
    
    Example:
        async with get_db() as db:
            # Database operations here
            result = await db.execute(select(User))
    
    Yields:
        AsyncSession: Database session
        
    Raises:
        RuntimeError: If database is not initialized
        SQLAlchemyError: If session creation fails
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Database session created")
            yield session
            await session.commit()
            logger.debug("Database session committed successfully")
            
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
            
        finally:
            await session.close()
            logger.debug("Database session closed")


async def health_check() -> bool:
    """
    Check database connection health.
    
    Returns:
        bool: True if database is healthy, False otherwise
        
    Raises:
        RuntimeError: If database is not initialized
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    try:
        logger.debug("Performing database health check...")
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            
            if row and row[0] == 1:
                logger.debug("Database health check passed")
                return True
            else:
                logger.error("Database health check failed: unexpected result")
                return False
                
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")
        return False


async def execute_raw_sql(sql: str, parameters: Optional[dict] = None) -> any:
    """
    Execute raw SQL with parameters (for migrations or special cases).
    
    Args:
        sql: SQL query string
        parameters: Optional parameters for the query
        
    Returns:
        Query result
        
    Raises:
        RuntimeError: If database is not initialized
        SQLAlchemyError: If query execution fails
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    try:
        logger.debug(f"Executing raw SQL: {sql[:100]}...")
        
        async with engine.begin() as conn:
            if parameters:
                result = await conn.execute(text(sql), parameters)
            else:
                result = await conn.execute(text(sql))
            
            logger.debug("Raw SQL executed successfully")
            return result
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to execute raw SQL: {e}")
        raise


async def get_connection_info() -> dict:
    """
    Get database connection information for monitoring.
    
    Returns:
        dict: Connection pool information
        
    Raises:
        RuntimeError: If database is not initialized
    """
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    pool = engine.pool
    
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid(),
        "url_database": engine.url.database,
        "url_host": engine.url.host,
        "url_port": engine.url.port
    } 