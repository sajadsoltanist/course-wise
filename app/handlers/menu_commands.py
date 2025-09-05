"""Main menu handlers and navigation."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
from loguru import logger


def get_main_menu_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🤖 پیشنهاد دروس", callback_data="start_recommend"),
            InlineKeyboardButton("📚 چارت درسی", callback_data="show_curriculum")
        ],
        [
            InlineKeyboardButton("📢 کانال ایتا", callback_data="show_ita"),
            InlineKeyboardButton("📋 قوانین انتخاب واحد", callback_data="show_rules")
        ],
        [
            InlineKeyboardButton("❓ راهنما", callback_data="show_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def main_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    try:
        # Check student registration
        from app.core.database import get_db
        from app.models import Student
        from sqlalchemy import select
        
        async with get_db() as db:
            result = await db.execute(
                select(Student).where(Student.telegram_user_id == user_id)
            )
            student = result.scalar_one_or_none()
        
        # Registration required
        if not student or not student.student_number:
            message_text = (
                "🎓 **ثبت نام در CourseWise**\n\n"
                "برای استفاده از امکانات بات، ابتدا شماره دانشجویی خود را وارد کنید:\n\n"
                "📝 **شماره دانشجویی:** مثلاً 98123456789"
            )
            
            await update.message.reply_text(
                text=message_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            context.user_data['waiting_for_student_number'] = True
            context.user_data['user_id'] = user_id
            return
        
        user_name = update.effective_user.first_name or "کاربر"
        message_text = (
            "🤖 *CourseWise - مشاور هوشمند انتخاب واحد*\n\n"
            f"👋 سلام **{user_name}**!\n"
            "یکی از گزینه‌های زیر رو انتخاب کن:\n\n"
            "🤖 *پیشنهاد دروس*: دریافت پیشنهادات هوشمند با هوش مصنوعی\n"
            "📚 *چارت درسی*: مشاهده چارت درسی رشته\n"
            "📢 *کانال ایتا*: لینک کانال اطلاع‌رسانی\n"
            "📋 *قوانین انتخاب واحد*: مقررات رشته و عمومی\n"
            "❓ *راهنما*: نحوه استفاده از بات"
        )
        
        await update.message.reply_text(
            text=message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_inline_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in main_menu_command: {e}")
        await update.message.reply_text(
            "❌ مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
        )


async def handle_main_menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == "start_recommend":
        from app.handlers.simple_flow import SimpleFlowHandler
        from app.core.database import get_db
        from app.models import Student
        from sqlalchemy import select
        
        user_id = query.from_user.id
        
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(Student).where(Student.telegram_user_id == user_id)
                )
                student = result.scalar_one_or_none()
            
            if student and student.entry_year and student.current_semester:
                message_text = (
                    f"🎯 **آماده برای پیشنهاد دروس هوشمند!**\n\n"
                    f"📚 ورودی: **{student.entry_year}**\n"
                    f"📅 ترم فعلی: **{student.current_semester}**\n\n"
                    f"برای تهیه بهترین پیشنهادات، این اطلاعات رو در **یک پیام** بفرست:\n\n"
                    f"📋 **نمرات تمام دروس گذرانده شده:**\n"
                    f"💡 مثال: ریاضی عمومی ۱: 17.5، فیزیک ۱: 16، زبان انگلیسی: 15\n\n"
                    f"📊 **معدل ترم قبل:** مثلاً 16.2\n\n"
                    f"🎯 **معدل کل تا الان:** مثلاً 15.8\n\n"
                    f"🚀 آماده‌ای؟ همه چیز رو یکجا بفرست تا بهترین دروس رو برات انتخاب کنم! 🤖✨"
                )
            else:
                message_text = (
                    f"🎉 **به CourseWise خوش اومدی!**\n\n"
                    f"🤖 من مشاور هوشمند انتخاب واحد دانشگاه آزاد شهرکردم و آماده‌م تا بهترین دروس رو برات پیدا کنم!\n\n"
                    f"📝 برای شروع، این اطلاعات رو در **یک پیام** بفرست:\n\n"
                    f"🎓 **سال ورودی:** مثلاً 1401 یا 1403\n\n"
                    f"📅 **ترم فعلی:** مثلاً 4\n\n"
                    f"📋 **نمرات تمام دروس گذرانده شده:**\n"
                    f"💡 مثال: ریاضی عمومی ۱: 17.5، فیزیک ۱: 16، زبان انگلیسی: 15\n\n"
                    f"📊 **معدل ترم قبل:** مثلاً 16.2\n\n"
                    f"🎯 **معدل کل:** مثلاً 15.8\n\n"
                    f"🚀 حالا همه چیز رو یکجا بفرست تا جادوی پیشنهاد دروس شروع بشه! ✨🎯"
                )
            
            await query.message.reply_text(
                text=message_text,
                parse_mode='Markdown'
            )
            
            await query.delete_message()
            context.user_data['waiting_for_grades'] = True
            context.user_data['user_id'] = user_id
                
        except Exception as e:
            logger.error(f"Error in start_recommend callback: {e}")
            await query.edit_message_text(
                text="متأسفانه مشکلی پیش اومد. لطفاً مجدداً تلاش کنید."
            )
        
    elif query.data == "show_curriculum":
        await curriculum_inline_menu(query, context)
        
    elif query.data == "show_ita":
        await ita_inline_response(query, context)
        
    elif query.data == "show_help":
        await help_inline_response(query, context)
        
    elif query.data == "show_rules":
        await rules_inline_response(query, context)


async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    message_text = (
        "🤖 *CourseWise - مشاور هوشمند انتخاب واحد*\n\n"
        "سلام! به بات مشاوره انتخاب واحد خوش اومدی.\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:\n\n"
        "🤖 *پیشنهاد دروس*: دریافت پیشنهادات هوشمند\n"
        "📚 *چارت درسی*: مشاهده چارت درسی رشته\n"
        "📢 *کانال ایتا*: لینک کانال اطلاع‌رسانی\n"
        "❓ *راهنما*: نحوه استفاده از بات"
    )
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_inline_keyboard()
    )


async def curriculum_inline_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show curriculum selection inline."""
    keyboard = [
        [
            InlineKeyboardButton("ورودی 1403 به بعد", callback_data="curriculum_1403_plus"),
            InlineKeyboardButton("ورودی قبل از 1403", callback_data="curriculum_before_1403")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "📚 *چارت درسی رشته مهندسی کامپیوتر*\n\n"
        "لطفاً سال ورودی خود را انتخاب کنید:"
    )
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def ita_inline_response(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Ita channel info inline."""
    message_text = (
        "📢 *کانال اطلاع‌رسانی ایتا دانشکده*\n\n"
        "برای دریافت آخرین اخبار و اطلاعیه‌های دانشکده مهندسی کامپیوتر، "
        "به کانال ایتا دانشکده مراجعه کنید:\n\n"
        "🔗 [کانال ایتا دانشکده](https://eitaa.com/computer_engineering_channel)\n\n"
        "💡 *نکته:* در این کانال اطلاعات مهم درباره:\n"
        "• برنامه امتحانات\n"
        "• مهلت انتخاب واحد\n"
        "• رویدادهای علمی\n"
        "• اعلامیه‌های مهم\n"
        "منتشر می‌شود."
    )
    
    # Add back to menu button
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )


async def help_inline_response(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help info inline."""
    message_text = (
        "🤖 *راهنمای استفاده از بات CourseWise*\n\n"
        "این بات برای کمک به انتخاب بهتر واحدهای درسی طراحی شده است.\n\n"
        "🎯 *نحوه استفاده:*\n"
        "1️⃣ روی *پیشنهاد دروس* کلیک کنید\n"
        "2️⃣ اطلاعات دانشجویی خود را وارد کنید\n"
        "3️⃣ نمرات دروس گذرانده را ارسال کنید\n"
        "4️⃣ پیشنهادات هوشمند دریافت کنید\n\n"
        "💡 *نکته:* بات با هوش مصنوعی پیشنهادات را بر اساس:\n"
        "• پیش‌نیازهای دروس\n"
        "• معدل فعلی شما\n"
        "• قوانین دانشگاه\n"
        "ارائه می‌دهد.\n\n"
        "❓ برای بازگشت به منو اصلی، `/start` کنید."
    )
    
    # Add back to menu button
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def rules_inline_response(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show course selection rules menu."""
    keyboard = [
        [
            InlineKeyboardButton("📋 قوانین رشته کامپیوتر", callback_data="rules_major"),
            InlineKeyboardButton("🎓 قوانین عمومی دانشگاه", callback_data="rules_general")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "📋 *قوانین انتخاب واحد*\n\n"
        "یکی از بخش‌های زیر را انتخاب کنید:\n\n"
        "📋 *قوانین رشته*: مقررات مخصوص مهندسی کامپیوتر\n"
        "🎓 *قوانین عمومی*: مقررات کلی دانشگاه آزاد"
    )
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def curriculum_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /curriculum command - redirect to main menu."""
    await main_menu_command(update, context)


async def curriculum_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle curriculum entry year selection callback."""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "curriculum_1403_plus":
            # Send curriculum for 1403+ entries
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document="BQACAgQAAxkBAAIBdmi7D0z-mBYMOZMUS9pBGc9fWA1HAAKaHAACp6HZUba7PsVZWLdcNgQ",
                caption="📚 چارت درسی - ورودی 1403 به بعد"
            )
            
        elif query.data == "curriculum_before_1403":
            # Send curriculum for pre-1403 entries
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document="BQACAgQAAxkBAAIBdGi7Dzfv830cAAEsPLAmkKW3n-8mjAACmRwAAqeh2VHORSCEUKr-bzYE",
                caption="📚 چارت درسی - ورودی قبل از 1403"
            )
        
        # Send back to menu button after file
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            "✅ چارت درسی ارسال شد!",
            reply_markup=reply_markup
        )
        
        # Delete the original message with buttons
        await query.delete_message()
        
        logger.info(f"User {update.effective_user.id} selected curriculum: {query.data}")
        
    except Exception as e:
        logger.error(f"Error in curriculum callback: {e}")
        await query.edit_message_text(
            "❌ متأسفانه مشکلی در ارسال چارت درسی پیش آمد."
        )


async def ita_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ita command - redirect to main menu."""
    await main_menu_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - redirect to main menu."""
    await main_menu_command(update, context)


async def show_major_rules(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show computer engineering specific rules."""
    message_text = (
        "📋 *قوانین رشته مهندسی کامپیوتر*\n\n"
        
        "💠 *معدل و وضعیت تحصیلی:*\n"
        "📊 معدل بالای ۱۷: مجاز به ۲۴ واحد\n"
        "⚠️ معدل زیر ۱۲: مشروط - حداکثر ۱۴ واحد\n"
        "🎯 حداقل معدل قبولی: ۱۲ از ۲۰\n\n"
        
        "💠 *پیش‌نیازهای دروس:*\n"
        "🔗 باید تمام پیش‌نیازها را با نمره قبولی (۱۰+) گذرانده باشید\n"
        "📚 برخی دروس هم‌نیاز دارند که باید همزمان انتخاب شوند\n"
        "⚡ دروس پایه قبل از تخصصی الزامی است\n\n"
        
        "💠 *دروس اختیاری تخصصی:*\n"
        "🎓 برای فارغ‌التحصیلی حداقل ۱۲ واحد از یک گرایش انتخابی\n"
        "⚠️ پس از انتخاب گرایش، باید فقط دروس همان گرایش را برداشت\n"
        "📌 گرایش‌ها: هوش مصنوعی، شبکه‌های کامپیوتری، نرم‌افزار، گرافیک، پایگاه داده، امنیت، معماری\n"
        "🔺 ویژه ورودی قبل ۱۴۰۳: گرایش شبکه‌های کامپیوتری ارائه می‌شود\n\n"
        
        "💠 *دروس عملی و آزمایشگاه:*\n"
        "🔬 حضور در آزمایشگاه الزامی است\n"
        "📝 نمره عملی جداگانه محاسبه می‌شود\n"
        "⚠️ دروس عملی در معرفی به استاد پذیرفته نمی‌شوند\n\n"
        
        "💡 *نکته مهم:* قبل از انتخاب واحد، چارت درسی و پیش‌نیازها را بررسی کرده و با مشاور آموزشی مشورت کنید."
    )
    
    # Add back to rules menu button
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به قوانین", callback_data="show_rules")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def show_general_rules(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show general university rules."""
    message_text = (
        "🎓 *قوانین عمومی دانشگاه آزاد*\n\n"
        
        "💠 *حداقل و حداکثر واحد مجاز:*\n"
        "🔴 کف واحد: حداقل ۱۲ واحد (تمام وقت)\n"
        "🔴 سقف واحد: حداکثر ۲۰ واحد\n"
        "✅ معدل بالای ۱۷: تا ۲۴ واحد\n"
        "❌ مشروط (زیر ۱۲): حداکثر ۱۴ واحد\n\n"
        
        "💠 *دروس معارف اسلامی:*\n"
        "📚 می‌توانید هر ترم یکی از دروس معارف برداشته و انتخاب کنید\n"
        "📖 درس انس با قرآن برای ورودی‌های ۱۴۰۱+ الزامی\n"
        "🎯 نمره در معدل حساب می‌شود اما در سقف واحد محاسبه نمی‌شود\n\n"
        
        "💠 *معرفی به استاد:*\n"
        "🎯 برای دانشجویان ترم آخر با حداکثر ۸ واحد باقیمانده\n"
        "⚠️ فقط دروس نظری (بدون واحد عملی)\n"
        "📝 تا ۴ واحد: مراجعه به امتحانات\n"
        "📝 ۵-۸ واحد: مراجعه به کارشناس گروه\n"
        "💰 هزینه: نصف شهریه ثابت + متغیر\n\n"
        
        "💡 *نکته مهم:* برای اطلاع از وضعیت دقیق واحدهای خود، از منوی \"مشاهده آخرین وضعیت ثبت‌نام\" در آموزشیار استفاده کنید."
    )
    
    # Add back to rules menu button
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به قوانین", callback_data="show_rules")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_grades_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle grades input from users who came from menu."""
    user_id = update.effective_user.id
    user_input = update.message.text
    
    # Check if this user is waiting for student number
    if context.user_data.get('waiting_for_student_number') and context.user_data.get('user_id') == user_id:
        logger.info(f"🔥 PROCESSING STUDENT NUMBER from user {user_id}")
        
        # Validate student number (basic validation)
        if len(user_input.strip()) < 8 or not user_input.strip().isdigit():
            await update.message.reply_text(
                "❌ **شماره دانشجویی نامعتبر**\n\n"
                "لطفاً شماره دانشجویی صحیح وارد کنید.\n"
                "مثال: 98123456789",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Save student number to database
        await save_student_number(user_id, user_input.strip())
        
        # Clear state
        context.user_data['waiting_for_student_number'] = False
        
        # Show success message and then menu
        await update.message.reply_text(
            "✅ **ثبت نام موفقیت‌آمیز!**\n\n"
            f"🎓 شماره دانشجویی شما: **{user_input.strip()}**\n\n"
            "حالا می‌تونید از تمام امکانات CourseWise استفاده کنید! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Show menu
        await main_menu_command(update, context)
        return
    
    # Check if this user is waiting for grades
    elif context.user_data.get('waiting_for_grades') and context.user_data.get('user_id') == user_id:
        logger.info(f"🔥 PROCESSING GRADES INPUT from menu user {user_id}")
        
        # Import and use simple flow handler
        from app.handlers.simple_flow import SimpleFlowHandler
        handler = SimpleFlowHandler()
        
        # Clear the state
        context.user_data['waiting_for_grades'] = False
        
        # Process the grades
        await handler.process_grades_input(update, context)


async def save_student_number(user_id: int, student_number: str) -> None:
    """Save student number to database."""
    try:
        from app.core.database import get_db
        from app.models import Student
        from sqlalchemy import select
        
        async with get_db() as db:
            # Check if student exists
            result = await db.execute(
                select(Student).where(Student.telegram_user_id == user_id)
            )
            student = result.scalar_one_or_none()
            
            if student:
                # Update existing student
                student.student_number = student_number
            else:
                # Create new student
                student = Student(
                    telegram_user_id=user_id,
                    student_number=student_number
                )
                db.add(student)
            
            await db.commit()
            logger.info(f"Student number saved for user {user_id}: {student_number}")
            
    except Exception as e:
        logger.error(f"Error saving student number: {e}")
        raise


async def handle_rules_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rules callback buttons."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "rules_major":
        await show_major_rules(query, context)
    elif query.data == "rules_general":
        await show_general_rules(query, context)


# Export functions
__all__ = ['get_menu_command_handlers', 'main_menu_command', 'get_main_menu_inline_keyboard']

# Handler creators
def get_menu_command_handlers():
    """Get all menu command handlers."""
    return [
        CommandHandler("start", main_menu_command),
        CommandHandler("curriculum", curriculum_command),
        CommandHandler("ita", ita_command),
        CommandHandler("help", help_command),
        CallbackQueryHandler(handle_main_menu_callbacks, pattern="^(start_recommend|show_curriculum|show_ita|show_help|show_rules)$"),
        CallbackQueryHandler(handle_back_to_menu, pattern="^back_to_menu$"),
        CallbackQueryHandler(curriculum_callback, pattern="^curriculum_"),
        CallbackQueryHandler(handle_rules_callbacks, pattern="^rules_(major|general)$"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_grades_input)
    ]