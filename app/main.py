"""
Main application entry point for CourseWise Telegram bot.

This module provides the application startup, signal handling,
and graceful shutdown functionality.
"""

import asyncio
import signal
import sys
from loguru import logger

from app.config import settings
from app.services.bot import CourseWiseBot
from app.core.database import init_db


class CourseWiseApp:
    """
    Main application class for CourseWise bot.
    
    Handles application lifecycle, signal management, and service coordination.
    """
    
    def __init__(self):
        """Initialize the CourseWise application."""
        self.bot: CourseWiseBot = None
        self.is_shutting_down = False
        
        # Configure logging
        logger.remove()  # Remove default handler
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=settings.log_level
        )
        
        # Add file logging if configured
        if settings.log_file_path:
            logger.add(
                settings.log_file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=settings.log_level,
                rotation="1 day",
                retention="30 days",
                compression="gz"
            )
        
        # Note: Curriculum data now loaded dynamically from static files
        
        logger.info("CourseWise application initialized")
    
    async def startup(self) -> None:
        """
        Start the CourseWise application.
        
        Initializes database, bot services, and begins polling.
        """
        try:
            logger.info("Starting CourseWise application...")
            
            # Initialize database
            logger.info("Initializing database connection...")
            await init_db()
            logger.info("Database initialization complete")
            
            # Initialize bot
            logger.info("Initializing CourseWise bot...")
            self.bot = CourseWiseBot()
            await self.bot.initialize()
            logger.info("Bot initialization complete")
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Start bot
            logger.info("Starting bot polling...")
            await self.bot.start()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            await self.shutdown()
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self) -> None:
        """
        Gracefully shutdown the application.
        
        Stops bot services and cleans up resources.
        """
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        logger.info("Shutting down CourseWise application...")
        
        try:
            if self.bot:
                await self.bot.stop()
                logger.info("Bot stopped successfully")
            
            # Additional cleanup if needed
            logger.info("Application shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {signal.Signals(sig).name}")
            asyncio.create_task(self.shutdown())
        
        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.debug("Signal handlers configured")
    
    async def health_check(self) -> bool:
        """
        Perform application health check.
        
        Returns:
            True if application is healthy, False otherwise
        """
        try:
            if not self.bot:
                return False
            
            # Check bot health (this will check database and LLM services)
            await self.bot._health_check()
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


async def main() -> None:
    """Main application entry point."""
    app = CourseWiseApp()
    
    try:
        await app.startup()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Ensure we're running with proper asyncio event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)