"""
Student Context Analyzer Service

تجزیه و تحلیل وضعیت تحصیلی دانشجو برای پیشنهاد بهینه دروس
شامل: تحلیل نمرات، بررسی پیش‌نیازها، محاسبه GPA، تعیین وضعیت تحصیلی
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
from loguru import logger

from app.models.student import Student, StudentGrade
from app.models.course import Course
from app.core.database import get_db
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@dataclass
class StudentAcademicStatus:
    """وضعیت تحصیلی دانشجو"""
    student_id: int
    current_gpa: float
    total_credits_passed: int
    academic_standing: str  # "normal", "probation", "good_standing"
    entry_year: int
    current_semester: int
    curriculum_version: str  # "pre_1403" or "post_1403"
    group_assignment: Optional[str]  # "A", "B", or None
    failed_courses: List[Dict[str, Any]]
    completed_courses: List[Dict[str, Any]]
    prerequisite_status: Dict[str, bool]
    specialization_status: Dict[str, Any]
    graduation_progress: Dict[str, Any]


class StudentAnalyzer:
    """سرویس تجزیه و تحلیل وضعیت تحصیلی دانشجو"""
    
    def __init__(self):
        self.curriculum_chart = self._load_curriculum_chart()
        self.academic_rules = self._load_academic_rules()
    
    def _load_curriculum_chart(self) -> Dict[str, Any]:
        """بارگذاری چارت‌های درسی از فایل‌های JSON"""
        try:
            data_path = Path(__file__).parent.parent.parent / "data"
            
            # بارگذاری چارت‌های درسی
            with open(data_path / "curriculum_1403_onwards.json", 'r', encoding='utf-8') as f:
                post_1403_chart = json.load(f)
            
            with open(data_path / "curriculum_before_1403.json", 'r', encoding='utf-8') as f:
                pre_1403_chart = json.load(f)
            
            # ترکیب داده‌ها در ساختار مورد انتظار
            return {
                "curriculum_versions": {
                    "post_1403": post_1403_chart,
                    "pre_1403": pre_1403_chart
                },
                "academic_rules": {
                    "credit_limits": {
                        "gpa_17_plus": {"max_credits": 24, "min_credits": 12},
                        "gpa_15_to_17": {"max_credits": 20, "min_credits": 12},
                        "gpa_12_to_15": {"max_credits": 18, "min_credits": 12},
                        "gpa_below_12": {"max_credits": 16, "min_credits": 14}
                    }
                },
                "specialization_groups": post_1403_chart.get("specialization_tracks", {})
            }
        except Exception as e:
            logger.error(f"Error loading curriculum charts: {e}")
            return {}
    
    def _load_academic_rules(self) -> Dict[str, Any]:
        """استخراج قوانین تحصیلی از چارت درسی"""
        return self.curriculum_chart.get("academic_rules", {})
    
    async def analyze_student_status(self, student_id: int) -> StudentAcademicStatus:
        """تجزیه کامل وضعیت تحصیلی دانشجو"""
        async with get_db() as db:
            # دریافت اطلاعات دانشجو و نمرات
            student = await self._get_student_with_grades(db, student_id)
            if not student:
                raise ValueError(f"Student {student_id} not found")
            
            # تعیین نسخه چارت درسی
            curriculum_version = self._determine_curriculum_version(student.entry_year)
            
            # محاسبه GPA و واحدهای گذرانده شده
            gpa, total_credits = self._calculate_gpa_and_credits(student.grades)
            
            # تعیین وضعیت تحصیلی
            academic_standing = self._determine_academic_standing(gpa, student.grades)
            
            # شناسایی دروس مردودی و گذرانده شده
            failed_courses = self._get_failed_courses(student.grades)
            completed_courses = self._get_completed_courses(student.grades)
            
            # بررسی وضعیت پیش‌نیازها
            prerequisite_status = self._check_prerequisite_status(completed_courses, curriculum_version)
            
            # بررسی وضعیت گرایش
            specialization_status = self._analyze_specialization_status(completed_courses, student.current_semester)
            
            # محاسبه پیشرفت تحصیلی
            graduation_progress = self._calculate_graduation_progress(
                total_credits, completed_courses, curriculum_version
            )
            
            # تعیین گروه (برای ورودی‌های ۱۴۰۳ به بعد)
            group_assignment = self._determine_group_assignment(student.entry_year, student.student_number)
            
            return StudentAcademicStatus(
                student_id=student_id,
                current_gpa=gpa,
                total_credits_passed=total_credits,
                academic_standing=academic_standing,
                entry_year=student.entry_year,
                current_semester=student.current_semester,
                curriculum_version=curriculum_version,
                group_assignment=group_assignment,
                failed_courses=failed_courses,
                completed_courses=completed_courses,
                prerequisite_status=prerequisite_status,
                specialization_status=specialization_status,
                graduation_progress=graduation_progress
            )
    
    async def _get_student_with_grades(self, db, student_id: int) -> Optional[Student]:
        """دریافت دانشجو همراه با نمرات"""
        try:
            result = await db.execute(
                select(Student)
                .options(selectinload(Student.grades).selectinload(StudentGrade.course))
                .where(Student.id == student_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching student {student_id}: {e}")
            return None
    
    def _determine_curriculum_version(self, entry_year: int) -> str:
        """تعیین نسخه چارت درسی بر اساس سال ورود"""
        if entry_year >= 1403:
            return "post_1403"
        else:
            return "pre_1403"
    
    def _calculate_gpa_and_credits(self, grades: List[StudentGrade]) -> Tuple[float, int]:
        """محاسبه GPA و مجموع واحدهای گذرانده شده"""
        total_points = 0.0
        total_credits = 0
        passed_credits = 0
        
        for grade_record in grades:
            if grade_record.status not in ["passed", "confirmed"]:
                continue
                
            course = grade_record.course
            course_credits = course.theoretical_credits + course.practical_credits
            grade_value = float(grade_record.grade)
            
            # فقط آخرین تلاش برای هر درس در نظر گرفته شود
            if grade_value >= 10.0:  # قبولی
                total_points += grade_value * course_credits
                total_credits += course_credits
                passed_credits += course_credits
            else:  # مردودی
                total_points += grade_value * course_credits
                total_credits += course_credits
        
        gpa = total_points / total_credits if total_credits > 0 else 0.0
        return round(gpa, 2), passed_credits
    
    def _determine_academic_standing(self, gpa: float, grades: List[StudentGrade]) -> str:
        """تعیین وضعیت تحصیلی بر اساس GPA و نمرات"""
        rules = self.academic_rules.get("credit_limits", {})
        
        # بررسی مشروطی بر اساس GPA کل
        if gpa < 12.0:
            return "probation"
        
        # بررسی دروس مردودی در ترم جاری
        current_semester_failed = sum(
            1 for grade in grades 
            if grade.grade < 10.0 and grade.status == "confirmed"
        )
        
        if current_semester_failed > 2:
            return "probation"
        
        # وضعیت عادی یا عالی
        if gpa >= 17.0:
            return "excellent"
        elif gpa >= 15.0:
            return "good_standing"
        else:
            return "normal"
    
    def _get_failed_courses(self, grades: List[StudentGrade]) -> List[Dict[str, Any]]:
        """شناسایی دروس مردودی"""
        failed_courses = []
        course_attempts = {}
        
        # گروه‌بندی بر اساس کد درس
        for grade in grades:
            if grade.status != "confirmed":
                continue
                
            course_code = grade.course.course_code
            if course_code not in course_attempts:
                course_attempts[course_code] = []
            course_attempts[course_code].append(grade)
        
        # بررسی آخرین وضعیت هر درس
        for course_code, attempts in course_attempts.items():
            latest_attempt = max(attempts, key=lambda g: g.attempt_number)
            
            if latest_attempt.grade < 10.0:  # مردودی
                failed_courses.append({
                    "course_code": course_code,
                    "course_name": latest_attempt.course.course_name,
                    "grade": latest_attempt.grade,
                    "attempt_number": latest_attempt.attempt_number,
                    "credits": latest_attempt.course.theoretical_credits + latest_attempt.course.practical_credits,
                    "course_type": latest_attempt.course.course_type,
                    "priority": "high"  # دروس مردودی اولویت بالا دارند
                })
        
        return failed_courses
    
    def _get_completed_courses(self, grades: List[StudentGrade]) -> List[Dict[str, Any]]:
        """شناسایی دروس گذرانده شده"""
        completed_courses = []
        course_attempts = {}
        
        # گروه‌بندی بر اساس کد درس
        for grade in grades:
            if grade.status != "confirmed":
                continue
                
            course_code = grade.course.course_code
            if course_code not in course_attempts:
                course_attempts[course_code] = []
            course_attempts[course_code].append(grade)
        
        # بررسی آخرین وضعیت هر درس
        for course_code, attempts in course_attempts.items():
            latest_attempt = max(attempts, key=lambda g: g.attempt_number)
            
            if latest_attempt.grade >= 10.0:  # قبولی
                completed_courses.append({
                    "course_code": course_code,
                    "course_name": latest_attempt.course.course_name,
                    "grade": latest_attempt.grade,
                    "credits": latest_attempt.course.theoretical_credits + latest_attempt.course.practical_credits,
                    "course_type": latest_attempt.course.course_type,
                    "semester_taken": latest_attempt.created_at.strftime("%Y-%m") if latest_attempt.created_at else "unknown"
                })
        
        return completed_courses
    
    def _check_prerequisite_status(self, completed_courses: List[Dict], curriculum_version: str) -> Dict[str, bool]:
        """بررسی وضعیت پیش‌نیازها"""
        completed_codes = {course["course_code"] for course in completed_courses}
        prerequisite_status = {}
        
        # دریافت لیست تمام دروس از چارت
        curriculum = self.curriculum_chart.get("curriculum_versions", {}).get(curriculum_version, {})
        semester_structure = curriculum.get("semesters", {})
        
        for semester_num, semester_data in semester_structure.items():
            mandatory_courses = semester_data.get("courses", [])
            
            for course in mandatory_courses:
                course_code = course["course_code"]
                prerequisites = course.get("prerequisites", [])
                
                # بررسی تمام پیش‌نیازها
                all_met = all(prereq in completed_codes for prereq in prerequisites)
                prerequisite_status[course_code] = all_met
        
        return prerequisite_status
    
    def _analyze_specialization_status(self, completed_courses: List[Dict], current_semester: int) -> Dict[str, Any]:
        """تجزیه وضعیت گرایش تخصصی"""
        specialization_status = {
            "selection_allowed": current_semester >= 5,
            "selected_group": None,
            "completed_specialized_credits": 0,
            "progress_by_group": {}
        }
        
        # محاسبه واحدهای تخصصی گذرانده شده از هر گرایش
        specialization_data = self.curriculum_chart.get("specialization_groups", {})
        tracks = specialization_data.get("tracks", [])
        
        for track in tracks:
            track_name = track.get("track_name", "")
            track_courses = track.get("courses", [])
            min_credits = track.get("min_credits", 6)
            
            track_credits = 0
            
            for course in completed_courses:
                # بررسی اینکه آیا این درس جزو این گرایش است
                if course["course_code"] in track_courses:
                    track_credits += course["credits"]
            
            specialization_status["progress_by_group"][track_name] = {
                "credits_completed": track_credits,
                "persian_name": track_name,
                "minimum_required": min_credits,
                "is_sufficient": track_credits >= min_credits
            }
        
        # تعیین گرایش انتخابی (بیشترین تعداد واحد)
        if specialization_status["progress_by_group"]:
            max_group = max(
                specialization_status["progress_by_group"].items(),
                key=lambda x: x[1]["credits_completed"]
            )
            if max_group[1]["credits_completed"] >= 3:  # حداقل 3 واحد
                specialization_status["selected_group"] = max_group[0]
                specialization_status["completed_specialized_credits"] = max_group[1]["credits_completed"]
        
        return specialization_status
    
    def _calculate_graduation_progress(self, passed_credits: int, completed_courses: List[Dict], curriculum_version: str) -> Dict[str, Any]:
        """محاسبه پیشرفت تحصیلی"""
        total_required = 140  # مجموع واحدهای مورد نیاز
        
        # تفکیک واحدها بر اساس نوع درس
        credits_by_type = {
            "foundation": 0,
            "core": 0,
            "specialized": 0,
            "general": 0
        }
        
        for course in completed_courses:
            course_type = course.get("course_type", "general")
            if course_type in credits_by_type:
                credits_by_type[course_type] += course["credits"]
        
        # محاسبه درصد پیشرفت
        progress_percentage = (passed_credits / total_required) * 100
        
        # تعیین مرحله تحصیلی
        if passed_credits < 35:
            academic_level = "مقدماتی"
        elif passed_credits < 70:
            academic_level = "میانی"
        elif passed_credits < 105:
            academic_level = "پیشرفته"
        else:
            academic_level = "نهایی"
        
        return {
            "total_credits_passed": passed_credits,
            "total_credits_required": total_required,
            "progress_percentage": round(progress_percentage, 1),
            "academic_level": academic_level,
            "credits_by_type": credits_by_type,
            "remaining_credits": total_required - passed_credits,
            "estimated_semesters_to_graduation": max(1, (total_required - passed_credits) // 18)
        }
    
    def _determine_group_assignment(self, entry_year: int, student_number: str) -> Optional[str]:
        """تعیین گروه دانشجو برای ورودی‌های ۱۴۰۳ به بعد"""
        if entry_year < 1403:
            return None  # سیستم گروه‌بندی اعمال نمی‌شود
        
        # الگوریتم ساده برای تعیین گروه بر اساس شماره دانشجویی
        # در پیاده‌سازی واقعی، این اطلاعات باید از دیتابیس یا فایل مجزا آمده باشد
        try:
            last_digit = int(student_number[-1])
            return "A" if last_digit % 2 == 0 else "B"
        except (ValueError, IndexError):
            return "A"  # پیش‌فرض
    
    def get_credit_limit(self, gpa: float) -> Dict[str, int]:
        """محاسبه حد مجاز واحد بر اساس معدل"""
        rules = self.academic_rules.get("credit_limits", {})
        
        if gpa >= 17.0:
            return rules.get("gpa_17_plus", {"max_credits": 24, "min_credits": 12})
        elif gpa >= 15.0:
            return rules.get("gpa_15_to_17", {"max_credits": 20, "min_credits": 12})
        elif gpa >= 12.0:
            return rules.get("gpa_12_to_15", {"max_credits": 18, "min_credits": 12})
        else:
            return rules.get("gpa_below_12", {"max_credits": 16, "min_credits": 14})
    
    def analyze_course_recommendations_context(self, status: StudentAcademicStatus) -> Dict[str, Any]:
        """تجزیه کامل برای سیستم پیشنهاد دروس"""
        credit_limit = self.get_credit_limit(status.current_gpa)
        
        return {
            "student_profile": {
                "gpa": status.current_gpa,
                "academic_standing": status.academic_standing,
                "current_semester": status.current_semester,
                "entry_year": status.entry_year,
                "curriculum_version": status.curriculum_version,
                "group_assignment": status.group_assignment,
                "total_credits_passed": status.total_credits_passed
            },
            "academic_constraints": {
                "max_credits": credit_limit["max_credits"],
                "min_credits": credit_limit["min_credits"],
                "group_restrictions": status.group_assignment is not None and status.current_semester <= 2
            },
            "academic_priorities": {
                "failed_courses": status.failed_courses,
                "prerequisite_gaps": [
                    code for code, met in status.prerequisite_status.items() if not met
                ],
                "specialization_selection_needed": (
                    status.current_semester >= 5 and 
                    status.specialization_status["selected_group"] is None
                )
            },
            "graduation_status": status.graduation_progress,
            "specialization_analysis": status.specialization_status
        }