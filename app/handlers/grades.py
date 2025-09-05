"""
Grade input and processing handlers for CourseWise bot.

This module handles the grade input flow including text parsing,
LLM processing, confirmation, and database storage.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from loguru import logger

from app.core.database import get_db
from app.utils.session import DatabaseSessionManager
from app.services.llm import LLMService
from app.models.student import Student, StudentGrade
from app.models.course import Course
from sqlalchemy import select


# Get service instances
session_manager = DatabaseSessionManager()
llm_service = LLMService()


async def grades_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle /grades command and begin grade input flow.
    
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
            # Check if user is registered
            result = await db.execute(
                select(Student).where(Student.telegram_user_id == user_id)
            )
            student = result.scalar_one_or_none()
            
            if not student:
                await update.message.reply_text(
                    "❌ **ثبت‌نام نشده‌اید**\n\n"
                    "ابتدا باید ثبت‌نام کنید تا بتوانید نمرات وارد کنید.\n"
                    "از /start برای ثبت‌نام پروفایل استفاده کنید.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # Create new session for grade input
            await session_manager.create_session(
                db, user_id, initial_step="waiting_grades"
            )
            
            # Store student info in session
            await session_manager.set_session_data(db, user_id, "student_id", student.id)
            await session_manager.set_session_data(db, user_id, "student_info", {
                "student_number": student.student_number,
                "major": student.major,
                "semester": student.current_semester,
                "entry_year": student.entry_year
            })
        
        grades_intro_text = f"""
📊 **وارد کردن نمرات**

سلام {student.first_name}! بیایید نمرات تحصیلی شما را وارد کنیم تا توصیه‌های شخصی‌سازی شده ارائه دهیم.

**نحوه وارد کردن نمرات:**

می‌توانید نمرات را در فرمت‌های مختلف وارد کنید:
• `ریاضی1: 18, برنامه‌سازی: 17, فیزیک: مردود`
• `ساختمان داده = 19.5, حساب دیفرانسیل: 15`
• `برنامه‌سازی: قبول, آمار: 12.5`

**فرمت‌های پشتیبانی شده:**
• کد درس (CS101, MATH201 و غیره)
• نام درس (برنامه‌سازی, حساب دیفرانسیل و غیره)
• نمرات: مقیاس ۰-۲۰ یا قبول/مردود
• چندین درس جدا شده با کاما

**مثال:**
```
ریاضی1: 18
برنامه‌سازی: 17.5
فیزیک1: مردود
ساختمان_داده: 19
حساب_دیفرانسیل: 16
```

لطفاً نمرات خود را وارد کنید:
        """
        
        await update.message.reply_text(grades_intro_text, parse_mode=ParseMode.MARKDOWN)
        
        logger.info(f"Started grade input flow for user {user_id} (student: {student.student_number})")
        
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_GRADES
        
    except Exception as e:
        logger.error(f"Error in grades command for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong. Please try again with /grades.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


async def process_grade_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Process grade text input using LLM parsing.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    grade_text = update.message.text.strip()
    
    try:
        # Show processing message
        processing_msg = await update.message.reply_text(
            "🤖 **در حال پردازش نمرات شما...**\n\n"
            "از هوش مصنوعی برای تجزیه و اعتبارسنجی ورودی استفاده می‌کنم...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        async with get_db() as db:
            # Get valid course codes and names from database
            result = await db.execute(select(Course.course_code, Course.course_name))
            course_list = [{"code": row[0], "name": row[1]} for row in result.fetchall()]
            
            # Parse grades using LLM service
            parse_result = await llm_service.parse_grades_text(grade_text, course_list)
            
            if not parse_result.success or not parse_result.parsed_grades:
                await processing_msg.edit_text(
                    "❌ **نتوانستم نمرات را تجزیه کنم**\n\n"
                    f"خطا: {parse_result.error_message or 'هیچ نمره‌ای در ورودی شما پیدا نشد'}\n\n"
                    "لطفاً با فرمت واضح‌تری دوباره تلاش کنید:\n"
                    "• `ریاضی1: 18, برنامه‌سازی: 17`\n"
                    "• `برنامه‌سازی: 19, حساب_دیفرانسیل: مردود`",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                from app.services.bot import CourseWiseBot
                return CourseWiseBot.WAITING_GRADES
            
            # Store parsed grades in session
            await session_manager.update_session(
                db, user_id,
                current_step="confirming_grades",
                session_data={
                    "parsed_grades": [
                        {
                            "course_code": grade.course_code,
                            "course_name": grade.course_name,
                            "grade": grade.grade,
                            "status": grade.status,
                            "semester_taken": grade.semester_taken,
                            "confidence": grade.confidence
                        }
                        for grade in parse_result.parsed_grades
                    ],
                    "parse_confidence": parse_result.confidence,
                    "parse_warnings": parse_result.warnings,
                    "original_text": grade_text
                }
            )
        
        # Format grades for confirmation
        formatted_grades = llm_service.format_grades_for_confirmation(parse_result)
        
        # Create confirmation message
        confirmation_text = f"""
{formatted_grades}

**Please review and confirm:**
• ✅ **Confirm** - Save these grades
• ✏️ **Edit** - Make corrections
• ❌ **Cancel** - Start over
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_grades"),
                InlineKeyboardButton("✏️ Edit", callback_data="edit_grades")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_grades")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            confirmation_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        logger.info(f"Parsed {len(parse_result.parsed_grades)} grades for user {user_id}")
        
        from app.services.bot import CourseWiseBot
        bot_instance = CourseWiseBot()
        return bot_instance.CONFIRMING_GRADES
        
    except Exception as e:
        logger.error(f"Error processing grade text for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Something went wrong while processing your grades. Please try again.",
            parse_mode=ParseMode.MARKDOWN
        )
        from app.services.bot import CourseWiseBot
        return CourseWiseBot.WAITING_GRADES


async def confirm_parsed_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle grade confirmation callback.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        ConversationHandler.END or other state
    """
    if not update.effective_user or not update.callback_query:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "cancel_grades":
            # Cancel and clean up session
            async with get_db() as db:
                await session_manager.delete_session(db, user_id)
            
            await query.edit_message_text(
                "❌ **ورود نمرات لغو شد**\n\n"
                "هر وقت آماده بودید با /grades دوباره شروع کنید.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        elif query.data == "edit_grades":
            # Allow user to make corrections
            await query.edit_message_text(
                "✏️ **ویرایش نمرات شما**\n\n"
                "لطفاً نمرات اصلاح شده را به این فرمت وارد کنید:\n"
                "• `CS101: 18, MATH201: 17`\n"
                "• `برنامه‌سازی: 19, ریاضی: رد شده`",
                parse_mode=ParseMode.MARKDOWN
            )
            
            from app.services.bot import CourseWiseBot
            return CourseWiseBot.WAITING_GRADES
        
        elif query.data == "confirm_grades":
            # Save grades to database
            async with get_db() as db:
                session = await session_manager.get_session(db, user_id)
                if not session:
                    raise RuntimeError("Session lost during confirmation")
                
                student_id = session.get_data("student_id")
                parsed_grades = session.get_data("parsed_grades")
                student_info = session.get_data("student_info")
                
                if not student_id or not parsed_grades or not student_info:
                    raise RuntimeError("Missing session data for grade confirmation")
                
                # Create elective records for each grade
                saved_count = 0
                for grade_data in parsed_grades:
                    # Skip grades without course codes - try to resolve from name first
                    course_code = grade_data.get("course_code")
                    if not course_code:
                        # Try to get course code from course name
                        course_name = grade_data.get("course_name")
                        if course_name:
                            from app.utils.curriculum import get_course_code_by_name
                            course_code = get_course_code_by_name(course_name)
                            if course_code:
                                grade_data["course_code"] = course_code
                                logger.info(f"Mapped course name '{course_name}' to code '{course_code}'")
                        
                        if not course_code:
                            logger.warning(f"Skipping grade with no course code: {grade_data}")
                            continue
                    
                    # Check if course exists, create if needed
                    result = await db.execute(
                        select(Course).where(Course.course_code == course_code)
                    )
                    course = result.scalar_one_or_none()
                    
                    if not course:
                        # Get course info from curriculum data
                        from app.utils.curriculum import get_course_info_by_code_or_name
                        
                        student_entry_year = student_info.get("entry_year", 1403)
                        curriculum_course = get_course_info_by_code_or_name(
                            course_code, 
                            student_entry_year
                        )
                        
                        if curriculum_course:
                            # Create course from curriculum data
                            course = Course(
                                course_code=course_code,
                                course_name=curriculum_course["course_name"],
                                theoretical_credits=curriculum_course["theoretical_credits"],
                                practical_credits=curriculum_course["practical_credits"],
                                course_type=curriculum_course["course_type"],
                                semester_recommended=curriculum_course.get("semester_recommended"),
                                entry_year=student_entry_year,
                                is_mandatory=curriculum_course["is_mandatory"]
                            )
                        else:
                            # Fallback: create with default values but warn user
                            course_name = grade_data.get("course_name") or course_code
                            
                            course = Course(
                                course_code=course_code,
                                course_name=course_name,
                                theoretical_credits=3,  # Default
                                practical_credits=0,   # Default
                                course_type="general",  # Safe default
                                entry_year=student_entry_year,
                                is_mandatory=False
                            )
                            
                            logger.warning(f"Course {course_code} not found in curriculum for entry year {student_entry_year}, using defaults")
                        db.add(course)
                        await db.flush()  # Get the course ID
                    
                    # Check if grade record already exists
                    result = await db.execute(
                        select(StudentGrade).where(
                            StudentGrade.student_id == student_id,
                            StudentGrade.course_id == course.id
                        )
                    )
                    existing_grade = result.scalar_one_or_none()
                    
                    if existing_grade:
                        # Update existing record with new attempt
                        existing_grade.grade = grade_data["grade"]
                        existing_grade.status = grade_data["status"]
                        if grade_data.get("semester_taken"):
                            existing_grade.semester_taken = grade_data["semester_taken"]
                        existing_grade.attempt_number = existing_grade.attempt_number + 1
                    else:
                        # Create new grade record
                        student_grade = StudentGrade(
                            student_id=student_id,
                            course_id=course.id,
                            grade=grade_data["grade"],
                            status=grade_data["status"],
                            semester_taken=grade_data.get("semester_taken"),
                            attempt_number=1
                        )
                        db.add(student_grade)
                    
                    saved_count += 1
                
                await db.commit()
                
                # Clean up session
                await session_manager.delete_session(db, user_id)
            
            success_text = f"""
🎉 **نمرات با موفقیت ذخیره شد!**

✅ **{saved_count} نمره** به پروفایل شما اضافه شد.

**گام بعدی چیست؟**
• افزودن نمرات بیشتر با /grades
• دریافت پیشنهاد دروس با /recommend
• بررسی پروفایل با /status  
• مشاهده همه دستورات با /help

پروفایل تحصیلی شما در حال رشد است! 📈
            """
            
            await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
            
            logger.info(f"Saved {saved_count} grades for user {user_id}")
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Error confirming grades for user {user_id}: {e}")
        await query.edit_message_text(
            "❌ **ذخیره نمرات با خطا مواجه شد**\n\n"
            "مشکلی در ذخیره نمرات شما به وجود آمد. لطفاً دوباره با /grades تلاش کنید.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    return ConversationHandler.END


async def handle_grade_corrections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle manual grade corrections during confirmation.
    
    Args:
        update: Telegram update object
        context: Bot context
        
    Returns:
        Next conversation state
    """
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    correction_text = update.message.text.strip()
    
    # Process the correction text same as initial grade input
    return await process_grade_text(update, context)