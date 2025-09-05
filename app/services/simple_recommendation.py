"""
Simple LLM-based recommendation service for CourseWise.

Replaces complex context assembly and rule engines with direct LLM processing.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


class SimpleRecommendationService:
    """
    Simplified course recommendation service using LLM for all processing.
    
    Flow:
    1. Load static data (curriculum + offerings)
    2. Create simple text prompts 
    3. Let LLM handle course mapping + recommendations
    4. Return structured response
    """
    
    def __init__(self):
        self.llm = LLMService()
        self.data_path = Path("data")
    
    async def get_recommendation(
        self,
        student_entry_year: int,
        current_semester: int,
        raw_grades: str,
        last_semester_gpa: float,
        overall_gpa: float,
        target_semester: str = "mehr_1404"
    ) -> Dict[str, Any]:
        """
        Get course recommendation using LLM-based processing.
        
        Args:
            student_entry_year: Entry year like 1401, 1403 
            current_semester: Current semester number
            raw_grades: Raw grade text from user
            last_semester_gpa: GPA from previous semester
            overall_gpa: Cumulative GPA
            target_semester: Target semester for recommendations
            
        Returns:
            Dict with recommendations and metadata
        """
        
        try:
            # 1. Load static data files
            curriculum = self._load_curriculum(student_entry_year)
            offerings = self._load_offerings(target_semester, student_entry_year, current_semester)
            
            # 2. Calculate academic constraints
            credit_limit = self._get_credit_limit(overall_gpa)
            
            # 3. Create simple prompt for LLM
            prompt = self._create_recommendation_prompt(
                entry_year=student_entry_year,
                current_semester=current_semester,
                raw_grades=raw_grades,
                last_semester_gpa=last_semester_gpa,
                overall_gpa=overall_gpa,
                curriculum=curriculum,
                offerings=offerings,
                credit_limit=credit_limit
            )
            
            # 4. Get LLM recommendation
            logger.info(f"Getting recommendation for entry_year={student_entry_year}, semester={current_semester}")
            
            response = await self.llm.generate_course_recommendations(
                context=prompt,
                student_preferences={},
                available_courses=[]
            )
            
            if not response or not response.get("success"):
                logger.warning("LLM recommendation failed, using fallback")
                return self._create_fallback_response()
            
            # 5. Structure response
            return {
                "success": True,
                "recommendations": response.get("recommendations", {}),
                "metadata": {
                    "entry_year": student_entry_year,
                    "current_semester": current_semester,
                    "target_semester": target_semester,
                    "credit_limit": credit_limit,
                    "overall_gpa": overall_gpa
                }
            }
            
        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": self._create_fallback_response()
            }
    
    def _load_curriculum(self, entry_year: int) -> str:
        """Load curriculum chart based on entry year"""
        
        try:
            if entry_year >= 1403:
                file_path = self.data_path / "curriculum_1403_onwards.json"
            else:
                file_path = self.data_path / "curriculum_before_1403.json"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Convert to simple text format for LLM
            return self._format_curriculum_for_llm(data)
            
        except Exception as e:
            logger.error(f"Failed to load curriculum for {entry_year}: {e}")
            return "چارت درسی در دسترس نیست"
    
    def _load_offerings(self, semester: str, student_entry_year: int = None, student_semester: int = None) -> str:
        """Load course offerings for target semester with proper filtering"""
        
        try:
            # Try new structure first, fallback to old
            file_path = self.data_path / "offerings" / f"{semester}_new.json"
            if not file_path.exists():
                file_path = self.data_path / "offerings" / f"{semester}.json"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert to simple text format with smart filtering
            return self._format_offerings_for_llm(data, student_entry_year, student_semester)
            
        except Exception as e:
            logger.error(f"Failed to load offerings for {semester}: {e}")
            return "لیست دروس ارائه شده در دسترس نیست"
    
    
    def _get_credit_limit(self, gpa: float) -> str:
        """Calculate credit limit based on GPA"""
        
        if gpa < 12.0:
            return "مشروط: حداکثر 14 واحد"
        elif gpa >= 17.0:
            return "عالی: حداکثر 24 واحد"
        else:
            return "معمولی: حداکثر 20 واحد"
    
    def _format_curriculum_for_llm(self, curriculum: Dict) -> str:
        """Convert curriculum JSON to simple text for LLM"""
        
        text = f"چارت درسی ورودی {curriculum.get('entry_years', [])}\n"
        text += f"تعداد کل واحدها: {curriculum.get('total_credits_required', 140)}\n\n"
        
        semesters = curriculum.get("semesters", {})
        for semester_num, semester_data in semesters.items():
            text += f"ترم {semester_num}: {semester_data.get('semester_name', '')}\n"
            
            for course in semester_data.get("courses", []):
                text += f"  - {course.get('course_code', '')}: {course.get('course_name', '')} "
                text += f"({course.get('theoretical_credits', 0)}+{course.get('practical_credits', 0)} واحد)\n"
            text += "\n"
        
        return text
    
    def _format_offerings_for_llm(self, offerings: Dict, student_entry_year: int = None, student_semester: int = None) -> str:
        """Convert offerings to text format for LLM"""
        
        text = f"دروس ارائه شده ترم {offerings.get('semester', '')}\n\n"
        
        # Include all courses
        if "entry_year_groups" in offerings:
            text += self._format_all_offerings_structure(offerings)
        else:
            # Use old format
            text += self._format_old_offerings_structure(offerings)
        
        return text
    
    def _format_all_offerings_structure(self, offerings: Dict) -> str:
        """Format all offerings without filtering"""
        
        text = ""
        
        # Entry year specific courses
        entry_year_groups = offerings.get("entry_year_groups", {})
        if entry_year_groups:
            text += "🎓 دروس مخصوص سال ورودی:\n\n"
            
            for entry_year_key, group_data in entry_year_groups.items():
                entry_year_display = "1403 به بعد" if entry_year_key == "1403" else "1402 و قبل"
                text += f"  📅 ورودی {entry_year_display}:\n"
                
                semesters = group_data.get("semesters", {})
                for semester_key in sorted(semesters.keys()):
                    semester_data = semesters[semester_key]
                    text += f"    ترم {semester_key}:\n"
                    
                    for course in semester_data.get("courses", []):
                        credits = course.get("credits", {})
                        theoretical = credits.get("theoretical", 0)
                        practical = credits.get("practical", 0)
                        text += f"      - {course.get('course_code')}: {course.get('course_name')} "
                        text += f"({theoretical}+{practical} واحد)"
                        if course.get('instructor'):
                            text += f" - استاد: {course['instructor']}"
                        text += "\n"
                    text += "\n"
                text += "\n"
        
        # Open courses (semester 3+)
        open_courses = offerings.get("open_courses", {})
        if open_courses.get("courses"):
            text += "📚 دروس آزاد (ترم 3 به بعد):\n"
            
            # Group by target semester for better organization
            courses_by_semester = {}
            for course in open_courses["courses"]:
                target_semesters = course.get("target_semesters", [])
                for semester in target_semesters:
                    if semester not in courses_by_semester:
                        courses_by_semester[semester] = []
                    courses_by_semester[semester].append(course)
            
            # Show courses by semester
            for semester in sorted(courses_by_semester.keys()):
                text += f"\n  دروس ترم {semester}:\n"
                for course in courses_by_semester[semester]:
                    credits = course.get("credits", {})
                    theoretical = credits.get("theoretical", 0)
                    practical = credits.get("practical", 0)
                    text += f"    - {course.get('course_code')}: {course.get('course_name')} "
                    text += f"({theoretical}+{practical} واحد)"
                    if course.get('instructor'):
                        text += f" - استاد: {course['instructor']}"
                    text += "\n"
            text += "\n"
        
        # General courses
        general_courses = offerings.get("general_courses", {})
        if general_courses.get("courses"):
            text += "🌐 دروس عمومی (همه ارائه می‌شوند):\n"
            text += general_courses.get("description", "") + "\n\n"
            
            # Group by type
            courses_by_type = {}
            for course in general_courses["courses"]:
                course_type = course.get("type", "عمومی")
                if course_type not in courses_by_type:
                    courses_by_type[course_type] = []
                courses_by_type[course_type].append(course)
            
            for course_type, courses in courses_by_type.items():
                text += f"  {course_type}:\n"
                for course in courses:
                    credits = course.get("credits", {})
                    theoretical = credits.get("theoretical", 0)
                    practical = credits.get("practical", 0)
                    text += f"    - {course.get('course_code')}: {course.get('course_name')} "
                    text += f"({theoretical}+{practical} واحد)\n"
                text += "\n"
            
            # Add rules
            rules = general_courses.get("rules", {})
            if rules:
                text += "📋 قوانین دروس عمومی:\n"
                if rules.get("معارف"):
                    text += f"  - {rules['معارف']}\n"
                for rule in rules.get("special_rules", []):
                    text += f"  - {rule}\n"
                text += "\n"
        
        # Special projects
        special_projects = offerings.get("special_projects", [])
        if special_projects:
            text += "🏗️ پروژه‌ها و کارآموزی:\n"
            for project in special_projects:
                credits = project.get("credits", {})
                theoretical = credits.get("theoretical", 0)
                practical = credits.get("practical", 0)
                text += f"  - {project.get('course_code')}: {project.get('course_name')} "
                text += f"({theoretical}+{practical} واحد)\n"
            text += "\n"
        
        return text
    

    def _format_old_offerings_structure(self, offerings: Dict) -> str:
        """Handle old offerings format"""
        
        text = ""
        groups = offerings.get("available_groups", offerings.get("course_groups", []))
        
        for group in groups:
            group_name = group.get("group_name", "")
            text += f"گروه {group_name}:\n"
            
            courses = group.get("courses", [])
            for course in courses:
                text += f"  - {course.get('course_code', '')}: {course.get('course_name', '')}"
                if course.get('instructor'):
                    text += f" (استاد: {course['instructor']})"
                text += "\n"
            text += "\n"
        
        return text
    
    def _format_old_offerings_structure(self, offerings: Dict) -> str:
        """Handle old offerings format"""
        
        text = ""
        groups = offerings.get("available_groups", offerings.get("course_groups", []))
        
        for group in groups:
            group_name = group.get("group_name", "")
            text += f"گروه {group_name}:\n"
            
            courses = group.get("courses", [])
            for course in courses:
                text += f"  - {course.get('course_code', '')}: {course.get('course_name', '')}"
                if course.get('instructor'):
                    text += f" (استاد: {course['instructor']})"
                text += "\n"
            text += "\n"
        
        return text
    
    def _create_recommendation_prompt(
        self,
        entry_year: int,
        current_semester: int,
        raw_grades: str,
        last_semester_gpa: float,
        overall_gpa: float,
        curriculum: str,
        offerings: str,
        credit_limit: str
    ) -> str:
        """Create comprehensive prompt for LLM recommendation"""
        
        prompt = f"""تو یک مشاور تحصیلی هستی برای دانشگاه آزاد شهرکرد، رشته مهندسی کامپیوتر.

اطلاعات دانشجو:
- ورودی: {entry_year}
- ترم فعلی: {current_semester}
- معدل ترم قبل: {last_semester_gpa}
- معدل کل: {overall_gpa}
- محدودیت واحد: {credit_limit}

نمرات ارائه شده توسط دانشجو:
{raw_grades}

چارت درسی:
{curriculum}

دروس ارائه شده این ترم:
{offerings}

📋 **راهنمای کامل انتخاب دروس:**

🎯 **گروه‌بندی دروس ارائه شده:**
1. **🎓 دروس مخصوص سال ورودی:**
   - برای ترم‌های 1-2 مخصوص ورودی خاص
   - دانشجو ترم {current_semester} است - اگر ترم 3+ است این دروس معمولاً مناسب نیست
   - فقط اگر دانشجو این دروس را افتاده باشد

2. **📚 دروس آزاد (ترم 3 به بعد):**
   - بر اساس ترم هدف طبقه‌بندی شده
   - باید پیش‌نیازها بررسی شود
   - دانشجو ترم {current_semester} است - دروس ترم {current_semester} و بالاتر مناسب

3. **🌐 دروس عمومی:**
   - همه ارائه می‌شوند (بدون محدودیت زمانی)
   - قوانین خاص دارند - حتماً رعایت کن
   - اولویت با دروس تخصصی

4. **🏗️ پروژه‌ها و کارآموزی:**
   - برای ترم‌های انتهایی
   - نیاز به پیش‌نیازهای خاص

⚠️ **نکات بحرانی برای انتخاب:**

🔍 **بررسی‌های الزامی:**
1. **آیا درس در دسترس است؟** (بررسی لیست ارائه شده)
2. **پیش‌نیازهای گذرانده شده؟** (بررسی نمرات و چارت)
3. **مناسب برای ترم فعلی؟** (ترم {current_semester})
4. **رعایت قوانین عمومی؟** (معارف، زبان، تربیت بدنی)

🎯 **اولویت‌بندی هوشمند:**
1. **🚨 دروس افتاده** (اولویت 100%) - اگر نمره‌ای < 10 یا درس گم شده
2. **⭐ دروس ترم فعلی** (اولویت 90%) - مطابق چارت درسی
3. **🔗 پیش‌نیازها** (اولویت 85%) - برای باز کردن دروس آینده  
4. **📖 عمومی باقی‌مانده** (اولویت 75%) - تکمیل دروس عمومی
5. **🆕 دروس آینده** (اولویت 60%) - اگر جا باقی مانده

📖 **قوانین ویژه دروس عمومی:**
- **معارف اسلامی**: فقط یک درس در هر ترم
- **زبان‌ها**: ترتیبی (پیش → انگلیسی 1 → انگلیسی 2 → تخصصی)
- **تربیت بدنی**: حداکثر 2 واحد کل دوره
- **کارگاه**: آشنایی با صنعت → کارآفرینی

🔄 **مراحل تصمیم‌گیری:**

**1. 🧾 تحلیل وضعیت دانشجو:**
   - تطبیق نمرات با چارت درسی (استاندارد کردن نام‌ها)
   - شناسایی دروس افتاده (نمره < 10) یا گم شده
   - بررسی ترم فعلی و پیشرفت تحصیلی

**2. 🎯 انتخاب دروس بر اساس اولویت:**
   - **اولویت 1**: دروس افتاده که در این ترم ارائه می‌شوند
   - **اولویت 2**: دروس الزامی ترم {current_semester} (مطابق چارت)
   - **اولویت 3**: پیش‌نیازهای مهم برای ترم‌های آینده
   - **اولویت 4**: دروس عمومی (بر اساس قوانین خاص)
   - **اولویت 5**: دروس اختیاری یا پیشرفته (اگر جا باقی مانده)

**3. ✅ اعتبارسنجی نهایی:**
   - کل واحدها ≤ {credit_limit}
   - همه دروس در لیست ارائه شده موجود باشند
   - پیش‌نیازها رعایت شده باشند
   - قوانین دروس عمومی نقض نشده باشند

**مهم**: فقط دروسی پیشنهاد بده که در لیست "دروس ارائه شده این ترم" موجودند! اگر درسی در آن لیست نیست، پیشنهاد نکن.

پاسخت رو به صورت JSON ساختار یافته بده:
{{
  "mapped_grades": [
    {{"course_code": "کد درس", "course_name": "نام استاندارد", "grade": نمره, "status": "قبول/مردود"}}
  ],
  "recommended_courses": [
    {{
      "course_code": "کد درس", 
      "course_name": "نام درس", 
      "credits": {{"theoretical": X, "practical": Y}},
      "type": "تخصصی/عمومی/اختیاری",
      "priority": "بالا/متوسط/پایین",
      "reason": "دلیل پیشنهاد"
    }}
  ],
  "total_credits": "مجموع واحدهای پیشنهادی",
  "analysis": "تحلیل کلی وضعیت دانشجو و توضیح استراتژی انتخاب واحد"
}}"""

        return prompt
    
    def _create_fallback_response(self) -> Dict[str, Any]:
        """Create fallback response when LLM fails"""
        
        return {
            "success": False,
            "message": "متأسفانه سرویس پیشنهاد درس موقتاً در دسترس نیست. لطفاً مجدداً تلاش کنید.",
            "courses": [],
            "analysis": "امکان تحلیل وضعیت تحصیلی در حال حاضر فراهم نیست."
        }