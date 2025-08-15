"""
Database session management for CourseWise bot.

This module provides the DatabaseSessionManager class for handling
user session state with PostgreSQL persistence.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from sqlalchemy.exc import IntegrityError, NoResultFound
from loguru import logger

from app.models.session import UserSession


class DatabaseSessionManager:
    """
    Manages user sessions with database persistence.
    
    Provides CRUD operations for user sessions with automatic expiration
    handling and cleanup functionality.
    """
    
    def __init__(self, default_expiry_minutes: int = 30):
        """
        Initialize the session manager.
        
        Args:
            default_expiry_minutes: Default session expiry time in minutes
        """
        self.default_expiry_minutes = default_expiry_minutes
    
    async def get_session(self, db: AsyncSession, telegram_user_id: int) -> Optional[UserSession]:
        """
        Get active session for a user.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            
        Returns:
            UserSession if found and not expired, None otherwise
        """
        try:
            result = await db.execute(
                select(UserSession)
                .where(UserSession.telegram_user_id == telegram_user_id)
            )
            session = result.scalar_one_or_none()
            
            if session and session.is_expired:
                logger.debug(f"Session for user {telegram_user_id} is expired, cleaning up")
                await self.delete_session(db, telegram_user_id)
                return None
            
            if session:
                logger.debug(f"Retrieved active session for user {telegram_user_id}, step: {session.current_step}")
            
            return session
            
        except Exception as e:
            logger.error(f"Error retrieving session for user {telegram_user_id}: {e}")
            return None
    
    async def get_or_create_session(self, db: AsyncSession, telegram_user_id: int, 
                                   initial_step: str = "start") -> UserSession:
        """
        Get existing session or create a new one.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            initial_step: Initial conversation step for new sessions
            
        Returns:
            UserSession instance (existing or newly created)
        """
        session = await self.get_session(db, telegram_user_id)
        
        if session:
            # Extend existing session
            session.extend_session(self.default_expiry_minutes)
            await db.commit()
            logger.debug(f"Extended existing session for user {telegram_user_id}")
            return session
        
        # Create new session
        return await self.create_session(db, telegram_user_id, initial_step)
    
    async def create_session(self, db: AsyncSession, telegram_user_id: int, 
                           initial_step: str = "start") -> UserSession:
        """
        Create a new session for a user.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            initial_step: Initial conversation step
            
        Returns:
            Newly created UserSession
            
        Raises:
            IntegrityError: If session already exists for user
        """
        try:
            # First, clean up any existing session
            await self.delete_session(db, telegram_user_id, commit=False)
            
            session = UserSession.create_new_session(
                telegram_user_id=telegram_user_id,
                initial_step=initial_step,
                expiry_minutes=self.default_expiry_minutes
            )
            
            db.add(session)
            await db.commit()
            
            logger.info(f"Created new session for user {telegram_user_id}, step: {initial_step}")
            return session
            
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Integrity error creating session for user {telegram_user_id}: {e}")
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating session for user {telegram_user_id}: {e}")
            raise
    
    async def update_session(self, db: AsyncSession, telegram_user_id: int, 
                           current_step: Optional[str] = None,
                           session_data: Optional[Dict[str, Any]] = None,
                           extend_expiry: bool = True) -> Optional[UserSession]:
        """
        Update session step and/or data.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            current_step: New conversation step
            session_data: Data to merge into session
            extend_expiry: Whether to extend session expiration
            
        Returns:
            Updated UserSession or None if not found
        """
        try:
            session = await self.get_session(db, telegram_user_id)
            if not session:
                logger.warning(f"No active session found for user {telegram_user_id}")
                return None
            
            # Update step if provided
            if current_step:
                session.current_step = current_step
                logger.debug(f"Updated session step for user {telegram_user_id}: {current_step}")
            
            # Update session data if provided
            if session_data:
                for key, value in session_data.items():
                    session.set_data(key, value)
                logger.debug(f"Updated session data for user {telegram_user_id}: {list(session_data.keys())}")
            
            # Extend expiry if requested
            if extend_expiry:
                session.extend_session(self.default_expiry_minutes)
            
            await db.commit()
            return session
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating session for user {telegram_user_id}: {e}")
            return None
    
    async def set_session_data(self, db: AsyncSession, telegram_user_id: int, 
                              key: str, value: Any) -> bool:
        """
        Set a specific data key in the session.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            key: Data key to set
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(db, telegram_user_id)
            if not session:
                return False
            
            session.set_data(key, value)
            session.extend_session(self.default_expiry_minutes)
            await db.commit()
            
            logger.debug(f"Set session data for user {telegram_user_id}: {key}")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error setting session data for user {telegram_user_id}: {e}")
            return False
    
    async def get_session_data(self, db: AsyncSession, telegram_user_id: int, 
                              key: str, default: Any = None) -> Any:
        """
        Get a specific data key from the session.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            key: Data key to retrieve
            default: Default value if key not found
            
        Returns:
            Value from session data or default
        """
        try:
            session = await self.get_session(db, telegram_user_id)
            if not session:
                return default
            
            return session.get_data(key, default)
            
        except Exception as e:
            logger.error(f"Error getting session data for user {telegram_user_id}: {e}")
            return default
    
    async def delete_session(self, db: AsyncSession, telegram_user_id: int, 
                           commit: bool = True) -> bool:
        """
        Delete a user's session.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            commit: Whether to commit the transaction
            
        Returns:
            True if session was deleted, False otherwise
        """
        try:
            result = await db.execute(
                delete(UserSession)
                .where(UserSession.telegram_user_id == telegram_user_id)
            )
            
            if commit:
                await db.commit()
            
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted session for user {telegram_user_id}")
            
            return deleted
            
        except Exception as e:
            if commit:
                await db.rollback()
            logger.error(f"Error deleting session for user {telegram_user_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """
        Remove all expired sessions from the database.
        
        Args:
            db: Database session
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            result = await db.execute(
                delete(UserSession)
                .where(UserSession.expires_at <= current_time)
            )
            
            await db.commit()
            
            cleaned_count = result.rowcount
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired sessions")
            
            return cleaned_count
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    async def get_active_sessions_count(self, db: AsyncSession) -> int:
        """
        Get count of active (non-expired) sessions.
        
        Args:
            db: Database session
            
        Returns:
            Number of active sessions
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            result = await db.execute(
                select(UserSession)
                .where(UserSession.expires_at > current_time)
            )
            
            sessions = result.scalars().all()
            return len(sessions)
            
        except Exception as e:
            logger.error(f"Error getting active sessions count: {e}")
            return 0
    
    async def get_sessions_by_step(self, db: AsyncSession, step: str) -> List[UserSession]:
        """
        Get all active sessions at a specific conversation step.
        
        Args:
            db: Database session
            step: Conversation step to filter by
            
        Returns:
            List of UserSession instances
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            result = await db.execute(
                select(UserSession)
                .where(
                    and_(
                        UserSession.current_step == step,
                        UserSession.expires_at > current_time
                    )
                )
            )
            
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting sessions by step '{step}': {e}")
            return []
    
    async def extend_session_expiry(self, db: AsyncSession, telegram_user_id: int, 
                                   minutes: int = None) -> bool:
        """
        Extend a session's expiry time.
        
        Args:
            db: Database session
            telegram_user_id: Telegram user ID
            minutes: Minutes to extend (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = await self.get_session(db, telegram_user_id)
            if not session:
                return False
            
            extend_minutes = minutes or self.default_expiry_minutes
            session.extend_session(extend_minutes)
            await db.commit()
            
            logger.debug(f"Extended session expiry for user {telegram_user_id} by {extend_minutes} minutes")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error extending session expiry for user {telegram_user_id}: {e}")
            return False