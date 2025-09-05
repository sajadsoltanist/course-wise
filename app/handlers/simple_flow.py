"""
Simplified single-step handler for CourseWise recommendations.

Replaces complex multi-step conversation with one simple interaction.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from app.core.database import get_db
from app.models import Student
from app.services.simple_recommendation import SimpleRecommendationService
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_GRADES = 1


class SimpleFlowHandler:
    """
    Simplified handler for course recommendations.
    
    Flow:
    1. /start or /recommend - ask for basic info + grades
    2. Process everything with LLM 
    3. Return recommendations
    """
    
    def __init__(self):
        self.recommendation_service = SimpleRecommendationService()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /start command - begin recommendation process"""
        
        user_id = update.effective_user.id
        
        try:
            # Check if student exists in database
            async with get_db() as db:
                result = await db.execute(
                    select(Student).where(Student.telegram_user_id == user_id)
                )
                student = result.scalar_one_or_none()
            
            if student and student.entry_year and student.current_semester:
                # Existing student - ask for grades directly
                await update.message.reply_text(
                    f"سلام! 👋\n\n"
                    f"ورودی: {student.entry_year}\n"
                    f"ترم فعلی: {student.current_semester}\n\n"
                    f"لطفاً اطلاعات زیر رو برام بفرست:\n\n"
                    f"**نمرات تمام دروس گذرانده شده:**\n"
                    f"مثال: ریاضی عمومی ۱: 17.5، فیزیک ۱: 16، زبان پیش: 15\n\n"
                    f"**معدل ترم قبل:** مثلاً 16.2\n\n"
                    f"**معدل کل تا الان:** مثلاً 15.8\n\n"
                    f"همه رو در یک پیام بفرست تا بتونم بهترین دروس رو پیشنهاد بدم.",
                    parse_mode='Markdown'
                )
                return WAITING_FOR_GRADES
                
            else:
                # New student - ask for basic info first
                await update.message.reply_text(
                    f"سلام! 👋 به CourseWise خوش اومدی\n\n"
                    f"من مشاور هوشمند انتخاب واحد دانشگاه آزاد شهرکردم.\n\n"
                    f"لطفاً اطلاعات زیر رو برام بفرست:\n\n"
                    f"**سال ورودی:** مثلاً 1401 یا 1403\n\n"
                    f"**ترم فعلی:** مثلاً 4\n\n"
                    f"**نمرات تمام دروس گذرانده شده:**\n"
                    f"مثال: ریاضی عمومی ۱: 17.5، فیزیک ۱: 16، زبان پیش: 15\n\n"
                    f"**معدل ترم قبل:** مثلاً 16.2\n\n"
                    f"**معدل کل تا الان:** مثلاً 15.8\n\n"
                    f"همه رو در یک پیام بفرست.",
                    parse_mode='Markdown'
                )
                return WAITING_FOR_GRADES
        
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await update.message.reply_text(
                "متأسفانه مشکلی پیش اومد. لطفاً مجدداً تلاش کنید."
            )
            return ConversationHandler.END
    
    async def recommend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /recommend command - same as start"""
        return await self.start_command(update, context)
    
    async def process_grades_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process the complete input and generate recommendations"""
        
        user_id = update.effective_user.id
        user_input = update.message.text
        
        try:
            # Parse user input to extract info
            parsed_info = self._parse_user_input(user_input)
            logger.info(f"Parsed user input: {parsed_info}")
            
            if not parsed_info["valid"]:
                await update.message.reply_text(
                    f"❌ {parsed_info['error']}\n\n"
                    f"لطفاً دوباره اطلاعات رو به این شکل بفرست:\n"
                    f"ورودی: 1403\n"
                    f"ترم: 4\n"
                    f"نمرات: ریاضی عمومی ۱: 17، فیزیک ۱: 16\n"
                    f"معدل ترم قبل: 16.2\n"
                    f"معدل کل: 15.8"
                )
                return WAITING_FOR_GRADES
            
            # Update student info in database
            await self._update_student_info(user_id, parsed_info)
            
            # Show processing message
            processing_msg = await update.message.reply_text(
                "🔄 در حال تحلیل نمرات و آماده کردن پیشنهادات...\n"
                "این کار ممکنه چند ثانیه طول بکشه."
            )
            
            # Get recommendation from LLM
            recommendation = await self.recommendation_service.get_recommendation(
                student_entry_year=int(parsed_info["entry_year"]),
                current_semester=parsed_info["current_semester"], 
                raw_grades=parsed_info["raw_grades"],
                last_semester_gpa=parsed_info["last_semester_gpa"],
                overall_gpa=parsed_info["overall_gpa"]
            )
            
            # Delete processing message
            await processing_msg.delete()
            
            if recommendation.get("success"):
                await self._send_recommendations(update, recommendation)
            else:
                await update.message.reply_text(
                    f"❌ متأسفانه نتونستم پیشنهاد مناسبی تهیه کنم.\n\n"
                    f"خطا: {recommendation.get('error', 'نامشخص')}\n\n"
                    f"لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
            
            return ConversationHandler.END
        
        except Exception as e:
            logger.error(f"Error processing grades: {e}")
            await update.message.reply_text(
                "❌ متأسفانه مشکلی در پردازش اطلاعات پیش اومد.\n"
                "لطفاً مجدداً تلاش کنید."
            )
            return ConversationHandler.END
    
    def _parse_user_input(self, text: str) -> dict:
        """Parse user input to extract all required information"""
        
        import re
        
        result = {
            "valid": False,
            "error": "",
            "entry_year": None,
            "current_semester": None,
            "raw_grades": "",
            "last_semester_gpa": None,
            "overall_gpa": None
        }
        
        try:
            # Extract entry year
            entry_match = re.search(r'(?:ورودی|سال ورودی)[:\s]*(\d{4})', text)
            if entry_match:
                result["entry_year"] = entry_match.group(1)
            
            # Extract current semester  
            semester_match = re.search(r'(?:ترم|ترم فعلی)[:\s]*(\d+)', text)
            if semester_match:
                result["current_semester"] = int(semester_match.group(1))
            
            # Extract last semester GPA
            last_gpa_match = re.search(r'(?:معدل ترم قبل|معدل پیش)[:\s]*(\d+\.?\d*)', text)
            if last_gpa_match:
                result["last_semester_gpa"] = float(last_gpa_match.group(1))
            
            # Extract overall GPA
            overall_gpa_match = re.search(r'(?:معدل کل|معدل کلی)[:\s]*(\d+\.?\d*)', text)
            if overall_gpa_match:
                result["overall_gpa"] = float(overall_gpa_match.group(1))
            
            # Extract raw grades (everything else)
            # Remove the structured parts and keep the grades
            grades_text = text
            for pattern in [r'(?:ورودی|سال ورودی)[:\s]*\d{4}', r'(?:ترم|ترم فعلی)[:\s]*\d+', 
                          r'(?:معدل ترم قبل|معدل پیش)[:\s]*\d+\.?\d*', r'(?:معدل کل|معدل کلی)[:\s]*\d+\.?\d*']:
                grades_text = re.sub(pattern, '', grades_text)
            
            result["raw_grades"] = grades_text.strip()
            
            # Validation
            required_fields = ["entry_year", "current_semester", "last_semester_gpa", "overall_gpa"]
            missing = [field for field in required_fields if result[field] is None]
            
            if missing:
                result["error"] = f"اطلاعات ناقص: {', '.join(missing)}"
                return result
            
            if not result["raw_grades"]:
                result["error"] = "نمرات دروس یافت نشد"
                return result
            
            result["valid"] = True
            return result
            
        except Exception as e:
            result["error"] = f"خطا در پردازش اطلاعات: {str(e)}"
            return result
    
    async def _update_student_info(self, user_id: int, info: dict):
        """Update student information in database"""
        
        try:
            async with get_db() as db:
                # Get existing student or create new one
                result = await db.execute(
                    select(Student).where(Student.telegram_user_id == user_id)
                )
                student = result.scalar_one_or_none()
                
                if student:
                    # Update existing
                    student.entry_year = int(info["entry_year"]) 
                    student.current_semester = info["current_semester"]
                else:
                    # Create new
                    student = Student(
                        telegram_user_id=user_id,
                        entry_year=int(info["entry_year"]),
                        current_semester=info["current_semester"],
                        is_active=True
                    )
                    db.add(student)
                
                await db.commit()
                logger.info(f"Updated student info for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to update student info: {e}")
            # Don't fail the whole process for this
    
    async def _send_recommendations(self, update: Update, recommendation: dict):
        """Send formatted recommendations to user"""
        
        try:
            rec_data = recommendation.get("recommendations", {})
            metadata = recommendation.get("metadata", {})
            
            # Header message
            header = f"✅ **پیشنهادات درسی**\n\n"
            header += f"📊 **اطلاعات دانشجو:**\n"
            header += f"• ورودی: {metadata.get('entry_year', 'نامشخص')}\n"
            header += f"• ترم فعلی: {metadata.get('current_semester', 'نامشخص')}\n"
            header += f"• {metadata.get('credit_limit', 'محدودیت واحد نامشخص')}\n\n"
            
            # Mapped grades
            mapped_grades = rec_data.get("mapped_grades", [])
            if mapped_grades:
                header += f"📚 **نمرات تطبیق داده شده:**\n"
                for grade in mapped_grades[:10]:  # محدود کردن تعداد
                    header += f"• {grade.get('course_name', '')}: {grade.get('grade', '')}\n"
                header += "\n"
            
            # Course recommendations
            courses = rec_data.get("courses", [])
            if courses:
                header += f"🎯 **دروس پیشنهادی:**\n"
                for course in courses[:8]:  # حداکثر 8 درس
                    header += f"• **{course.get('course_name', '')}** ({course.get('course_code', '')})\n"
                    if course.get('reason'):
                        header += f"  ↳ {course['reason']}\n"
                header += "\n"
            
            # Analysis
            analysis = rec_data.get("analysis", "")
            if analysis:
                header += f"📝 **تحلیل:**\n{analysis}\n\n"
            
            header += f"💡 **نکته:** این پیشنهادات بر اساس تحلیل هوشمند ارائه شده. حتماً با مشاور دانشکده نیز مشورت کنید."
            
            # Send with action buttons
            keyboard = [
                [InlineKeyboardButton("🔄 پیشنهاد جدید", callback_data="new_recommendation")],
                [InlineKeyboardButton("📋 راهنمای انتخاب واحد", callback_data="help_guide")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                header,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error sending recommendations: {e}")
            await update.message.reply_text(
                "✅ پیشنهادات آماده شد ولی مشکلی در نمایش پیش اومد.\n"
                "لطفاً دوباره تلاش کنید."
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline buttons"""
        
        query = update.callback_query
        await query.answer()
        
        if query.data == "new_recommendation":
            await query.edit_message_text(
                "برای پیشنهاد جدید، دستور /recommend رو بزن و اطلاعات جدید رو وارد کن."
            )
        
        elif query.data == "help_guide":
            help_text = """📋 **راهنمای انتخاب واحد**

🔹 **محدودیت واحدها:**
• معدل زیر 12: حداکثر 14 واحد (مشروط)
• معدل 12-17: حداکثر 20 واحد
• معدل 17 به بالا: حداکثر 24 واحد

🔹 **نکات مهم:**
• پیش‌نیازها رو رعایت کنید
• دروس عمومی زمان‌بندی ندارند
• با مشاور دانشکده مشورت کنید

🔹 **برای پیشنهاد جدید:**
دستور /recommend رو بزنید"""
            
            await query.edit_message_text(help_text, parse_mode='Markdown')
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the conversation"""
        await update.message.reply_text("❌ عملیات لغو شد.")
        return ConversationHandler.END


def create_conversation_handler() -> ConversationHandler:
    """Create the simplified conversation handler"""
    
    handler = SimpleFlowHandler()
    
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", handler.start_command),
            CommandHandler("recommend", handler.recommend_command),
        ],
        states={
            WAITING_FOR_GRADES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.process_grades_input)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handler.cancel),
            CallbackQueryHandler(handler.handle_callback)
        ],
        allow_reentry=True
    )