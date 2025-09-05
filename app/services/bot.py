"""Telegram bot service for CourseWise."""

import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.constants import ParseMode
from loguru import logger

from app.config import settings
from app.handlers.simple_flow import create_conversation_handler


class CourseWiseBot:
    """
    Simplified Telegram bot service for CourseWise.
    
    Manages bot lifecycle with single-step LLM-based recommendations.
    """
    
    def __init__(self):
        """Initialize the CourseWise bot."""
        self.application: Optional[Application] = None
        self.is_running = False
        
        logger.info("CourseWise bot initialized")
    
    async def initialize(self) -> None:
        """Initialize the Telegram bot application."""
        try:
            # Create bot application
            self.application = Application.builder().token(settings.telegram_bot_token).build()
            
            # Setup bot menu
            await self._setup_bot_menu()
            
            # Register handlers
            self._register_handlers()
            
            logger.info("Bot application created and handlers registered")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def _setup_bot_menu(self) -> None:
        """Setup bot menu commands"""
        from telegram import BotCommand
        
        try:
            commands = [
                BotCommand("start", "شروع کار با بات و پیشنهاد دروس"),
                BotCommand("recommend", "پیشنهاد دروس جدید"),
                BotCommand("curriculum", "چارت درسی"),
                BotCommand("ita", "کانال ایتا رشته"),
                BotCommand("help", "راهنمای استفاده")
            ]
            
            await self.application.bot.set_my_commands(commands)
            logger.info("Bot menu commands configured")
            
        except Exception as e:
            logger.error(f"Failed to setup bot menu: {e}")
    
    def _register_handlers(self) -> None:
        """Register bot command and conversation handlers."""
        
        if not self.application:
            raise RuntimeError("Application not initialized")
        
        try:
            # Add menu command handlers first (higher priority)
            from app.handlers.menu_commands import get_menu_command_handlers
            menu_handlers = get_menu_command_handlers()
            for handler in menu_handlers:
                self.application.add_handler(handler)
            
            # Add the simplified conversation handler
            conversation_handler = create_conversation_handler()
            self.application.add_handler(conversation_handler)
            
            # Add error handler
            self.application.add_error_handler(self._error_handler)
            
            logger.info("All handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register handlers: {e}")
            raise
    
    async def start(self) -> None:
        """Start the bot and begin polling."""
        if not self.application:
            raise RuntimeError("Bot not initialized")
        
        try:
            # Initialize the application
            await self.application.initialize()
            
            # Start the bot
            await self.application.start()
            
            # Begin polling
            logger.info("Starting bot polling...")
            self.is_running = True
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Keep the application running
            logger.info("Bot is now running. Press Ctrl+C to stop.")
            
            # Keep running until stopped
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the bot and cleanup resources."""
        if not self.application:
            return
        
        try:
            self.is_running = False
            logger.info("Stopping bot...")
            
            # Stop polling
            await self.application.updater.stop()
            
            # Stop the application
            await self.application.stop()
            
            # Shutdown the application
            await self.application.shutdown()
            
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation."""
        
        error_message = f"Update {update.update_id} caused error: {context.error}"
        logger.error(error_message)
        
        # Notify user about error if update is available
        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ متأسفانه مشکلی پیش اومد. لطفاً دوباره تلاش کنید.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")
    
    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        """Send a message to a specific chat."""
        if not self.application or not self.application.bot:
            raise RuntimeError("Bot not initialized")
        
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def _health_check(self) -> bool:
        """Perform bot health check."""
        try:
            if not self.application or not self.application.bot:
                return False
            
            # Try to get bot info
            bot_info = await self.application.bot.get_me()
            logger.debug(f"Bot health check passed: {bot_info.username}")
            return True
            
        except Exception as e:
            logger.error(f"Bot health check failed: {e}")
            return False