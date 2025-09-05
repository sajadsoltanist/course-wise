"""
Academic Rules Engine

موتور اعمال قوانین تحصیلی برای اعتبارسنجی و پیشنهاد دروس
شامل: بررسی پیش‌نیازها، محدودیت‌های واحدی، قوانین گرایش، تداخل زمانی
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, time
import json
from pathlib import Path
from loguru import logger

from app.services.student_analyzer import StudentAcademicStatus


@dataclass
class CourseValidationResult:
    """نتیجه اعتبارسنجی درس"""
    course_code: str
    is_valid: bool
    validation_errors: List[str]
    warnings: List[str]
    priority_score: int  # امتیاز اولویت (بالاتر = مهم‌تر)


@dataclass
class ScheduleConflict:
    """تداخل زمانی"""
    course1_code: str
    course2_code: str
    conflict_type: str  # "time_overlap", "lab_overlap", "exam_conflict"
    details: str


class AcademicRulesEngine:
    """موتور قوانین تحصیلی"""
    
    def __init__(self):
        self.curriculum_chart = self._load_curriculum_chart()
        self.curriculum_rules = self._load_curriculum_rules()
    
    def _load_curriculum_chart(self) -> Dict[str, Any]:
        """بارگذاری چارت‌های درسی"""
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
            logger.error(f"Error loading curriculum chart: {e}")
            return {}
    
    def _load_curriculum_rules(self) -> str:
        """بارگذاری قوانین تحصیلی متنی"""
        try:
            rules_path = Path(__file__).parent.parent.parent / "data" / "curriculum_rules.md"
            with open(rules_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading curriculum rules: {e}")
            return ""
    
    def validate_course_selection(
        self, 
        course_code: str, 
        student_status: StudentAcademicStatus,
        semester_offerings: Dict[str, Any],
        selected_courses: List[str] = None
    ) -> CourseValidationResult:
        """اعتبارسنجی کامل انتخاب یک درس"""
        
        selected_courses = selected_courses or []
        errors = []
        warnings = []
        priority_score = 0
        
        # 1. بررسی وجود درس در ارائه ترم جاری
        if not self._is_course_offered(course_code, semester_offerings, student_status.group_assignment):
            errors.append(f"درس {course_code} در این ترم ارائه نمی‌شود")
            return CourseValidationResult(course_code, False, errors, warnings, 0)
        
        # 2. بررسی پیش‌نیازها
        prerequisite_check = self._check_prerequisites(course_code, student_status)
        if not prerequisite_check["is_met"]:
            errors.extend(prerequisite_check["missing_prerequisites"])
        
        # 3. بررسی محدودیت گروه (ترم‌های 1 و 2 ورودی‌های ۱۴۰۳+)
        group_check = self._check_group_restrictions(course_code, student_status, semester_offerings)
        if not group_check["is_allowed"]:
            errors.append(group_check["error_message"])
        
        # 3.5. بررسی قوانین دروس عمومی
        general_check = self._check_general_course_rules(course_code, student_status, selected_courses)
        if not general_check["is_allowed"]:
            errors.extend(general_check["errors"])
        warnings.extend(general_check["warnings"])
        
        # 4. بررسی تداخل زمانی
        schedule_conflicts = self._check_schedule_conflicts(
            course_code, selected_courses, semester_offerings
        )
        if schedule_conflicts:
            for conflict in schedule_conflicts:
                errors.append(f"تداخل زمانی با درس {conflict.course2_code}: {conflict.details}")
        
        # 5. محاسبه اولویت
        priority_score = self._calculate_course_priority(course_code, student_status)
        
        # 6. هشدارها و توصیه‌ها
        warnings.extend(self._generate_course_warnings(course_code, student_status))
        
        is_valid = len(errors) == 0
        
        return CourseValidationResult(
            course_code=course_code,
            is_valid=is_valid,
            validation_errors=errors,
            warnings=warnings,
            priority_score=priority_score
        )
    
    def validate_full_course_selection(
        self, 
        selected_courses: List[str],
        student_status: StudentAcademicStatus,
        semester_offerings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """اعتبارسنجی کامل لیست دروس انتخابی"""
        
        results = {}
        total_credits = 0
        errors = []
        warnings = []
        
        # اعتبارسنجی هر درس
        for course_code in selected_courses:
            other_courses = [c for c in selected_courses if c != course_code]
            validation = self.validate_course_selection(
                course_code, student_status, semester_offerings, other_courses
            )
            results[course_code] = validation
            
            if validation.is_valid:
                course_credits = self._get_course_credits(course_code, semester_offerings)
                total_credits += course_credits
        
        # بررسی محدودیت واحدی
        credit_limit = self._get_credit_limit(student_status.current_gpa)
        if total_credits > credit_limit["max_credits"]:
            errors.append(f"تعداد واحدها ({total_credits}) از حد مجاز ({credit_limit['max_credits']}) بیشتر است")
        elif total_credits < credit_limit["min_credits"]:
            warnings.append(f"تعداد واحدها ({total_credits}) کمتر از حداقل مجاز ({credit_limit['min_credits']}) است")
        
        # بررسی تعادل دروس
        balance_analysis = self._analyze_course_balance(selected_courses, semester_offerings)
        warnings.extend(balance_analysis["warnings"])
        
        # بررسی اولویت‌ها
        priority_analysis = self._analyze_selection_priorities(selected_courses, student_status)
        warnings.extend(priority_analysis["suggestions"])
        
        return {
            "course_validations": results,
            "total_credits": total_credits,
            "credit_limits": credit_limit,
            "overall_errors": errors,
            "overall_warnings": warnings,
            "is_valid": len(errors) == 0,
            "balance_analysis": balance_analysis,
            "priority_analysis": priority_analysis
        }
    
    def _is_course_offered(
        self, 
        course_code: str, 
        semester_offerings: Dict[str, Any],
        student_group: Optional[str]
    ) -> bool:
        """بررسی ارائه درس در ترم جاری"""
        
        # بررسی در دروس گروه‌بندی شده
        if semester_offerings.get("group_based_system") and student_group:
            for group in semester_offerings.get("available_groups", []):
                if group["group_id"] == student_group:
                    for course in group.get("courses", []):
                        if course["course_code"] == course_code:
                            return True
        
        # بررسی در دروس عمومی/پیشرفته
        for category in ["general_courses", "advanced_courses"]:
            for course in semester_offerings.get(category, []):
                if course["course_code"] == course_code:
                    return True
                
                # بررسی sections
                for section in course.get("sections", []):
                    if not student_group or section.get("group") == student_group:
                        return True
        
        return False
    
    def _check_prerequisites(self, course_code: str, student_status: StudentAcademicStatus) -> Dict[str, Any]:
        """بررسی پیش‌نیازهای درس"""
        
        # پیدا کردن درس در چارت درسی
        curriculum = self.curriculum_chart["curriculum_versions"][student_status.curriculum_version]
        semester_structure = curriculum["semesters"]
        
        course_prerequisites = []
        for semester_data in semester_structure.values():
            for course in semester_data.get("courses", []):
                if course["course_code"] == course_code:
                    course_prerequisites = course.get("prerequisites", [])
                    break
        
        # اگر در دروس اجباری نبود، در دروس تخصصی جستجو کن
        if not course_prerequisites:
            specialization_data = self.curriculum_chart.get("specialization_groups", {})
            tracks = specialization_data.get("tracks", [])
            for track in tracks:
                track_courses = track.get("courses", [])
                if course_code in track_courses:
                    # برای دروس تخصصی پیش‌نیاز خاصی نیست
                    course_prerequisites = []
                    break
        
        # بررسی گذراندن پیش‌نیازها
        completed_codes = {c["course_code"] for c in student_status.completed_courses}
        missing_prerequisites = []
        
        for prereq in course_prerequisites:
            if prereq not in completed_codes:
                missing_prerequisites.append(f"پیش‌نیاز {prereq} گذرانده نشده است")
        
        return {
            "is_met": len(missing_prerequisites) == 0,
            "missing_prerequisites": missing_prerequisites,
            "required_prerequisites": course_prerequisites
        }
    
    def _check_group_restrictions(
        self,
        course_code: str,
        student_status: StudentAcademicStatus,
        semester_offerings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """بررسی محدودیت‌های گروهی"""
        
        # فقط برای ورودی‌های ۱۴۰۳+ و ترم‌های ۱ و ۲
        if (student_status.curriculum_version != "post_1403" or 
            student_status.current_semester > 2 or 
            not student_status.group_assignment):
            return {"is_allowed": True, "error_message": ""}
        
        # بررسی اینکه درس در گروه دانشجو ارائه می‌شود یا خیر
        student_group = student_status.group_assignment
        course_found_in_group = False
        
        for group in semester_offerings.get("available_groups", []):
            if group["group_id"] == student_group:
                for course in group.get("courses", []):
                    if course["course_code"] == course_code:
                        course_found_in_group = True
                        break
        
        if not course_found_in_group:
            return {
                "is_allowed": False,
                "error_message": f"درس {course_code} برای گروه {student_group} ارائه نمی‌شود"
            }
        
        return {"is_allowed": True, "error_message": ""}
    
    def _check_general_course_rules(
        self,
        course_code: str,
        student_status: StudentAcademicStatus,
        selected_courses: List[str]
    ) -> Dict[str, Any]:
        """بررسی قوانین دروس عمومی"""
        
        errors = []
        warnings = []
        
        try:
            # بارگذاری قوانین دروس عمومی
            data_path = Path(__file__).parent.parent.parent / "data"
            with open(data_path / "general_courses.json", 'r', encoding='utf-8') as f:
                general_rules = json.load(f)
            
            # بررسی محدودیت دروس معارف اسلامی
            religious_courses = [
                course["course_code"] for course in 
                general_rules["course_categories"]["religious_courses"]["courses"]
            ]
            
            if course_code in religious_courses:
                # شمارش دروس معارف انتخاب شده در ترم جاری
                selected_religious = [c for c in selected_courses if c in religious_courses]
                if len(selected_religious) >= 1:  # حداکثر یک درس معارف در ترم
                    errors.append("در هر ترم فقط یک درس معارف اسلامی قابل انتخاب است")
            
            # بررسی محدودیت تربیت بدنی
            pe_courses = [
                course["course_code"] for course in 
                general_rules["course_categories"]["physical_education"]["courses"]
            ]
            
            if course_code in pe_courses:
                # بررسی کل واحدهای تربیت بدنی گذرانده شده
                completed_pe_credits = sum(
                    course["credits"] for course in student_status.completed_courses
                    if course["course_code"] in pe_courses
                )
                
                if completed_pe_credits >= 2:
                    errors.append("حداکثر 2 واحد تربیت بدنی در کل دوره مجاز است")
            
            # بررسی ترتیب دروس زبان
            language_courses = [
                course["course_code"] for course in 
                general_rules["course_categories"]["language_courses"]["courses"]
            ]
            
            if course_code in language_courses:
                # پیدا کردن درس زبان انتخابی
                target_course = None
                for course in general_rules["course_categories"]["language_courses"]["courses"]:
                    if course["course_code"] == course_code:
                        target_course = course
                        break
                
                if target_course and target_course.get("prerequisites"):
                    completed_codes = {c["course_code"] for c in student_status.completed_courses}
                    for prereq in target_course["prerequisites"]:
                        if prereq not in completed_codes:
                            errors.append(f"پیش‌نیاز {prereq} برای درس زبان گذرانده نشده است")
            
        except Exception as e:
            logger.error(f"Error checking general course rules: {e}")
            warnings.append("خطا در بررسی قوانین دروس عمومی")
        
        return {
            "is_allowed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _check_schedule_conflicts(
        self,
        course_code: str,
        other_courses: List[str],
        semester_offerings: Dict[str, Any]
    ) -> List[ScheduleConflict]:
        """بررسی تداخل زمانی"""
        
        conflicts = []
        course_schedule = self._get_course_schedule(course_code, semester_offerings)
        
        if not course_schedule:
            return conflicts
        
        for other_course in other_courses:
            other_schedule = self._get_course_schedule(other_course, semester_offerings)
            if not other_schedule:
                continue
            
            # بررسی تداخل زمانی کلاس‌ها
            time_conflict = self._check_time_overlap(
                course_schedule.get("time_slots", []),
                other_schedule.get("time_slots", [])
            )
            
            if time_conflict:
                conflicts.append(ScheduleConflict(
                    course1_code=course_code,
                    course2_code=other_course,
                    conflict_type="time_overlap",
                    details=time_conflict
                ))
            
            # بررسی تداخل آزمایشگاه
            lab_conflict = self._check_time_overlap(
                course_schedule.get("lab_slots", []),
                other_schedule.get("lab_slots", [])
            )
            
            if lab_conflict:
                conflicts.append(ScheduleConflict(
                    course1_code=course_code,
                    course2_code=other_course,
                    conflict_type="lab_overlap",
                    details=lab_conflict
                ))
            
            # بررسی تداخل امتحان
            exam_conflict = self._check_exam_conflict(
                course_schedule.get("exam_date"),
                other_schedule.get("exam_date")
            )
            
            if exam_conflict:
                conflicts.append(ScheduleConflict(
                    course1_code=course_code,
                    course2_code=other_course,
                    conflict_type="exam_conflict",
                    details=exam_conflict
                ))
        
        return conflicts
    
    def _get_course_schedule(self, course_code: str, semester_offerings: Dict[str, Any]) -> Optional[Dict]:
        """دریافت برنامه زمانی درس"""
        
        # جستجو در دروس گروه‌بندی شده
        for group in semester_offerings.get("available_groups", []):
            for course in group.get("courses", []):
                if course["course_code"] == course_code:
                    return course
        
        # جستجو در دروس عمومی/پیشرفته
        for category in ["general_courses", "advanced_courses"]:
            for course in semester_offerings.get(category, []):
                if course["course_code"] == course_code:
                    return course
                
                # جستجو در sections
                for section in course.get("sections", []):
                    if course["course_code"] == course_code:
                        return section
        
        return None
    
    def _check_time_overlap(self, slots1: List[str], slots2: List[str]) -> Optional[str]:
        """بررسی تداخل زمانی بین دو لیست زمان"""
        
        for slot1 in slots1:
            for slot2 in slots2:
                if self._parse_time_overlap(slot1, slot2):
                    return f"تداخل در {slot1} و {slot2}"
        
        return None
    
    def _parse_time_overlap(self, slot1: str, slot2: str) -> bool:
        """تجزیه و بررسی تداخل دو بازه زمانی"""
        
        try:
            # استخراج روز و ساعت (مثال: "شنبه 8:00-10:30")
            day1, time1 = slot1.split(" ", 1)
            day2, time2 = slot2.split(" ", 1)
            
            # اگر روزها متفاوت باشند، تداخل نیست
            if day1 != day2:
                return False
            
            # تجزیه ساعت‌ها
            start1, end1 = time1.split("-")
            start2, end2 = time2.split("-")
            
            start1_hour, start1_min = map(int, start1.split(":"))
            end1_hour, end1_min = map(int, end1.split(":"))
            start2_hour, start2_min = map(int, start2.split(":"))
            end2_hour, end2_min = map(int, end2.split(":"))
            
            start1_total = start1_hour * 60 + start1_min
            end1_total = end1_hour * 60 + end1_min
            start2_total = start2_hour * 60 + start2_min
            end2_total = end2_hour * 60 + end2_min
            
            # بررسی تداخل
            return not (end1_total <= start2_total or end2_total <= start1_total)
            
        except (ValueError, IndexError):
            return False
    
    def _check_exam_conflict(self, exam1: Optional[str], exam2: Optional[str]) -> Optional[str]:
        """بررسی تداخل امتحان"""
        
        if not exam1 or not exam2:
            return None
        
        if exam1 == exam2:
            return f"امتحان در تاریخ {exam1}"
        
        return None
    
    def _calculate_course_priority(self, course_code: str, student_status: StudentAcademicStatus) -> int:
        """محاسبه امتیاز اولویت درس"""
        
        priority = 0
        
        # اولویت بالا برای دروس مردودی
        for failed_course in student_status.failed_courses:
            if failed_course["course_code"] == course_code:
                priority += 100
                # اولویت بیشتر برای تلاش‌های بیشتر
                priority += failed_course["attempt_number"] * 10
                break
        
        # اولویت متوسط برای دروس پیش‌نیاز
        if self._is_prerequisite_for_other_courses(course_code, student_status.curriculum_version):
            priority += 50
        
        # اولویت کم برای دروس اختیاری
        if self._is_elective_course(course_code):
            priority += 10
        
        # اولویت بر اساس ترم توصیه شده
        recommended_semester = self._get_recommended_semester(course_code, student_status.curriculum_version)
        if recommended_semester:
            if recommended_semester <= student_status.current_semester:
                priority += 30  # درس عقب‌افتاده
            elif recommended_semester == student_status.current_semester + 1:
                priority += 20  # درس ترم بعد
        
        return priority
    
    def _is_prerequisite_for_other_courses(self, course_code: str, curriculum_version: str) -> bool:
        """بررسی اینکه آیا درس پیش‌نیاز دروس دیگری است"""
        
        curriculum = self.curriculum_chart["curriculum_versions"][curriculum_version]
        semester_structure = curriculum["semesters"]
        
        for semester_data in semester_structure.values():
            for course in semester_data.get("courses", []):
                if course_code in course.get("prerequisites", []):
                    return True
        
        return False
    
    def _is_elective_course(self, course_code: str) -> bool:
        """بررسی اینکه آیا درس اختیاری است"""
        
        # جستجو در گرایش‌های تخصصی
        specialization_data = self.curriculum_chart.get("specialization_groups", {})
        tracks = specialization_data.get("tracks", [])
        for track in tracks:
            track_courses = track.get("courses", [])
            if course_code in track_courses:
                return True
        
        # جستجو در دروس عمومی اختیاری
        for course in self.curriculum_chart.get("general_electives", []):
            if course["course_code"] == course_code:
                return True
        
        return False
    
    def _get_recommended_semester(self, course_code: str, curriculum_version: str) -> Optional[int]:
        """دریافت ترم توصیه شده برای درس"""
        
        curriculum = self.curriculum_chart["curriculum_versions"][curriculum_version]
        semester_structure = curriculum["semesters"]
        
        for semester_num, semester_data in semester_structure.items():
            for course in semester_data.get("courses", []):
                if course["course_code"] == course_code:
                    return int(semester_num)
        
        return None
    
    def _get_course_credits(self, course_code: str, semester_offerings: Dict[str, Any]) -> int:
        """دریافت تعداد واحدهای درس"""
        
        course_info = self._get_course_schedule(course_code, semester_offerings)
        if course_info and "credits" in course_info:
            credits = course_info["credits"]
            if isinstance(credits, dict):
                return credits.get("theoretical", 0) + credits.get("practical", 0)
            else:
                return credits
        
        return 0
    
    def _get_credit_limit(self, gpa: float) -> Dict[str, int]:
        """دریافت محدودیت واحدی بر اساس معدل"""
        
        rules = self.curriculum_chart.get("academic_rules", {}).get("credit_limits", {})
        
        if gpa >= 17.0:
            return rules.get("gpa_17_plus", {"max_credits": 24, "min_credits": 12})
        elif gpa >= 15.0:
            return rules.get("gpa_15_to_17", {"max_credits": 20, "min_credits": 12})
        elif gpa >= 12.0:
            return rules.get("gpa_12_to_15", {"max_credits": 18, "min_credits": 12})
        else:
            return rules.get("gpa_below_12", {"max_credits": 16, "min_credits": 14})
    
    def _generate_course_warnings(self, course_code: str, student_status: StudentAcademicStatus) -> List[str]:
        """تولید هشدارها و توصیه‌ها برای درس"""
        
        warnings = []
        
        # هشدار برای دروس سخت
        if self._is_difficult_course(course_code):
            if student_status.current_gpa < 14.0:
                warnings.append(f"درس {course_code} سطح دشواری بالایی دارد")
        
        # هشدار برای انتخاب بیش از حد از یک گرایش
        specialization_credits = self._count_specialization_credits(course_code, student_status)
        if specialization_credits > 18:
            warnings.append(f"تعداد واحدهای انتخابی از این گرایش بالا است")
        
        return warnings
    
    def _is_difficult_course(self, course_code: str) -> bool:
        """بررسی سطح دشواری درس"""
        
        # دروس تخصصی معمولاً سختتر هستند
        specialization_data = self.curriculum_chart.get("specialization_groups", {})
        tracks = specialization_data.get("tracks", [])
        for track in tracks:
            track_courses = track.get("courses", [])
            if course_code in track_courses:
                return True  # دروس تخصصی را سخت در نظر می‌گیریم
        
        return False
    
    def _count_specialization_credits(self, course_code: str, student_status: StudentAcademicStatus) -> int:
        """شمارش واحدهای انتخابی از گرایش مشخص"""
        
        target_track = None
        specialization_data = self.curriculum_chart.get("specialization_groups", {})
        tracks = specialization_data.get("tracks", [])
        
        for track in tracks:
            track_courses = track.get("courses", [])
            if course_code in track_courses:
                target_track = track
                break
        
        if not target_track:
            return 0
        
        total_credits = 0
        track_courses = target_track.get("courses", [])
        
        for completed_course in student_status.completed_courses:
            if completed_course["course_code"] in track_courses:
                total_credits += completed_course["credits"]
        
        return total_credits
    
    def _analyze_course_balance(self, selected_courses: List[str], semester_offerings: Dict[str, Any]) -> Dict[str, Any]:
        """تجزیه تعادل دروس انتخابی"""
        
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        type_counts = {"foundation": 0, "core": 0, "specialized": 0, "general": 0}
        warnings = []
        
        for course_code in selected_courses:
            # تجزیه سطح دشواری
            difficulty = self._get_course_difficulty(course_code)
            if difficulty in difficulty_counts:
                difficulty_counts[difficulty] += 1
            
            # تجزیه نوع درس
            course_type = self._get_course_type(course_code)
            if course_type in type_counts:
                type_counts[course_type] += 1
        
        # تولید هشدارها
        if difficulty_counts["hard"] > 2:
            warnings.append("تعداد دروس سخت زیاد است - توصیه می‌شود تعادل ایجاد کنید")
        
        if type_counts["specialized"] > 3:
            warnings.append("تعداد دروس تخصصی زیاد است - دروس عمومی را نیز در نظر بگیرید")
        
        return {
            "difficulty_distribution": difficulty_counts,
            "type_distribution": type_counts,
            "warnings": warnings,
            "balance_score": self._calculate_balance_score(difficulty_counts, type_counts)
        }
    
    def _get_course_difficulty(self, course_code: str) -> str:
        """دریافت سطح دشواری درس"""
        
        for group_data in self.curriculum_chart.get("specialization_groups", {}).values():
            for course in group_data.get("courses", []):
                if course["course_code"] == course_code:
                    return course.get("difficulty", "medium")
        
        for course in self.curriculum_chart.get("general_electives", []):
            if course["course_code"] == course_code:
                return course.get("difficulty", "easy")
        
        return "medium"
    
    def _get_course_type(self, course_code: str) -> str:
        """دریافت نوع درس"""
        
        # جستجو در چارت درسی
        for version_data in self.curriculum_chart.get("curriculum_versions", {}).values():
            for semester_data in version_data.get("semesters", {}).values():
                for course in semester_data.get("courses", []):
                    if course["course_code"] == course_code:
                        return course.get("course_type", "core")
        
        # جستجو در گرایش‌ها
        specialization_data = self.curriculum_chart.get("specialization_groups", {})
        tracks = specialization_data.get("tracks", [])
        for track in tracks:
            track_courses = track.get("courses", [])
            if course_code in track_courses:
                return "specialized"
        
        return "general"
    
    def _calculate_balance_score(self, difficulty_counts: Dict, type_counts: Dict) -> int:
        """محاسبه امتیاز تعادل (0-100)"""
        
        score = 100
        
        # کسر امتیاز برای عدم تعادل در سطح دشواری
        total_courses = sum(difficulty_counts.values())
        if total_courses > 0:
            hard_ratio = difficulty_counts["hard"] / total_courses
            if hard_ratio > 0.6:  # بیش از 60% سخت
                score -= 30
            elif hard_ratio < 0.1:  # کمتر از 10% سخت
                score -= 10
        
        # کسر امتیاز برای عدم تعادل در نوع درس
        total_courses = sum(type_counts.values())
        if total_courses > 0:
            specialized_ratio = type_counts["specialized"] / total_courses
            if specialized_ratio > 0.7:  # بیش از 70% تخصصی
                score -= 20
        
        return max(0, score)
    
    def _analyze_selection_priorities(self, selected_courses: List[str], student_status: StudentAcademicStatus) -> Dict[str, Any]:
        """تجزیه اولویت‌های انتخاب دروس"""
        
        suggestions = []
        
        # بررسی دروس مردودی
        failed_codes = {course["course_code"] for course in student_status.failed_courses}
        selected_failed = failed_codes.intersection(set(selected_courses))
        missed_failed = failed_codes - set(selected_courses)
        
        if missed_failed:
            suggestions.append(f"دروس مردودی نادیده گرفته شده: {', '.join(missed_failed)}")
        
        # بررسی پیش‌نیازها
        missing_prerequisites = []
        for course_code in selected_courses:
            prereq_check = self._check_prerequisites(course_code, student_status)
            if not prereq_check["is_met"]:
                missing_prerequisites.extend(prereq_check["required_prerequisites"])
        
        if missing_prerequisites:
            suggestions.append(f"پیش‌نیازهای مفقود: {', '.join(set(missing_prerequisites))}")
        
        return {
            "selected_failed_courses": list(selected_failed),
            "missed_failed_courses": list(missed_failed),
            "missing_prerequisites": missing_prerequisites,
            "suggestions": suggestions
        }