"""
Course Recommendation Handler

هندلر دستور /recommend برای پیشنهاد دروس هوشمند
شامل: مکالمه تعاملی، تنظیمات کاربر، نمایش پیشنهادات
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from loguru import logger

from app.core.database import get_db
from app.utils.session import DatabaseSessionManager
from app.models.student import Student
from app.services.recommendation_engine import RecommendationEngine
from sqlalchemy import select


# Get session manager instance
session_manager = DatabaseSessionManager()

# Get recommendation engine instance
recommendation_engine = RecommendationEngine()


# Conversation states - match CourseWiseBot constants
WAITING_SEMESTER_SELECTION = 10
WAITING_PREFERENCES_INPUT = 11
WAITING_CREDIT_PREFERENCE = 12
WAITING_FINAL_CONFIRMATION = 13


async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle /recommend command and start recommendation flow.
    
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
        # Get database session and check if user is registered
        async with get_db() as db:
            result = await db.execute(
                select(Student).where(Student.telegram_user_id == user_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                await update.message.reply_text(
                    "❌ **شما هنوز ثبت‌نام نکرده‌اید!**\n\n"
                    "برای دریافت پیشنهاد دروس، ابتدا باید ثبت‌نام کنید.\n"
                    "از دستور /start استفاده کنید.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # Check if student has any grades - do this within the session
            from app.models.student import StudentGrade
            grades_result = await db.execute(
                select(StudentGrade).where(StudentGrade.student_id == student.id)
            )
            has_grades = grades_result.first() is not None
            
            # Calculate GPA within session
            student_gpa = await _calculate_student_gpa_in_session(db, student.id)
            
            # Store student info in context
            context.user_data['student_id'] = student.id
            context.user_data['student_info'] = {
                'name': student.first_name,
                'semester': student.current_semester,
                'entry_year': student.entry_year,
                'gpa': student_gpa
            }
        
        # Check if student has any grades
        if not has_grades:
            await update.message.reply_text(
                "⚠️ **نمرات شما ثبت نشده است!**\n\n"
                "برای ارائه پیشنهاد بهتر، ابتدا نمرات خود را وارد کنید.\n"
                "از دستور /grades استفاده کنید.\n\n"
                "آیا می‌خواهید با اطلاعات موجود ادامه دهیم؟",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ ادامه", callback_data="continue_without_grades"),
                        InlineKeyboardButton("❌ انصراف", callback_data="cancel_recommendation")
                    ]
                ])
            )
            return WAITING_FINAL_CONFIRMATION
            
        # Show semester selection
        await _show_semester_selection(update, context.user_data['student_info'])
        
        logger.info(f"Started recommendation flow for student {context.user_data['student_id']}")
        return WAITING_SEMESTER_SELECTION
        
    except Exception as e:
        logger.error(f"Error in recommend command for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ مشکلی در شروع فرایند پیشنهاد به وجود آمد. لطفاً دوباره تلاش کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


async def _show_semester_selection(update: Update, student_info: dict) -> None:
    """Show semester selection options."""
    
    current_year = 1404  # Current academic year
    
    # Available semesters
    semesters = [
        {"id": f"mehr_{current_year}", "name": f"مهر {current_year}", "current": True},
        {"id": f"bahman_{current_year}", "name": f"بهمن {current_year}", "current": False}
    ]
    
    keyboard = []
    for semester in semesters:
        status = " (ترم جاری)" if semester["current"] else ""
        keyboard.append([
            InlineKeyboardButton(
                f"📅 {semester['name']}{status}", 
                callback_data=f"semester_{semester['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ انصراف", callback_data="cancel_recommendation")
    ])
    
    welcome_text = f"""
🎓 **سلام {student_info['name']}!**

برای ارائه بهترین پیشنهاد دروس، لطفاً ترم مورد نظر خود را انتخاب کنید:

📊 **اطلاعات کلی شما:**
• ترم فعلی: {student_info['semester']}
• سال ورود: {student_info['entry_year']}
• معدل فعلی: {student_info['gpa']:.2f}

🎯 **انتخاب ترم:**
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_semester_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle semester selection callback."""
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_recommendation":
        await query.edit_message_text(
            "❌ **فرایند پیشنهاد دروس لغو شد.**\n\n"
            "برای شروع مجدد از دستور /recommend استفاده کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    if query.data == "continue_without_grades":
        # Continue without grades - show semester selection
        await query.edit_message_text("⏳ در حال آماده‌سازی...")
        await _show_semester_selection_after_query(query, context.user_data['student_info'])
        return WAITING_SEMESTER_SELECTION
    
    if query.data.startswith("semester_"):
        semester_id = query.data.replace("semester_", "")
        context.user_data['target_semester'] = semester_id
        
        # Show credit preference selection
        await _show_credit_preferences(query, context)
        return WAITING_CREDIT_PREFERENCE
    
    return WAITING_SEMESTER_SELECTION


async def _show_semester_selection_after_query(query, student_info: dict) -> None:
    """Show semester selection after callback query."""
    
    current_year = 1404
    semesters = [
        {"id": f"mehr_{current_year}", "name": f"مهر {current_year}", "current": True},
        {"id": f"bahman_{current_year}", "name": f"بهمن {current_year}", "current": False}
    ]
    
    keyboard = []
    for semester in semesters:
        status = " (ترم جاری)" if semester["current"] else ""
        keyboard.append([
            InlineKeyboardButton(
                f"📅 {semester['name']}{status}", 
                callback_data=f"semester_{semester['id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ انصراف", callback_data="cancel_recommendation")
    ])
    
    text = f"""
🎓 **انتخاب ترم برای پیشنهاد دروس**

**دانشجو:** {student_info['name']}
**ترم فعلی:** {student_info['semester']}

📅 **لطفاً ترم مورد نظر را انتخاب کنید:**
    """
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_credit_preferences(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show credit preference selection."""
    
    semester_name = context.user_data['target_semester'].replace('_', ' ').title()
    student_info = context.user_data['student_info']
    
    # Calculate recommended credit range based on GPA
    gpa = student_info.get('gpa', 0)
    if gpa >= 17:
        credit_ranges = [
            {"range": "12-16", "desc": "متعادل"},
            {"range": "17-20", "desc": "استاندارد"},
            {"range": "21-24", "desc": "حداکثر"}
        ]
    elif gpa >= 15:
        credit_ranges = [
            {"range": "12-16", "desc": "محتاطانه"},
            {"range": "17-20", "desc": "استاندارد"}
        ]
    elif gpa >= 12:
        credit_ranges = [
            {"range": "12-16", "desc": "توصیه شده"},
            {"range": "17-18", "desc": "حداکثر"}
        ]
    else:
        credit_ranges = [
            {"range": "14-16", "desc": "اجباری (مشروطی)"}
        ]
    
    keyboard = []
    for credit_range in credit_ranges:
        keyboard.append([
            InlineKeyboardButton(
                f"📚 {credit_range['range']} واحد ({credit_range['desc']})",
                callback_data=f"credits_{credit_range['range']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔧 تنظیمات دستی", callback_data="custom_preferences"),
        InlineKeyboardButton("⬅️ بازگشت", callback_data="back_to_semester")
    ])
    
    text = f"""
📊 **انتخاب تعداد واحد**

**ترم انتخابی:** {semester_name}
**معدل فعلی:** {gpa:.2f}

بر اساس معدل شما، گزینه‌های زیر پیشنهاد می‌شود:

💡 **نکته:** انتخاب تعداد واحد مناسب بر عملکرد تحصیلی شما تأثیر مستقیم دارد.
    """
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_credit_preference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle credit preference selection."""
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_semester":
        await _show_semester_selection_after_query(query, context.user_data['student_info'])
        return WAITING_SEMESTER_SELECTION
    
    if query.data == "custom_preferences":
        await _show_custom_preferences_form(query, context)
        return WAITING_PREFERENCES_INPUT
    
    if query.data.startswith("credits_"):
        credit_range = query.data.replace("credits_", "")
        context.user_data['credit_preference'] = credit_range
        context.user_data['preferences'] = {
            'desired_credits': credit_range,
            'preferences_type': 'quick'
        }
        
        # Start generating recommendations
        await _start_recommendation_generation(query, context)
        return ConversationHandler.END
    
    return WAITING_CREDIT_PREFERENCE


async def _show_custom_preferences_form(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show custom preferences input form."""
    
    text = """
🔧 **تنظیمات دقیق پیشنهاد دروس**

لطفاً ترجیحات خود را در پیام بعدی بنویسید:

**مثال:**
```
تعداد واحد: 18
زمان‌بندی: صبحگاهی  
علاقه‌مندی: دروس برنامه‌سازی
اولویت: دروس آسان
یادداشت: نمی‌خواهم جمعه کلاس داشته باشم
```

**راهنما:**
• تعداد واحد: عدد یا بازه (مثل 16-20)
• زمان‌بندی: صبحگاهی/عصرگاهی/مختلط
• علاقه‌مندی: نام گرایش یا نوع درس
• اولویت: بهبود معدل/جبران درس مردودی/گرایش
• یادداشت: سایر درخواست‌ها

❌ برای انصراف /cancel بزنید.
    """
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_custom_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom preferences input."""
    
    if not update.message or not update.message.text:
        await update.message.reply_text(
            "❌ لطفاً ترجیحات خود را متنی وارد کنید یا /cancel برای انصراف."
        )
        return WAITING_PREFERENCES_INPUT
    
    preferences_text = update.message.text.strip()
    
    if preferences_text.lower() in ['/cancel', 'انصراف']:
        await update.message.reply_text(
            "❌ **فرایند پیشنهاد دروس لغو شد.**\n\n"
            "برای شروع مجدد از دستور /recommend استفاده کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    # Parse preferences
    parsed_preferences = _parse_user_preferences(preferences_text)
    context.user_data['preferences'] = {
        **parsed_preferences,
        'preferences_type': 'custom',
        'raw_input': preferences_text
    }
    
    # Show confirmation and start generation
    await _show_preferences_confirmation(update, context)
    return WAITING_FINAL_CONFIRMATION


def _parse_user_preferences(text: str) -> dict:
    """Parse user preferences from text input."""
    
    preferences = {
        'desired_credits': None,
        'preferred_schedule': None,
        'interests': None,
        'priority': None,
        'additional_notes': None
    }
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if 'واحد' in key or 'credit' in key:
                preferences['desired_credits'] = value
            elif 'زمان' in key or 'schedule' in key:
                preferences['preferred_schedule'] = value
            elif 'علاقه' in key or 'interest' in key:
                preferences['interests'] = value
            elif 'اولویت' in key or 'priority' in key:
                preferences['priority'] = value
            elif 'یادداشت' in key or 'note' in key:
                preferences['additional_notes'] = value
    
    return preferences


async def _show_preferences_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show preferences confirmation."""
    
    preferences = context.user_data['preferences']
    semester = context.user_data['target_semester']
    
    confirmation_text = f"""
✅ **تنظیمات دریافت شد**

**ترم انتخابی:** {semester.replace('_', ' ').title()}

**ترجیحات شما:**
• تعداد واحد: {preferences.get('desired_credits', 'نامشخص')}
• زمان‌بندی: {preferences.get('preferred_schedule', 'نامشخص')}
• علاقه‌مندی: {preferences.get('interests', 'نامشخص')}
• اولویت: {preferences.get('priority', 'نامشخص')}
• یادداشت: {preferences.get('additional_notes', 'ندارد')}

🤖 **آماده تولید پیشنهاد هوشمند!**

این فرایند ممکن است تا 30 ثانیه طول بکشد.
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 شروع تولید پیشنهاد", callback_data="start_generation"),
            InlineKeyboardButton("🔧 ویرایش", callback_data="edit_preferences")
        ],
        [InlineKeyboardButton("❌ انصراف", callback_data="cancel_recommendation")]
    ])
    
    await update.message.reply_text(
        confirmation_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def handle_final_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle final confirmation and start generation."""
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_recommendation":
        await query.edit_message_text(
            "❌ **فرایند پیشنهاد دروس لغو شد.**\n\n"
            "برای شروع مجدد از دستور /recommend استفاده کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    if query.data == "edit_preferences":
        await _show_custom_preferences_form(query, context)
        return WAITING_PREFERENCES_INPUT
    
    if query.data == "start_generation":
        await _start_recommendation_generation(query, context)
        return ConversationHandler.END
    
    return WAITING_FINAL_CONFIRMATION


async def _start_recommendation_generation(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the recommendation generation process."""
    
    try:
        # Show loading message
        await query.edit_message_text(
            "🔄 **در حال تولید پیشنهاد هوشمند...**\n\n"
            "⏳ لطفاً منتظر بمانید، این فرایند تا 30 ثانیه طول می‌کشد.\n\n"
            "🤖 سیستم در حال تجزیه و تحلیل:\n"
            "• وضعیت تحصیلی شما\n"
            "• دروس موجود در ترم\n"
            "• قوانین دانشگاه\n"
            "• ترجیحات شما",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Extract data from context
        student_id = context.user_data['student_id']
        target_semester = context.user_data['target_semester']
        preferences = context.user_data.get('preferences', {})
        
        # Generate recommendations
        result = await recommendation_engine.generate_course_recommendations(
            student_id=student_id,
            target_semester=target_semester,
            user_preferences=preferences,
            use_llm=True
        )
        
        # Format and send results
        if result.get('recommendations', {}).get('final'):
            await _send_recommendation_results(query, result, context)
        else:
            await _send_recommendation_error(query, result)
            
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        await query.edit_message_text(
            "❌ **خطا در تولید پیشنهاد**\n\n"
            "متأسفانه در تولید پیشنهاد دروس مشکلی پیش آمد.\n"
            "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.\n\n"
            f"**جزئیات خطا:** {str(e)[:100]}...",
            parse_mode=ParseMode.MARKDOWN
        )


async def _send_recommendation_results(query, result: dict, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send formatted recommendation results."""
    
    try:
        final_recommendations = result['recommendations']['final']
        weekly_schedule = result['weekly_schedule']
        validation = result['validation']
        explanation = result['explanation']
        
        # Main recommendation message
        main_message = _format_main_recommendation(
            final_recommendations, 
            weekly_schedule,
            result['academic_context']
        )
        
        await query.edit_message_text(main_message, parse_mode=ParseMode.MARKDOWN)
        
        # Send detailed schedule
        schedule_message = _format_weekly_schedule(weekly_schedule)
        await query.message.reply_text(schedule_message, parse_mode=ParseMode.MARKDOWN)
        
        # Send analysis and tips
        if explanation:
            analysis_message = _format_analysis_and_tips(explanation, validation)
            await query.message.reply_text(analysis_message, parse_mode=ParseMode.MARKDOWN)
        
        # Send additional options
        options_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 پیشنهاد جدید", callback_data="new_recommendation"),
                InlineKeyboardButton("⚙️ تنظیمات", callback_data="adjust_preferences")
            ],
            [
                InlineKeyboardButton("💾 ذخیره پیشنهاد", callback_data="save_recommendation"),
                InlineKeyboardButton("📤 اشتراک‌گذاری", callback_data="share_recommendation")
            ]
        ])
        
        await query.message.reply_text(
            "🛠️ **گزینه‌های بیشتر:**",
            reply_markup=options_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error sending recommendation results: {e}")
        await query.edit_message_text(
            "❌ خطا در نمایش نتایج. لطفاً دوباره تلاش کنید.",
            parse_mode=ParseMode.MARKDOWN
        )


def _format_main_recommendation(recommendations: list, schedule: dict, academic_context: dict) -> str:
    """Format main recommendation message."""
    
    total_credits = schedule['total_credits']
    course_count = len(recommendations)
    gpa = academic_context['student_gpa']
    
    message = f"""
🎓 **پیشنهاد دروس تولید شد!**

📊 **خلاصه پیشنهاد:**
• مجموع واحدها: **{total_credits} واحد**
• تعداد دروس: **{course_count} درس**
• معدل فعلی شما: **{gpa:.2f}**

✅ **وضعیت پیشنهاد:**
• محدودیت واحدی: رعایت شده
• تداخل زمانی: بررسی شده
• قوانین دانشگاه: اعمال شده

🏆 **کیفیت پیشنهاد:**
• امتیاز تعادل: {schedule['balance_score']}/100
• تعداد تداخل: {len(schedule['conflicts'])}

📚 **دروس پیشنهادی:**
    """
    
    # Add course list
    for i, rec in enumerate(recommendations[:5], 1):  # Show first 5 courses
        priority_emoji = "🔥" if rec.priority_score >= 80 else "⭐" if rec.priority_score >= 60 else "💡"
        message += f"\n{i}. {priority_emoji} **{rec.course_name}** ({rec.course_code}) - {rec.credits} واحد"
    
    if len(recommendations) > 5:
        message += f"\n... و {len(recommendations) - 5} درس دیگر"
    
    message += "\n\n📋 **جدول زمانی کامل در پیام بعد ارسال می‌شود.**"
    
    return message


def _format_weekly_schedule(schedule: dict) -> str:
    """Format weekly schedule message."""
    
    weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
    
    message = "🗓️ **برنامه هفتگی کلاس‌ها:**\n\n"
    
    courses_by_day = schedule['courses_by_day']
    
    for day in weekdays:
        day_courses = courses_by_day.get(day, [])
        
        message += f"**{day}:**\n"
        
        if day_courses:
            for course in day_courses:
                time_info = ", ".join(course.time_slots) if course.time_slots else "زمان نامشخص"
                message += f"  • {course.course_name} ({course.course_code}) - {time_info}\n"
        else:
            message += "  • استراحت\n"
        
        message += "\n"
    
    # Add conflicts if any
    if schedule['conflicts']:
        message += "⚠️ **تداخل‌های احتمالی:**\n"
        for conflict in schedule['conflicts']:
            message += f"• {conflict}\n"
    
    return message


def _format_analysis_and_tips(explanation: dict, validation: dict) -> str:
    """Format analysis and tips message."""
    
    message = "💡 **تحلیل و توصیه‌ها:**\n\n"
    
    # Strategy explanation
    if explanation.get('strategy_rationale'):
        message += f"🎯 **استراتژی:** {explanation['strategy_rationale']}\n\n"
    
    # Priority analysis
    if explanation.get('priority_explanation'):
        message += "📋 **اولویت‌بندی دروس:**\n"
        for priority, courses in explanation['priority_explanation'].items():
            message += f"• {priority}: {', '.join(courses[:3])}\n"
        message += "\n"
    
    # Balance analysis
    balance_analysis = explanation.get('balance_analysis', {})
    if balance_analysis:
        message += f"⚖️ **تعادل برنامه:** {balance_analysis.get('distribution_quality', 'خوب')}\n"
        message += f"📊 **امتیاز تعادل:** {balance_analysis.get('balance_score', 0)}/100\n\n"
    
    # Validation warnings
    if validation.get('warnings'):
        message += "⚠️ **نکات مهم:**\n"
        for warning in validation['warnings'][:3]:
            message += f"• {warning}\n"
        message += "\n"
    
    # Next steps
    if explanation.get('next_steps'):
        message += "📝 **مراحل بعدی:**\n"
        for step in explanation['next_steps'][:4]:
            message += f"• {step}\n"
    
    return message


async def _send_recommendation_error(query, result: dict) -> None:
    """Send error message when recommendation fails."""
    
    error_message = f"""
❌ **تولید پیشنهاد ناموفق**

متأسفانه نتوانستیم پیشنهاد مناسبی برای شما تولید کنیم.

**احتمالی دلایل:**
• دروس کافی در ترم انتخابی ارائه نمی‌شود
• محدودیت‌های گروهی شما
• عدم وجود اطلاعات کافی در پروفایل

**راه‌حل‌های پیشنهادی:**
• ترم دیگری را انتخاب کنید
• نمرات خود را تکمیل کنید (/grades)
• با تنظیمات مختلف دوباره تلاش کنید
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 تلاش مجدد", callback_data="retry_recommendation"),
            InlineKeyboardButton("⚙️ تنظیمات مختلف", callback_data="new_preferences")
        ]
    ])
    
    await query.edit_message_text(
        error_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def _calculate_student_gpa_in_session(db, student_id: int) -> float:
    """Calculate student's current GPA within a database session."""
    
    from app.models.student import StudentGrade
    from app.models.course import Course
    from sqlalchemy.orm import selectinload
    
    # Get all grades for the student with course info
    result = await db.execute(
        select(StudentGrade)
        .options(selectinload(StudentGrade.course))
        .where(StudentGrade.student_id == student_id)
    )
    grades = result.scalars().all()
    
    if not grades:
        return 0.0
    
    total_points = 0.0
    total_credits = 0
    
    # Group grades by course to get latest attempt
    course_grades = {}
    for grade in grades:
        course_code = grade.course.course_code
        if course_code not in course_grades or grade.attempt_number > course_grades[course_code].attempt_number:
            course_grades[course_code] = grade
    
    # Calculate GPA from latest attempts (both passed and confirmed)
    for grade in course_grades.values():
        if grade.status in ["passed", "confirmed"]:
            credits = grade.course.theoretical_credits + grade.course.practical_credits
            total_points += float(grade.grade) * credits  # Convert Decimal to float
            total_credits += credits
    
    return total_points / total_credits if total_credits > 0 else 0.0


async def _calculate_student_gpa(student: Student) -> float:
    """Calculate student's current GPA (deprecated - use _calculate_student_gpa_in_session)."""
    
    if not student.grades:
        return 0.0
    
    total_points = 0.0
    total_credits = 0
    
    # Group grades by course to get latest attempt
    course_grades = {}
    for grade in student.grades:
        course_code = grade.course.course_code
        if course_code not in course_grades or grade.attempt_number > course_grades[course_code].attempt_number:
            course_grades[course_code] = grade
    
    # Calculate GPA from latest attempts
    for grade in course_grades.values():
        if grade.status == "confirmed":
            credits = grade.course.theoretical_credits + grade.course.practical_credits
            total_points += grade.grade * credits
            total_credits += credits
    
    return total_points / total_credits if total_credits > 0 else 0.0


async def cancel_recommendation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel recommendation flow."""
    
    await update.message.reply_text(
        "❌ **فرایند پیشنهاد دروس لغو شد.**\n\n"
        "برای شروع مجدد از دستور /recommend استفاده کنید.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END