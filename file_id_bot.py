"""
Simple standalone bot to get Telegram file IDs.
Just run this script and send files to get their IDs.
"""

import asyncio
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

# Put your bot token here
BOT_TOKEN = "8267702532:AAGzEasjf8cdduMuk0ZYbUeyGjdIYFimyy4"  # Replace with your bot token


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any document and return its file ID."""
    try:
        if update.message.document:
            file_id = update.message.document.file_id
            file_name = update.message.document.file_name or "Unknown"
            
            message = (
                f"📄 File: {file_name}\n"
                f"🆔 ID: `{file_id}`\n\n"
                f"Copy the ID above ↑"
            )
            
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            print(f"File: {file_name}")
            print(f"ID: {file_id}")
            print("-" * 40)
            
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def main():
    """Run the file ID bot."""
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN first!")
        print("Edit this file and replace BOT_TOKEN with your actual token")
        return
    
    print("🤖 File ID Bot Starting...")
    print("Send any file to get its Telegram file ID")
    print("-" * 40)
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add document handler
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Start bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    print("✅ Bot is running! Send files to get their IDs")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())