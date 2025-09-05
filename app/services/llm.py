"""
LLM integration service for CourseWise.

This module provides the LLMService class for OpenAI integration,
specifically for grade text parsing and course recommendation functionality.
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from openai import AsyncOpenAI
from loguru import logger

from app.config import settings


@dataclass
class ParsedGrade:
    """Represents a parsed grade from user input."""
    course_code: str
    course_name: Optional[str]
    grade: Optional[float]
    status: str  # 'passed', 'failed', 'withdrawn'
    semester_taken: Optional[int] = None
    confidence: float = 1.0


@dataclass
class GradeParseResult:
    """Result of grade text parsing operation."""
    success: bool
    parsed_grades: List[ParsedGrade]
    warnings: List[str]
    confidence: float
    raw_text: str
    error_message: Optional[str] = None


class LLMService:
    """
    Service for LLM operations using OpenAI API.
    
    Handles grade text parsing, course validation, and provides
    structured responses for bot interaction.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize LLM service.
        
        Args:
            api_key: OpenAI API key (uses settings if None)
            model: OpenAI model to use for operations
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(f"Initialized LLM service with model: {model}")
    
    async def parse_grades_text(self, text: str, valid_courses: Optional[List[dict]] = None) -> GradeParseResult:
        """
        Parse grade text input into structured format.
        
        Args:
            text: Raw grade text from user
            valid_courses: List of valid course codes for validation
            
        Returns:
            GradeParseResult with parsed grades and metadata
        """
        try:
            logger.info(f"Parsing grade text: {text[:100]}...")
            
            # Prepare the prompt for grade parsing
            prompt = self._prepare_grade_parsing_prompt(text, valid_courses or [])
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at parsing Iranian university grade information. Parse the user's grade text into structured JSON format."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent parsing
                max_tokens=1500
            )
            
            # Parse the LLM response
            result = self._parse_llm_response(response.choices[0].message.content, text)
            
            logger.info(f"Successfully parsed {len(result.parsed_grades)} grades with confidence {result.confidence}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing grades: {e}")
            return GradeParseResult(
                success=False,
                parsed_grades=[],
                warnings=[],
                confidence=0.0,
                raw_text=text,
                error_message=f"Failed to parse grades: {str(e)}"
            )
    
    def _prepare_grade_parsing_prompt(self, text: str, valid_courses: List[str]) -> str:
        """
        Prepare the prompt for grade parsing.
        
        Args:
            text: User's grade text
            valid_courses: List of valid course codes
            
        Returns:
            Formatted prompt for LLM
        """
        prompt = f"""
Parse the following grade text from an Iranian university student. Extract course codes, names, grades, and status.

**Input Text:** "{text}"

**Valid Courses (Code → Name):**
{self._format_course_list(valid_courses) if valid_courses else 'No course list provided - infer from text'}

**Instructions:**
1. Extract each course mentioned in the text
2. Match Persian course names to course codes using the Valid Courses list above
3. If exact match not found, find the closest match or leave course_code as null
4. Extract numerical grades (0-20 scale) or status (passed/failed)
5. Extract semester when course was taken (if mentioned)
6. Determine status: "passed" (grade ≥ 10), "failed" (grade < 10 or explicitly failed), "withdrawn"
7. Provide confidence score (0-1) for each parsing

**Matching Examples:**
- "ریاضی عمومی 1" → MATH101
- "زبان عمومی" → ENG101
- "تربیت بدنی" → PE101

**Output Format (JSON):**
```json
{{
    "success": true,
    "parsed_grades": [
        {{
            "course_code": "CS101",
            "course_name": "Programming Fundamentals",
            "grade": 18.5,
            "status": "passed",
            "semester_taken": 1,
            "confidence": 0.95
        }},
        {{
            "course_code": "MATH201", 
            "course_name": "Calculus",
            "grade": null,
            "status": "failed",
            "semester_taken": 2,
            "confidence": 0.90
        }}
    ],
    "warnings": ["Unknown course code: PHYS101"],
    "confidence": 0.92
}}
```

**Notes:**
- Iranian grading scale: 0-20 (passing grade ≥ 10)
- Common formats: "Math1: 17", "CS101: 18", "Physics: failed", "Data Structure = 19.5"
- Handle Persian/Farsi course names if present
- Extract semester info if mentioned: "ترم 1", "ترم اول", "semester 2", etc.
- If semester not mentioned, leave semester_taken as null
- Flag unknown course codes as warnings
"""
        return prompt
    
    def _format_course_list(self, course_list: List[dict]) -> str:
        """Format course list for LLM prompt."""
        if not course_list:
            return "No courses available"
            
        formatted = []
        for course in course_list[:30]:  # Limit to avoid token overflow
            code = course.get("code", "")
            name = course.get("name", "")
            if code and name:
                formatted.append(f"- {code}: {name}")
        
        return "\n".join(formatted) if formatted else "No valid courses found"
    
    def _parse_llm_response(self, response_text: str, original_text: str) -> GradeParseResult:
        """
        Parse LLM response into GradeParseResult.
        
        Args:
            response_text: Raw response from LLM
            original_text: Original user input
            
        Returns:
            Parsed GradeParseResult
        """
        try:
            # Extract JSON from response (handle code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find JSON in the response
                json_text = response_text
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Convert to ParsedGrade objects
            parsed_grades = []
            for grade_data in data.get('parsed_grades', []):
                parsed_grade = ParsedGrade(
                    course_code=grade_data.get('course_code', ''),
                    course_name=grade_data.get('course_name'),
                    grade=grade_data.get('grade'),
                    status=grade_data.get('status', 'unknown'),
                    semester_taken=grade_data.get('semester_taken'),
                    confidence=grade_data.get('confidence', 0.5)
                )
                parsed_grades.append(parsed_grade)
            
            return GradeParseResult(
                success=data.get('success', False),
                parsed_grades=parsed_grades,
                warnings=data.get('warnings', []),
                confidence=data.get('confidence', 0.5),
                raw_text=original_text
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"LLM response was: {response_text}")
            
            # Fallback: try simple regex parsing
            return self._fallback_grade_parsing(original_text)
            
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}")
            return GradeParseResult(
                success=False,
                parsed_grades=[],
                warnings=[f"Failed to process LLM response: {str(e)}"],
                confidence=0.0,
                raw_text=original_text,
                error_message=str(e)
            )
    
    def _fallback_grade_parsing(self, text: str) -> GradeParseResult:
        """
        Fallback parsing using regex when LLM parsing fails.
        
        Args:
            text: Original user text
            
        Returns:
            GradeParseResult with basic parsing
        """
        logger.warning("Using fallback regex parsing for grades")
        
        parsed_grades = []
        warnings = ["Using basic parsing - LLM parsing failed"]
        
        # Common patterns for grade text
        patterns = [
            r'([A-Z]+\d+)[:=]\s*(\d+(?:\.\d+)?)',  # CS101: 18
            r'([A-Z]+\d+)[:=]\s*(failed?|pass)',    # CS101: failed
            r'(\w+)[:=]\s*(\d+(?:\.\d+)?)',         # Math: 17
            r'(\w+)[:=]\s*(failed?|pass)',          # Math: failed
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                course_code = match.group(1).upper()
                grade_str = match.group(2).lower()
                
                if grade_str in ['failed', 'fail']:
                    grade = None
                    status = 'failed'
                elif grade_str in ['passed', 'pass']:
                    grade = None
                    status = 'passed'
                else:
                    try:
                        grade = float(grade_str)
                        status = 'passed' if grade >= 10 else 'failed'
                    except ValueError:
                        continue
                
                parsed_grade = ParsedGrade(
                    course_code=course_code,
                    course_name=None,
                    grade=grade,
                    status=status,
                    confidence=0.7  # Lower confidence for regex parsing
                )
                parsed_grades.append(parsed_grade)
        
        return GradeParseResult(
            success=len(parsed_grades) > 0,
            parsed_grades=parsed_grades,
            warnings=warnings,
            confidence=0.7,
            raw_text=text
        )
    
    async def validate_course_codes(self, course_codes: List[str], 
                                   known_courses: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validate course codes against known course list.
        
        Args:
            course_codes: List of course codes to validate
            known_courses: List of known/valid course codes
            
        Returns:
            Tuple of (valid_codes, invalid_codes)
        """
        valid_codes = []
        invalid_codes = []
        
        for code in course_codes:
            code_upper = code.upper()
            if code_upper in [c.upper() for c in known_courses]:
                valid_codes.append(code_upper)
            else:
                invalid_codes.append(code)
        
        if invalid_codes:
            logger.warning(f"Invalid course codes detected: {invalid_codes}")
        
        return valid_codes, invalid_codes
    
    def format_grades_for_confirmation(self, parse_result: GradeParseResult) -> str:
        """
        Format parsed grades for user confirmation.
        
        Args:
            parse_result: Result from grade parsing
            
        Returns:
            Formatted string for user display
        """
        if not parse_result.success or not parse_result.parsed_grades:
            return "L Could not parse any grades from your input."
        
        lines = ["=� **Detected Grades:**\n"]
        
        for i, grade in enumerate(parse_result.parsed_grades, 1):
            status_emoji = "" if grade.status == "passed" else "L" if grade.status == "failed" else "�"
            grade_text = f"{grade.grade:.1f}" if grade.grade is not None else grade.status
            
            line = f"{i}. {status_emoji} **{grade.course_code}**"
            if grade.course_name:
                line += f" ({grade.course_name})"
            line += f": {grade_text}"
            if grade.semester_taken:
                line += f" - ترم {grade.semester_taken}"
            
            lines.append(line)
        
        if parse_result.warnings:
            lines.append(f"\n� **Warnings:**")
            for warning in parse_result.warnings:
                lines.append(f"⚠️ {warning}")
        
        lines.append(f"\n📊 **Confidence:** {parse_result.confidence:.0%}")
        lines.append(f"\n📝 **Original text:** {parse_result.raw_text}")
        
        return "\n".join(lines)
    
    async def generate_course_recommendations(
        self,
        context: str,
        student_preferences: Optional[Dict[str, Any]] = None,
        available_courses: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate course recommendations using LLM.
        
        Args:
            context: Formatted context about student and academic rules
            student_preferences: User preferences for course selection
            available_courses: List of available courses for the semester
            
        Returns:
            Dict with LLM recommendations and analysis
        """
        try:
            logger.info("Generating course recommendations using LLM")
            
            # Prepare the recommendation prompt
            prompt = self._prepare_recommendation_prompt(context, student_preferences, available_courses)
            
            # Log prompt in debug mode only
            logger.debug(f"Sending prompt to LLM (length: {len(prompt)} chars)")
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """شما یک مشاور تحصیلی خبره برای دانشجویان مهندسی کامپیوتر ایرانی هستید. 
                        وظیفه شما ارائه پیشنهادات هوشمندانه و دقیق برای انتخاب واحد است.
                        
                        در پاسخ خود:
                        1. قوانین تحصیلی را دقیقاً رعایت کنید
                        2. اولویت را به دروس مردودی و پیش‌نیازها دهید  
                        3. برنامه زمانی متعادل و بدون تداخل ارائه دهید
                        4. توضیح روشن و کاربردی برای هر پیشنهاد بدهید
                        5. پاسخ را به فارسی و در فرمت خواسته شده ارائه دهید"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Moderate creativity for recommendations
                max_tokens=2000
            )
            
            # Parse the LLM response
            llm_response = response.choices[0].message.content
            
            # Log response in debug mode only
            logger.debug(f"Received LLM response (length: {len(llm_response)} chars)")
            
            # Extract structured information from response
            recommendations = self._parse_recommendation_response(llm_response)
            
            logger.info(f"Generated {len(recommendations.get('courses', []))} course recommendations")
            
            return {
                "success": True,
                "recommendations": recommendations,
                "raw_response": llm_response,
                "analysis": self._analyze_llm_recommendations(recommendations, available_courses or [])
            }
            
        except Exception as e:
            logger.error(f"Error generating LLM recommendations: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": {},
                "raw_response": "",
                "analysis": {}
            }
    
    def _prepare_recommendation_prompt(
        self,
        context: str, 
        preferences: Optional[Dict[str, Any]] = None,
        available_courses: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Prepare prompt for course recommendation.
        
        Args:
            context: Student and academic context
            preferences: User preferences
            available_courses: Available courses list
            
        Returns:
            Formatted prompt for LLM
        """
        prompt_sections = [context]
        
        # Add user preferences if provided
        if preferences:
            prompt_sections.append(f"""
# ترجیحات دانشجو

**تعداد واحد مطلوب:** {preferences.get('desired_credits', 'نامشخص')}
**علاقه‌مندی‌ها:** {preferences.get('interests', 'نامشخص')}
**زمان‌بندی ترجیحی:** {preferences.get('preferred_schedule', 'نامشخص')}
**سایر درخواست‌ها:** {preferences.get('additional_notes', 'ندارد')}
            """)
        
        # Add detailed course list if available
        if available_courses:
            valid_courses = [c for c in available_courses if c.get("validation", {}).get("is_valid")]
            if valid_courses:
                course_details = []
                for course in valid_courses[:20]:  # Limit to avoid token overflow
                    credits = course.get("credits", {})
                    if isinstance(credits, dict):
                        total_credits = credits.get("theoretical", 0) + credits.get("practical", 0)
                    else:
                        total_credits = credits
                    
                    time_info = ", ".join(course.get("time_slots", ["نامشخص"]))
                    priority = course.get("validation", {}).get("priority_score", 0)
                    
                    course_details.append(
                        f"- **{course['course_name']}** ({course['course_code']}): "
                        f"{total_credits} واحد، اولویت: {priority}, زمان: {time_info}"
                    )
                
                prompt_sections.append(f"""
# جزئیات دروس موجود (۲۰ درس اول)

{chr(10).join(course_details)}
                """)
        
        # Add final instructions
        prompt_sections.append("""
# دستورالعمل‌های اساسی انتخاب واحد

## محدودیت‌های تعداد واحد (بر اساس معدل):
- **معدل ≥ 17.0:** حداکثر 24 واحد
- **14.0 ≤ معدل < 17.0:** حداکثر 20 واحد  
- **12.0 ≤ معدل < 14.0:** حداکثر 16 واحد (مشروط)
- **معدل < 12.0:** حداکثر 12 واحد (در خطر اخراج)
- **ترم قبل مشروط:** حداکثر 14 واحد (صرف نظر از معدل کل)
- **ترم اول:** حداکثر 18 واحد (بدون محدودیت معدل)

## قوانین دروس عمومی:
- **دروس معارف اسلامی:** در هر ترم فقط یک درس معارف قابل انتخاب
- **دروس زبان:** باید به ترتیب گذرانده شوند (زبان پیش → انگلیسی ۱ → انگلیسی ۲ → زبان تخصصی)
- **تربیت بدنی:** حداکثر 2 واحد در کل دوره (تربیت بدنی → ورزش ۱)
- **کارگاه عمومی:** آشنایی با صنعت → کارآفرینی

## اولویت‌بندی انتخاب دروس:
1. **دروس مردودی** (اولویت 100) - بالاترین اولویت
2. **دروس پیش‌نیاز** (اولویت 90) - برای باز کردن دروس آینده
3. **دروس ترم جاری** (اولویت 80) - مطابق چارت درسی
4. **دروس عمومی باقی‌مانده** (اولویت 70) - تکمیل دروس عمومی

## قوانین پیش‌نیاز و هم‌نیاز:
- پیش‌نیازها باید با نمره ≥ 10 گذرانده شوند
- **دروس هم‌نیاز اجباری:**
  - ریاضی ۱ + حل تمرین ریاضی ۱
  - فیزیک ۱ + حل تمرین فیزیک ۱  
  - ریاضی ۲ + حل تمرین ریاضی ۲
  - فیزیک ۲ + حل تمرین فیزیک ۲

## چارت درسی (ورودی 1403 به بعد):
- **ترم 1:** ریاضی۱، فیزیک۱، مبانی کامپیوتر، اندیشه اسلامی۱، آیین زندگی
- **ترم 2:** ریاضی۲، فیزیک۲، برنامه‌سازی پیشرفته، ریاضیات گسسته، مدارهای منطقی، کارگاه کامپیوتر، انگلیسی۱، تاریخ صدر اسلام، آشنایی با صنعت
- **ترم 3:** ساختمان داده‌ها، معماری کامپیوتر، معادلات دیفرانسیل، آزمایشگاه مدارهای منطقی، انگلیسی۲، فارسی، کارآفرینی
- **ترم 4:** طراحی الگوریتم‌ها، نظریه زبان‌ها، آزمایشگاه معماری، مدارهای الکتریکی، جبر خطی، آمار و احتمال، زبان تخصصی، تاریخ فرهنگ اسلام

# دستورالعمل نهایی

لطفاً بر اساس اطلاعات فوق و قوانین تحصیلی، پیشنهاد دروس مناسب برای این ترم ارائه دهید.

**فرمت خروجی مورد انتظار:**

📚 **پیشنهاد دروس برای ترم:**

🗓️ **برنامه هفتگی:**

**شنبه:**
- [نام درس] ([کد درس]) - [ساعت کلاس] - [تعداد واحد] واحد - استاد: [نام استاد]

**یکشنبه:**
- [نام درس] ([کد درس]) - [ساعت کلاس] - [تعداد واحد] واحد - استاد: [نام استاد]

**دوشنبه:**
- [نام درس] ([کد درس]) - [ساعت کلاس] - [تعداد واحد] واحد - استاد: [نام استاد]

**سه‌شنبه:**
- [نام درس] ([کد درس]) - [ساعت کلاس] - [تعداد واحد] واحد - استاد: [نام استاد]

**چهارشنبه:**
- [نام درس] ([کد درس]) - [ساعت کلاس] - [تعداد واحد] واحد - استاد: [نام استاد]

**پنج‌شنبه:**
- [دروس پنج‌شنبه در صورت وجود]

**جمعه:**
- [دروس جمعه در صورت وجود]

📊 **خلاصه پیشنهاد:**
- **مجموع واحدها:** [تعداد کل] واحد
- **دروس مردودی پوشش داده شده:** [تعداد]
- **دروس پیش‌نیاز:** [تعداد]  
- **دروس جدید:** [تعداد]
- **دروس عمومی:** [تعداد]
- **محدودیت واحد رعایت شده:** [بله/خیر]

💡 **توجیه انتخاب:**
[توضیح منطق انتخاب دروس بر اساس اولویت‌ها، محدودیت‌ها و چارت درسی]

⚠️ **نکات مهم:**
[هشدارها درباره تداخل زمانی، پیش‌نیازها، محدودیت‌های خاص]

**اصول رعایت شده:** 
- محدودیت واحد بر اساس معدل و وضعیت تحصیلی
- اولویت دروس مردودی و پیش‌نیاز
- رعایت ترتیب دروس عمومی (زبان، معارف، کارگاه)
- تعادل بین دروس سخت و آسان
- اجتناب از تداخل زمانی
- **کلاس‌های حل تمرین همراه با درس اصلی** (ریاضی، فیزیک)
        """)
        
        return "\n".join(prompt_sections)
    
    def _parse_recommendation_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM recommendation response into structured format.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Structured recommendation data
        """
        try:
            recommendations = {
                "weekly_schedule": {},
                "summary": {},
                "explanation": "",
                "warnings": [],
                "courses": []
            }
            
            # Try to parse as JSON first (LLM might return structured JSON)
            if response.strip().startswith('```json') and '```' in response:
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    try:
                        import json
                        json_data = json.loads(json_match.group(1))
                        if "recommended_courses" in json_data:
                            for course in json_data["recommended_courses"]:
                                course_info = {
                                    'course_code': course.get('course_code', ''),
                                    'course_name': course.get('course_name', ''),
                                    'credits': course.get('credits', {}),
                                    'time_slots': ['نامشخص'],
                                    'instructor': course.get('instructor', 'نامشخص'),
                                    'type': course.get('type', 'تخصصی'),
                                    'priority': course.get('priority', 'متوسط'),
                                    'reason': course.get('reason', '')
                                }
                                recommendations["courses"].append(course_info)
                            
                            # Create simple weekly schedule from courses
                            weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه"]
                            for i, course in enumerate(recommendations["courses"]):
                                if i < len(weekdays):
                                    day = weekdays[i]
                                    recommendations["weekly_schedule"][day] = [course]
                            
                            # Extract analysis from JSON
                            recommendations["explanation"] = json_data.get("analysis", "")
                            recommendations["summary"] = {
                                "total_credits": json_data.get("total_credits", "نامشخص"),
                                "course_count": len(recommendations["courses"]),
                                "passed_grades": len(json_data.get("mapped_grades", []))
                            }
                            
                            logger.debug(f"Parsed JSON response with {len(recommendations['courses'])} courses")
                            return recommendations
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON response: {e}, falling back to text parsing")
            
            # Fallback to original text parsing for weekly schedule format
            weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
            
            for day in weekdays:
                day_pattern = rf"\*\*{day}:\*\*(.*?)(?=\*\*(?:{'|'.join(weekdays)}|خلاصه|توجیه|نکات)|\Z)"
                day_match = re.search(day_pattern, response, re.DOTALL)
                
                if day_match:
                    day_content = day_match.group(1).strip()
                    courses_on_day = []
                    
                    # Extract courses for this day
                    course_lines = [line.strip() for line in day_content.split('\n') if line.strip() and line.strip().startswith('-')]
                    
                    for line in course_lines:
                        course_info = self._extract_course_from_line(line)
                        if course_info:
                            courses_on_day.append(course_info)
                            
                            # Add to global course list if not already there
                            if not any(c['course_code'] == course_info['course_code'] for c in recommendations["courses"]):
                                recommendations["courses"].append(course_info)
                    
                    recommendations["weekly_schedule"][day] = courses_on_day
            
            # Fallback: if no courses found, try to extract course codes directly
            if not recommendations["courses"]:
                logger.warning("No courses found in weekly schedule, trying fallback extraction")
                recommendations["courses"] = self._fallback_course_extraction(response)
            
            # Extract summary
            summary_pattern = r"\*\*خلاصه پیشنهاد:\*\*(.*?)(?=💡|\*\*توجیه|\Z)"
            summary_match = re.search(summary_pattern, response, re.DOTALL)
            if summary_match:
                summary_text = summary_match.group(1).strip()
                recommendations["summary"] = self._parse_summary_section(summary_text)
            
            # Extract explanation
            explanation_pattern = r"💡\s*\*\*توجیه انتخاب:\*\*(.*?)(?=⚠️|\*\*نکات|\Z)"
            explanation_match = re.search(explanation_pattern, response, re.DOTALL)
            if explanation_match:
                recommendations["explanation"] = explanation_match.group(1).strip()
            
            # Extract warnings/notes
            warnings_pattern = r"⚠️\s*\*\*نکات مهم:\*\*(.*?)(?=\*\*مهم|\Z)"
            warnings_match = re.search(warnings_pattern, response, re.DOTALL)
            if warnings_match:
                warnings_text = warnings_match.group(1).strip()
                recommendations["warnings"] = [line.strip() for line in warnings_text.split('\n') if line.strip()]
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error parsing LLM recommendation response: {e}")
            return {"error": str(e), "courses": [], "weekly_schedule": {}}
    
    def _extract_course_from_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Extract course information from a single line.
        
        Args:
            line: Line containing course info
            
        Returns:
            Course information dict or None
        """
        try:
            # Pattern: - [نام درس] ([کد درس]) - [ساعت] - [واحد] واحد - استاد: [نام]
            pattern = r'-\s*(.+?)\s*\(([A-Z0-9]+)\)\s*-\s*(.+?)\s*-\s*(\d+)\s*واحد(?:\s*-\s*استاد:\s*(.+?))?'
            
            match = re.search(pattern, line)
            if match:
                return {
                    "course_name": match.group(1).strip(),
                    "course_code": match.group(2).strip(),
                    "time_slot": match.group(3).strip(),
                    "credits": int(match.group(4)),
                    "instructor": match.group(5).strip() if match.group(5) else "نامشخص"
                }
            
            # Simpler pattern if the above doesn't match
            simple_pattern = r'-\s*(.+?)\s*\(([A-Z0-9]+)\)'
            simple_match = re.search(simple_pattern, line)
            if simple_match:
                return {
                    "course_name": simple_match.group(1).strip(),
                    "course_code": simple_match.group(2).strip(),
                    "time_slot": "نامشخص",
                    "credits": 0,
                    "instructor": "نامشخص"
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not parse course line: {line} - {e}")
            return None
    
    def _parse_summary_section(self, summary_text: str) -> Dict[str, Any]:
        """
        Parse summary section from LLM response.
        
        Args:
            summary_text: Summary section text
            
        Returns:
            Parsed summary data
        """
        summary = {}
        
        # Extract total credits
        credits_match = re.search(r'مجموع واحدها.*?(\d+)', summary_text)
        if credits_match:
            summary["total_credits"] = int(credits_match.group(1))
        
        # Extract failed courses count
        failed_match = re.search(r'دروس مردودی.*?(\d+)', summary_text)
        if failed_match:
            summary["failed_courses_covered"] = int(failed_match.group(1))
        
        # Extract prerequisite courses count
        prereq_match = re.search(r'دروس پیش‌نیاز.*?(\d+)', summary_text)
        if prereq_match:
            summary["prerequisite_courses"] = int(prereq_match.group(1))
        
        # Extract new courses count
        new_match = re.search(r'دروس جدید.*?(\d+)', summary_text)
        if new_match:
            summary["new_courses"] = int(new_match.group(1))
        
        # Extract difficulty balance
        difficulty_match = re.search(r'تعادل سختی.*?(آسان|متوسط|سخت|متعادل)', summary_text)
        if difficulty_match:
            summary["difficulty_balance"] = difficulty_match.group(1)
        
        return summary
    
    def _analyze_llm_recommendations(self, recommendations: Dict[str, Any], available_courses: List[Dict]) -> Dict[str, Any]:
        """
        Analyze quality of LLM recommendations.
        
        Args:
            recommendations: Parsed LLM recommendations
            available_courses: List of available courses
            
        Returns:
            Analysis results
        """
        analysis = {
            "validity_score": 0,
            "coverage_score": 0,
            "balance_score": 0,
            "issues": [],
            "strengths": []
        }
        
        recommended_courses = recommendations.get("courses", [])
        
        if not recommended_courses:
            analysis["issues"].append("No courses recommended")
            return analysis
        
        # Check if recommended courses are actually available
        available_codes = {course["course_code"] for course in available_courses}
        recommended_codes = {course["course_code"] for course in recommended_courses}
        
        valid_recommendations = recommended_codes.intersection(available_codes)
        invalid_recommendations = recommended_codes - available_codes
        
        # Calculate validity score
        if recommended_codes:
            analysis["validity_score"] = len(valid_recommendations) / len(recommended_codes) * 100
        
        if invalid_recommendations:
            analysis["issues"].append(f"Invalid course codes: {', '.join(invalid_recommendations)}")
        else:
            analysis["strengths"].append("All recommended courses are available")
        
        # Check credit distribution
        total_credits_raw = recommendations.get("summary", {}).get("total_credits", 0)
        try:
            # Convert to int if it's a string
            if isinstance(total_credits_raw, str):
                total_credits = int(total_credits_raw.split()[0]) if total_credits_raw.split() else 0
            else:
                total_credits = int(total_credits_raw) if total_credits_raw else 0
            
            if 12 <= total_credits <= 24:
                analysis["strengths"].append(f"Appropriate credit count: {total_credits}")
            else:
                analysis["issues"].append(f"Credit count may be inappropriate: {total_credits}")
        except (ValueError, IndexError, TypeError):
            analysis["issues"].append("Could not determine credit count")
        
        # Check daily distribution
        weekly_schedule = recommendations.get("weekly_schedule", {})
        daily_counts = [len(courses) for courses in weekly_schedule.values()]
        
        if daily_counts and max(daily_counts) <= 3:
            analysis["strengths"].append("Good daily distribution")
            analysis["balance_score"] = 80
        else:
            analysis["issues"].append("Some days may be overloaded")
            analysis["balance_score"] = 50
        
        # Overall coverage score
        if len(valid_recommendations) >= 3:
            analysis["coverage_score"] = 80
            analysis["strengths"].append("Good course coverage")
        else:
            analysis["coverage_score"] = 40
            analysis["issues"].append("Limited course coverage")
        
        return analysis

    def _fallback_course_extraction(self, response: str) -> List[Dict[str, Any]]:
        """Fallback method to extract course codes from any format"""
        try:
            import re
            courses = []
            
            # Look for actual course codes from offerings first, then fallback to generic codes
            code_patterns = [
                r'([0-9]{10})',  # 10-digit codes like 7000031535, 4628164737
                r'\b([0-9]{7,12})\b',  # 7-12 digit codes from offerings  
                r'معادلات_دیفرانسیل|ساختار_داده|آمار_احتمالات|معماری_کامپیوتر|مهارتهای_نرم|کارآفرینی',  # Course keys from offerings
                r'\(([A-Z0-9_]+)\)',  # (CS101) or (code in parentheses)
                r'([A-Z]+[0-9]+)',  # Generic codes like CS101 (lowest priority)
            ]
            
            for pattern in code_patterns:
                matches = re.findall(pattern, response)
                for match in matches:
                    # Skip very long numbers that aren't course codes
                    if len(match) > 15 or len(match) < 2:
                        continue
                    
                    # Add if not already in list
                    if not any(c.get('course_code') == match for c in courses):
                        # Try to find course info from offerings
                        course_info = self._find_course_in_offerings(match)
                        
                        courses.append({
                            'course_code': match,
                            'course_name': course_info.get('course_name', f'درس {match}'),
                            'credits': course_info.get('credits', {'theoretical': 3, 'practical': 0}),
                            'time_slots': course_info.get('time_slots', ['نامشخص']),
                            'instructor': course_info.get('instructor', 'نامشخص'),
                            'exam_date': course_info.get('exam_date', '')
                        })
            
            logger.debug(f"Fallback extraction found {len(courses)} courses")
            return courses[:10]  # Limit to reasonable number
            
        except Exception as e:
            logger.error(f"Error in fallback course extraction: {e}")
            return []
    
    def _find_course_in_offerings(self, course_code: str) -> Dict[str, Any]:
        """Find course information from offerings data"""
        try:
            from pathlib import Path
            import json
            
            # Load offerings file
            offerings_path = Path("data/offerings/mehr_1404_new.json")
            
            if offerings_path.exists():
                with open(offerings_path, 'r', encoding='utf-8') as f:
                    offerings = json.load(f)
                
                # Search in all sections of offerings
                def search_in_courses(courses_list):
                    for course in courses_list:
                        if course.get('course_code') == course_code:
                            return course
                    return None
                
                # Search in entry year groups
                for entry_year, entry_data in offerings.get("entry_year_groups", {}).items():
                    for semester_num, semester_data in entry_data.get("semesters", {}).items():
                        found = search_in_courses(semester_data.get("courses", []))
                        if found:
                            return found
                
                # Search in open courses
                found = search_in_courses(offerings.get("open_courses", {}).get("courses", []))
                if found:
                    return found
                
                # Search in general courses
                found = search_in_courses(offerings.get("general_courses", {}).get("courses", []))
                if found:
                    return found
            
            return {}  # Not found
            
        except Exception as e:
            logger.error(f"Error searching course in offerings: {e}")
            return {}

    async def health_check(self) -> bool:
        """
        Check if LLM service is healthy and can connect to OpenAI.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False