"""
Registration and startup handlers for CourseWise bot.

This module handles the initial user registration flow including
student number collection, semester input, entry year, and confirmation.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from loguru import logger

from app.core.database import get_db
from app.utils.session import DatabaseSessionManager
from app.models.student import Student
from sqlalchemy import select


# Get session manager instance
session_manager = DatabaseSessionManager()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle /start command and begin registration flow.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    if not update.effective_user:
        return ConversationHandler.END
    
    user = update.effective_user
    user_id = user.id
    
    try:
        async with get_db() as db:
            # Check if user is already registered
            result = await db.execute(
                select(Student).where(Student.telegram_user_id == user_id)
            )
            existing_student = result.scalar_one_or_none()
            
            if existing_student:
                # User already registered, show welcome back message
                await update.message.reply_text(
                    f"🎓 **دوباره خوش آمدید، {existing_student.first_name}!**\n\n"
                    f"📊 **پروفایل شما:**\n"
                    f"• شماره دانشجویی: {existing_student.student_number}\n"
                    f"• رشته: {existing_student.major}\n"
                    f"• ترم: {existing_student.current_semester}\n"
                    f"• سال ورود: {existing_student.entry_year}\n\n"
                    f"برای وارد کردن نمرات جدید از /grades استفاده کنید یا /help برای مشاهده دستورات.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # Store user info in context for the conversation
            context.user_data['telegram_user'] = {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
            
        welcome_text = f"""
🎓 **به CourseWise خوش آمدید!**

سلام {user.first_name}! من اینجا هستم تا به شما در انتخاب بهینه دروس مهندسی کامپیوتر کمک کنم.

📝 **بیایید ثبت‌نام کنیم:**

برای ارائه توصیه‌های شخصی‌سازی شده، به اطلاعات پایه‌ای از پروفایل تحصیلی شما نیاز دارم.

**مرحله ۱ از ۴:** لطفاً **شماره دانشجویی** خود را وارد کنید
(مثال: 4001234567)
        """
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
        
        logger.info(f"Started registration flow for user {user_id} ({user.first_name})")
        
        # Import bot states from the bot service
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_STUDENT_NUMBER
        
    except Exception as e:
        logger.error(f"Error in start command for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong during registration. Please try again with /start.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


async def collect_student_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Collect and validate student number input.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    logger.info(f"collect_student_number called for update: {update.message.text if update.message else 'No message'}")
    
    if not update.effective_user or not update.message:
        logger.error("No effective user or message in collect_student_number")
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    student_number = update.message.text.strip()
    
    try:
        # Validate student number format (basic validation)
        if not student_number.isdigit() or len(student_number) < 8 or len(student_number) > 12:
            await update.message.reply_text(
                "❌ **فرمت شماره دانشجویی نامعتبر**\n\n"
                "لطفاً یک شماره دانشجویی معتبر (۸-۱۲ رقم) وارد کنید.\n"
                "مثال: 4001234567",
                parse_mode=ParseMode.MARKDOWN
            )
            from app.services.bot import CourseWiseBot
            return CourseWiseBot.WAITING_STUDENT_NUMBER
        
        async with get_db() as db:
            # Check if student number already exists
            result = await db.execute(
                select(Student).where(Student.student_number == student_number)
            )
            existing_student = result.scalar_one_or_none()
            
            if existing_student:
                await update.message.reply_text(
                    "❌ **شماره دانشجویی قبلاً ثبت شده**\n\n"
                    "این شماره دانشجویی قبلاً با حساب کاربری دیگری مرتبط شده. "
                    "اگر این شماره متعلق به شما است، لطفاً با پشتیبانی تماس بگیرید.",
                    parse_mode=ParseMode.MARKDOWN
                )
                from app.services.bot import CourseWiseBot
                return CourseWiseBot.WAITING_STUDENT_NUMBER
            
            # Store student number in context
            context.user_data['student_number'] = student_number
        
        await update.message.reply_text(
            f"✅ **شماره دانشجویی ذخیره شد:** {student_number}\n\n"
            f"**مرحله ۲ از ۴:** رشته شما **مهندسی کامپیوتر** است.\n\n"
            f"لطفاً **ترم فعلی** خود را وارد کنید:\n"
            f"(فقط عدد ترم - مثال: 5)",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Collected student number for user {user_id}: {student_number}")
        
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_SEMESTER
        
    except Exception as e:
        logger.error(f"Error collecting student number for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Something went wrong. Please try entering your student number again.",
            parse_mode=ParseMode.MARKDOWN
        )
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_STUDENT_NUMBER


async def collect_semester(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Collect and validate semester input.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    semester_str = update.message.text.strip()
    
    try:
        # Validate semester
        try:
            semester = int(semester_str)
            if semester < 1 or semester > 10:
                raise ValueError("Semester out of range")
        except ValueError:
            await update.message.reply_text(
                "❌ **ترم نامعتبر**\n\n"
                "لطفاً فقط شماره ترم (۱-۱۰) وارد کنید.\n\n"
                "مثال: 5",
                parse_mode=ParseMode.MARKDOWN
            )
            from app.services.bot import CourseWiseBot
            return CourseWiseBot.WAITING_SEMESTER
        
        # Store semester in context
        context.user_data['semester'] = semester
        
        await update.message.reply_text(
            f"✅ **ترم ذخیره شد:** {semester}\n\n"
            f"**مرحله ۳ از ۴:** لطفاً **سال ورود** خود را وارد کنید\n\n"
            f"(فقط سال شمسی - مثال: 1403)",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Collected semester for user {user_id}: {semester}")
        
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_ENTRY_YEAR
        
    except Exception as e:
        logger.error(f"Error collecting semester for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ مشکلی پیش آمد. لطفاً دوباره ترم خود را وارد کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_SEMESTER


async def collect_entry_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Collect and validate entry year input.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    entry_year_str = update.message.text.strip()
    
    try:
        # Validate entry year
        try:
            entry_year = int(entry_year_str)
            if entry_year < 1390 or entry_year > 1410:
                raise ValueError("Entry year out of range")
        except ValueError:
            await update.message.reply_text(
                "❌ **سال ورود نامعتبر**\n\n"
                "لطفاً سال ورود معتبر (۱۳۹۰-۱۴۱۰) وارد کنید.\n\n"
                "**سال‌های پشتیبانی شده:** 1393، 1395، 1397، 1399، 1401، 1403\n"
                "مثال: 1403",
                parse_mode=ParseMode.MARKDOWN
            )
            from app.services.bot import CourseWiseBot
            return CourseWiseBot.WAITING_ENTRY_YEAR
        
        # Store entry year in context
        context.user_data['entry_year'] = entry_year
        
        # Get all collected data
        student_number = context.user_data.get('student_number')
        semester = context.user_data.get('semester')
        telegram_user = context.user_data.get('telegram_user')
        
        if not student_number or not semester or not telegram_user:
            await update.message.reply_text(
                "❌ جلسه از دست رفت. لطفاً با /start دوباره شروع کنید",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Save student to database
        major = "مهندسی کامپیوتر"  # Fixed for now
        
        async with get_db() as db:
            student = Student(
                telegram_user_id=user_id,
                student_number=student_number,
                first_name=telegram_user.get('first_name', ''),
                last_name=telegram_user.get('last_name', ''),
                username=telegram_user.get('username'),
                major=major,
                current_semester=semester,
                entry_year=entry_year,
                is_active=True
            )
            
            db.add(student)
            await db.commit()
            
            logger.info(f"Student registered successfully: {student_number}")
        
        # Send success message
        success_text = f"""
🎉 **ثبت‌نام کامل شد!**

به CourseWise خوش آمدید، {telegram_user.get('first_name')}!

پروفایل شما با موفقیت ایجاد شد:
• 🆔 شماره دانشجویی: {student_number}
• 📚 رشته: {major}
• 📊 ترم: {semester}
• 📅 سال ورود: {entry_year}

**مرحله بعدی چیه؟**
• از /grades برای وارد کردن نمرات استفاده کنید
• توصیه‌های هوشمند دروس دریافت کنید
• از /help برای دیدن تمام دستورات استفاده کنید

بیایید با اضافه کردن نمرات شروع کنیم! 📊
        """
        
        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        
        logger.info(f"Registration completed for user {user_id}: {student_number}")
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error collecting entry year for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ مشکلی پیش آمد. لطفاً دوباره سال ورود خود را وارد کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_ENTRY_YEAR