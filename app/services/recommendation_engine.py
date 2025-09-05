"""
Course Recommendation Engine

موتور پیشنهاد دروس هوشمند با ترکیب منطق قوانین و LLM
شامل: الگوریتم اولویت‌بندی، بهینه‌سازی برنامه زمانی، پیشنهاد LLM
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import asyncio
from loguru import logger

from app.services.context_assembly import ContextAssemblyService
from app.services.academic_rules import AcademicRulesEngine
from app.services.llm import LLMService
from app.services.student_analyzer import StudentAcademicStatus


@dataclass
class CourseRecommendation:
    """پیشنهاد درس"""
    course_code: str
    course_name: str
    credits: int
    priority_score: int
    recommendation_reason: str
    time_slots: List[str]
    instructor: str
    prerequisites_met: bool
    difficulty_level: str
    course_type: str


@dataclass
class WeeklySchedule:
    """برنامه هفتگی"""
    total_credits: int
    courses_by_day: Dict[str, List[CourseRecommendation]]
    conflicts: List[str]
    balance_score: int
    recommendations: List[CourseRecommendation]


class RecommendationEngine:
    """موتور پیشنهاد دروس هوشمند"""
    
    def __init__(self):
        self.context_assembly = ContextAssemblyService()
        self.rules_engine = AcademicRulesEngine()
        self.llm_service = LLMService()
    
    async def generate_course_recommendations(
        self,
        student_id: int,
        target_semester: str,
        user_preferences: Optional[Dict[str, Any]] = None,
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """تولید پیشنهاد کامل دروس"""
        
        try:
            logger.info(f"Generating recommendations for student {student_id}, semester {target_semester}")
            
            # 1. تجمیع کانتکست کامل
            context = await self.context_assembly.assemble_complete_context(
                student_id, target_semester, user_preferences
            )
            
            # 2. پیشنهاد اولیه بر اساس قوانین
            rule_based_recommendations = self._generate_rule_based_recommendations(context)
            
            # 3. پیشنهاد LLM (اختیاری)
            llm_recommendations = None
            if use_llm:
                try:
                    llm_recommendations = await self._generate_llm_recommendations(context)
                except Exception as e:
                    logger.warning(f"LLM recommendation failed, using rule-based only: {e}")
            
            # 4. ترکیب و بهینه‌سازی پیشنهادات
            if llm_recommendations and llm_recommendations.get("success"):
                llm_courses = llm_recommendations.get("recommendations", {}).get("courses", [])
                logger.info(f"LLM provided {len(llm_courses)} course recommendations")
                if llm_courses:
                    logger.info(f"LLM course codes: {[c.get('course_code', 'unknown') for c in llm_courses]}")
            else:
                logger.warning("No valid LLM recommendations received")
            
            final_recommendations = self._combine_recommendations(
                rule_based_recommendations, llm_recommendations, context
            )
            
            # 5. ساخت برنامه هفتگی
            weekly_schedule = self._build_weekly_schedule(final_recommendations, context)
            
            # 6. اعتبارسنجی نهایی
            validation_result = self._validate_final_recommendations(
                final_recommendations, context
            )
            
            result = {
                "student_id": student_id,
                "target_semester": target_semester,
                "recommendation_strategy": context["recommendation_constraints"]["recommendation_strategy"],
                "total_available_courses": len(context["available_courses"]),
                
                "recommendations": {
                    "rule_based": rule_based_recommendations,
                    "llm_based": llm_recommendations,
                    "final": final_recommendations
                },
                
                "weekly_schedule": weekly_schedule.__dict__,
                "validation": validation_result,
                
                "academic_context": {
                    "student_gpa": context["student_profile"]["basic_info"]["current_gpa"],
                    "credit_limit": context["recommendation_constraints"]["credit_constraints"],
                    "failed_courses_count": len(context["academic_history"]["failed_courses"]["courses"]),
                    "group_restrictions": context["recommendation_constraints"]["priority_constraints"]["group_restrictions_active"]
                },
                
                "explanation": self._generate_explanation(context, final_recommendations, weekly_schedule)
            }
            
            logger.info(f"Successfully generated {len(final_recommendations)} recommendations for student {student_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating recommendations for student {student_id}: {e}")
            raise
    
    def _calculate_course_credits(self, course: Dict[str, Any]) -> int:
        """محاسبه مجموع واحدهای یک درس"""
        credits = course["credits"]
        if isinstance(credits, dict):
            return credits.get("theoretical", 0) + credits.get("practical", 0)
        else:
            return credits

    def _generate_rule_based_recommendations(self, context: Dict[str, Any]) -> List[CourseRecommendation]:
        """تولید پیشنهاد بر اساس قوانین"""
        
        recommendations = []
        available_courses = context["available_courses"]
        constraints = context["recommendation_constraints"]
        max_credits = constraints["credit_constraints"]["max_credits"]
        
        # مرحله 1: دروس مردودی (اولویت بالا)
        failed_courses = context["academic_history"]["failed_courses"]["courses"]
        for failed_course in failed_courses:
            course_code = failed_course["course_code"]
            matching_course = self._find_course_in_offerings(course_code, available_courses)
            
            if matching_course and matching_course["validation"]["is_valid"]:
                recommendations.append(self._create_course_recommendation(
                    matching_course, 
                    priority_score=100 + failed_course["attempt_number"] * 10,
                    reason=f"درس مردودی - تلاش {failed_course['attempt_number']}"
                ))
        
        # مرحله 2: دروس پیش‌نیاز مفقود
        current_credits = sum(rec.credits for rec in recommendations)
        if current_credits < max_credits:
            prerequisite_courses = self._find_prerequisite_courses(context, available_courses)
            for course in prerequisite_courses:
                course_credits = self._calculate_course_credits(course)
                if current_credits + course_credits <= max_credits:
                    recommendations.append(self._create_course_recommendation(
                        course,
                        priority_score=80,
                        reason="پیش‌نیاز برای دروس آینده"
                    ))
                    current_credits += course_credits
        
        # مرحله 3: دروس اجباری ترم جاری
        if current_credits < max_credits:
            mandatory_courses = self._find_mandatory_courses(context, available_courses)
            for course in mandatory_courses:
                course_credits = self._calculate_course_credits(course)
                if current_credits + course_credits <= max_credits:
                    recommendations.append(self._create_course_recommendation(
                        course,
                        priority_score=70,
                        reason="درس اجباری ترم جاری"
                    ))
                    current_credits += course_credits
        
        # مرحله 4: دروس گرایش (در صورت نیاز)
        if current_credits < max_credits and context["student_profile"]["basic_info"]["current_semester"] >= 5:
            specialization_courses = self._find_specialization_courses(context, available_courses)
            for course in specialization_courses:
                course_credits = self._calculate_course_credits(course)
                if current_credits + course_credits <= max_credits:
                    recommendations.append(self._create_course_recommendation(
                        course,
                        priority_score=60,
                        reason="تقویت گرایش تخصصی"
                    ))
                    current_credits += course_credits
        
        # مرحله 5: دروس اختیاری تکمیلی
        min_credits = constraints["credit_constraints"]["min_credits"]
        if current_credits < min_credits:
            elective_courses = self._find_elective_courses(context, available_courses)
            for course in elective_courses:
                course_credits = self._calculate_course_credits(course)
                if current_credits + course_credits <= max_credits:
                    recommendations.append(self._create_course_recommendation(
                        course,
                        priority_score=40,
                        reason="تکمیل حداقل واحد مجاز"
                    ))
                    current_credits += course_credits
                    if current_credits >= min_credits:
                        break
        
        # مرتب‌سازی بر اساس اولویت
        recommendations.sort(key=lambda x: x.priority_score, reverse=True)
        
        return recommendations
    
    async def _generate_llm_recommendations(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """تولید پیشنهاد توسط LLM"""
        
        try:
            # فرمت کردن کانتکست برای LLM
            formatted_context = self.context_assembly.format_context_for_llm(context)
            
            # ارسال درخواست به LLM
            llm_response = await self.llm_service.generate_course_recommendations(
                context=formatted_context,
                student_preferences=context.get("user_preferences", {}),
                available_courses=context["available_courses"]
            )
            
            return llm_response
            
        except Exception as e:
            logger.error(f"LLM recommendation failed: {e}")
            return None
    
    def _combine_recommendations(
        self, 
        rule_based: List[CourseRecommendation],
        llm_based: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[CourseRecommendation]:
        """ترکیب پیشنهادات rule-based و LLM"""
        
        logger.info(f"Starting combination: rule_based={len(rule_based)} courses, llm_based={llm_based is not None}")
        
        if not llm_based or not llm_based.get("success"):
            logger.info("LLM recommendations not available or failed, using rule-based only")
            return rule_based
        
        # استخراج پیشنهادات LLM
        llm_recommendations = llm_based.get("recommendations", {})
        llm_courses = llm_recommendations.get("courses", [])
        
        logger.info(f"LLM response structure: {list(llm_based.keys())}")
        logger.info(f"LLM recommendations structure: {list(llm_recommendations.keys()) if llm_recommendations else 'None'}")
        logger.info(f"Found {len(llm_courses)} courses in LLM recommendations")
        
        if not llm_courses:
            logger.warning("No courses found in LLM recommendations, using rule-based")
            return rule_based
        
        # تبدیل پیشنهادات LLM به فرمت CourseRecommendation
        combined = []
        available_courses = context.get("available_courses", [])
        logger.info(f"Available courses for matching: {len(available_courses)}")
        
        for i, llm_course in enumerate(llm_courses[:10]):  # حداکثر 10 درس
            course_code = llm_course.get("course_code", "")
            logger.info(f"Processing LLM course {i+1}: {course_code} - {llm_course}")
            
            # پیدا کردن جزئیات کامل درس از available_courses
            full_course_info = None
            for available_course in available_courses:
                if available_course.get("course_code") == course_code:
                    full_course_info = available_course
                    break
            
            logger.info(f"Found full course info for {course_code}: {full_course_info is not None}")
            
            try:
                if full_course_info:
                    # استفاده از اطلاعات کامل درس
                    recommendation = CourseRecommendation(
                        course_code=course_code,
                        course_name=full_course_info.get("course_name", llm_course.get("course_name", "")),
                        credits=self._calculate_course_credits(full_course_info),
                        recommendation_reason=f"پیشنهاد LLM - اولویت {i+1}",
                        priority_score=90 - i,  # اولویت کاهشی
                        time_slots=full_course_info.get("time_slots", []),
                        instructor=full_course_info.get("instructor", ""),
                        prerequisites_met=True,  # فرض می‌کنیم LLM پیش‌نیازها رو چک کرده
                        difficulty_level="medium",  # پیش‌فرض متوسط
                        course_type=full_course_info.get("course_type", "core")
                    )
                else:
                    # استفاده از اطلاعات محدود LLM
                    recommendation = CourseRecommendation(
                        course_code=course_code,
                        course_name=llm_course.get("course_name", f"درس {course_code}"),
                        credits=llm_course.get("credits", 3),
                        recommendation_reason=f"پیشنهاد LLM - اولویت {i+1}",
                        priority_score=90 - i,
                        time_slots=llm_course.get("time_slots", ["نامشخص"]),
                        instructor=llm_course.get("instructor", "نامشخص"),
                        prerequisites_met=True,  # فرض می‌کنیم LLM پیش‌نیازها رو چک کرده
                        difficulty_level="medium",  # پیش‌فرض متوسط
                        course_type="core"  # پیش‌فرض
                    )
                
                logger.info(f"Successfully created CourseRecommendation for {course_code}")
                combined.append(recommendation)
                logger.info(f"Added recommendation to combined list: {len(combined)} total")
                
            except Exception as e:
                logger.error(f"Failed to create CourseRecommendation for {course_code}: {e}")
                logger.error(f"LLM course data: {llm_course}")
                logger.error(f"Full course info: {full_course_info}")
                continue
        
        # اضافه کردن پیشنهادات rule-based که در LLM نیست
        llm_course_codes = {c.get("course_code") for c in llm_courses}
        for rule_rec in rule_based:
            if rule_rec.course_code not in llm_course_codes:
                # کاهش اولویت پیشنهادات rule-based
                rule_rec.priority_score = max(0, rule_rec.priority_score - 20)
                combined.append(rule_rec)
        
        # مرتب‌سازی بر اساس اولویت
        combined.sort(key=lambda x: x.priority_score, reverse=True)
        
        logger.info(f"Combined {len(llm_courses)} LLM recommendations with {len(rule_based)} rule-based")
        return combined[:10]  # حداکثر 10 پیشنهاد
    
    def _build_weekly_schedule(
        self, 
        recommendations: List[CourseRecommendation], 
        context: Dict[str, Any]
    ) -> WeeklySchedule:
        """ساخت برنامه هفتگی"""
        
        weekdays = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
        courses_by_day = {day: [] for day in weekdays}
        conflicts = []
        
        # پخش دروس در روزهای هفته
        for recommendation in recommendations:
            for time_slot in recommendation.time_slots:
                try:
                    day, time_range = time_slot.split(" ", 1)
                    if day in courses_by_day:
                        # بررسی تداخل زمانی
                        has_conflict = self._check_day_conflict(
                            courses_by_day[day], recommendation, time_range
                        )
                        
                        if not has_conflict:
                            courses_by_day[day].append(recommendation)
                        else:
                            conflicts.append(f"تداخل زمانی: {recommendation.course_name} در {time_slot}")
                            
                except ValueError:
                    logger.warning(f"Invalid time slot format: {time_slot}")
        
        total_credits = sum(rec.credits for rec in recommendations)
        balance_score = self._calculate_schedule_balance(courses_by_day, recommendations)
        
        return WeeklySchedule(
            total_credits=total_credits,
            courses_by_day=courses_by_day,
            conflicts=conflicts,
            balance_score=balance_score,
            recommendations=recommendations
        )
    
    def _validate_final_recommendations(
        self, 
        recommendations: List[CourseRecommendation],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """اعتبارسنجی نهایی پیشنهادات"""
        
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "summary": {}
        }
        
        total_credits = sum(rec.credits for rec in recommendations)
        constraints = context["recommendation_constraints"]["credit_constraints"]
        
        # بررسی محدودیت واحدی
        if total_credits > constraints["max_credits"]:
            validation_result["is_valid"] = False
            validation_result["errors"].append(
                f"تعداد واحدها ({total_credits}) از حد مجاز ({constraints['max_credits']}) بیشتر است"
            )
        elif total_credits < constraints["min_credits"]:
            validation_result["warnings"].append(
                f"تعداد واحدها ({total_credits}) کمتر از حداقل ({constraints['min_credits']}) است"
            )
        
        # بررسی پیش‌نیازها
        prerequisite_errors = []
        for rec in recommendations:
            if not rec.prerequisites_met:
                prerequisite_errors.append(f"پیش‌نیازهای {rec.course_name} برآورده نشده")
        
        if prerequisite_errors:
            validation_result["errors"].extend(prerequisite_errors)
            validation_result["is_valid"] = False
        
        # تجزیه توزیع دروس
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        type_counts = {"foundation": 0, "core": 0, "specialized": 0, "general": 0}
        
        for rec in recommendations:
            if rec.difficulty_level in difficulty_counts:
                difficulty_counts[rec.difficulty_level] += 1
            if rec.course_type in type_counts:
                type_counts[rec.course_type] += 1
        
        # هشدارهای تعادل
        total_courses = len(recommendations)
        if total_courses > 0:
            hard_ratio = difficulty_counts["hard"] / total_courses
            if hard_ratio > 0.6:
                validation_result["warnings"].append("نسبت دروس سخت بالا است")
        
        validation_result["summary"] = {
            "total_credits": total_credits,
            "total_courses": total_courses,
            "difficulty_distribution": difficulty_counts,
            "type_distribution": type_counts,
            "failed_courses_covered": self._count_failed_courses_covered(recommendations, context),
            "prerequisites_covered": self._count_prerequisites_covered(recommendations, context)
        }
        
        return validation_result
    
    def _find_course_in_offerings(self, course_code: str, available_courses: List[Dict]) -> Optional[Dict]:
        """پیدا کردن درس در لیست ارائه دروس"""
        for course in available_courses:
            if course["course_code"] == course_code and course["validation"]["is_valid"]:
                return course
        return None
    
    def _create_course_recommendation(
        self, 
        course_data: Dict[str, Any], 
        priority_score: int,
        reason: str
    ) -> CourseRecommendation:
        """ساخت شیء پیشنهاد درس"""
        
        credits = course_data["credits"]
        if isinstance(credits, dict):
            total_credits = credits.get("theoretical", 0) + credits.get("practical", 0)
        else:
            total_credits = credits
        
        return CourseRecommendation(
            course_code=course_data["course_code"],
            course_name=course_data["course_name"],
            credits=total_credits,
            priority_score=priority_score,
            recommendation_reason=reason,
            time_slots=course_data.get("time_slots", []),
            instructor=course_data.get("instructor", "نامشخص"),
            prerequisites_met=course_data["validation"]["is_valid"],
            difficulty_level=course_data.get("difficulty", "medium"),
            course_type=course_data.get("course_type", "general")
        )
    
    def _find_prerequisite_courses(self, context: Dict[str, Any], available_courses: List[Dict]) -> List[Dict]:
        """پیدا کردن دروس پیش‌نیاز مفقود"""
        unmet_prerequisites = context["academic_history"]["prerequisite_analysis"]["unmet_prerequisites"]
        prerequisite_courses = []
        
        for course_code in unmet_prerequisites:
            course = self._find_course_in_offerings(course_code, available_courses)
            if course:
                prerequisite_courses.append(course)
        
        return prerequisite_courses
    
    def _find_mandatory_courses(self, context: Dict[str, Any], available_courses: List[Dict]) -> List[Dict]:
        """پیدا کردن دروس اجباری ترم جاری"""
        current_semester = context["student_profile"]["basic_info"]["current_semester"]
        curriculum_version = context["student_profile"]["basic_info"]["curriculum_version"]
        
        curriculum_context = context["curriculum_context"]
        current_semester_courses = curriculum_context.get("current_semester_expectations", {})
        mandatory_course_codes = [
            course["course_code"] 
            for course in current_semester_courses.get("mandatory_courses", [])
        ]
        
        # فیلتر کردن دروسی که قبلاً گذرانده نشده‌اند
        completed_codes = {
            course["course_code"] 
            for course in context["academic_history"]["completed_courses"]["courses"]
        }
        
        pending_mandatory = [code for code in mandatory_course_codes if code not in completed_codes]
        
        mandatory_courses = []
        for course_code in pending_mandatory:
            course = self._find_course_in_offerings(course_code, available_courses)
            if course:
                mandatory_courses.append(course)
        
        return mandatory_courses
    
    def _find_specialization_courses(self, context: Dict[str, Any], available_courses: List[Dict]) -> List[Dict]:
        """پیدا کردن دروس گرایش"""
        specialization_status = context["student_profile"]["specialization_status"]
        selected_group = specialization_status.get("selected_group")
        
        if not selected_group:
            # اگر گرایش انتخاب نشده، از بیشترین واحد استفاده کن
            progress_by_group = specialization_status.get("progress_by_group", {})
            if progress_by_group:
                selected_group = max(
                    progress_by_group.items(),
                    key=lambda x: x[1]["credits_completed"]
                )[0]
        
        if not selected_group:
            return []
        
        # دریافت دروس گرایش از چارت
        try:
            curriculum_context = context.get("curriculum_context", {})
            specialization_data = curriculum_context.get("specialization_groups", {})
            tracks = specialization_data.get("tracks", [])
            logger.debug(f"Found {len(tracks)} specialization tracks")
        except Exception as e:
            logger.error(f"Error accessing specialization data: {e}")
            logger.error(f"Available context keys: {list(context.keys())}")
            if "curriculum_context" in context:
                logger.error(f"curriculum_context keys: {list(context['curriculum_context'].keys())}")
            tracks = []
        
        group_course_codes = []
        for track in tracks:
            if track.get("track_name") == selected_group:
                group_course_codes = track.get("courses", [])
                break
        
        # فیلتر کردن دروسی که قبلاً گذرانده نشده‌اند
        completed_codes = {
            course["course_code"] 
            for course in context["academic_history"]["completed_courses"]["courses"]
        }
        
        pending_specialization = [code for code in group_course_codes if code not in completed_codes]
        
        specialization_courses = []
        for course_code in pending_specialization:
            course = self._find_course_in_offerings(course_code, available_courses)
            if course:
                specialization_courses.append(course)
        
        return specialization_courses
    
    def _find_elective_courses(self, context: Dict[str, Any], available_courses: List[Dict]) -> List[Dict]:
        """پیدا کردن دروس اختیاری"""
        elective_courses = []
        
        # دروس عمومی اختیاری
        general_electives = context["curriculum_context"].get("general_electives", [])
        general_codes = [course["course_code"] for course in general_electives]
        
        # دروس تخصصی اختیاری (از گرایش‌های دیگر)
        try:
            curriculum_context = context.get("curriculum_context", {})
            specialization_data = curriculum_context.get("specialization_groups", {})
            tracks = specialization_data.get("tracks", [])
        except Exception as e:
            logger.error(f"Error accessing specialization data in electives: {e}")
            tracks = []
        all_specialization_codes = []
        for track in tracks:
            all_specialization_codes.extend(track.get("courses", []))
        
        elective_codes = general_codes + all_specialization_codes
        
        # فیلتر کردن دروسی که قبلاً گذرانده نشده‌اند
        completed_codes = {
            course["course_code"] 
            for course in context["academic_history"]["completed_courses"]["courses"]
        }
        
        pending_electives = [code for code in elective_codes if code not in completed_codes]
        
        for course_code in pending_electives:
            course = self._find_course_in_offerings(course_code, available_courses)
            if course:
                elective_courses.append(course)
        
        return elective_courses
    
    def _check_day_conflict(
        self, 
        day_courses: List[CourseRecommendation], 
        new_course: CourseRecommendation,
        time_range: str
    ) -> bool:
        """بررسی تداخل زمانی در یک روز"""
        
        for existing_course in day_courses:
            for existing_slot in existing_course.time_slots:
                try:
                    existing_day, existing_time = existing_slot.split(" ", 1)
                    if self._time_ranges_overlap(existing_time, time_range):
                        return True
                except ValueError:
                    continue
        
        return False
    
    def _time_ranges_overlap(self, time1: str, time2: str) -> bool:
        """بررسی تداخل دو بازه زمانی"""
        
        try:
            start1, end1 = time1.split("-")
            start2, end2 = time2.split("-")
            
            start1_min = self._time_to_minutes(start1)
            end1_min = self._time_to_minutes(end1)
            start2_min = self._time_to_minutes(start2)
            end2_min = self._time_to_minutes(end2)
            
            return not (end1_min <= start2_min or end2_min <= start1_min)
            
        except (ValueError, IndexError):
            return False
    
    def _time_to_minutes(self, time_str: str) -> int:
        """تبدیل زمان به دقیقه"""
        try:
            hour, minute = map(int, time_str.split(":"))
            return hour * 60 + minute
        except (ValueError, IndexError):
            return 0
    
    def _calculate_schedule_balance(
        self, 
        courses_by_day: Dict[str, List[CourseRecommendation]],
        all_recommendations: List[CourseRecommendation]
    ) -> int:
        """محاسبه امتیاز تعادل برنامه (0-100)"""
        
        score = 100
        
        # کسر امتیاز برای توزیع نامتعادل در روزهای هفته
        course_counts_per_day = [len(courses) for courses in courses_by_day.values()]
        if course_counts_per_day:
            max_courses_per_day = max(course_counts_per_day)
            if max_courses_per_day > 3:
                score -= 20
        
        # کسر امتیاز برای عدم تعادل در سطح دشواری
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        for rec in all_recommendations:
            if rec.difficulty_level in difficulty_counts:
                difficulty_counts[rec.difficulty_level] += 1
        
        total_courses = len(all_recommendations)
        if total_courses > 0:
            hard_ratio = difficulty_counts["hard"] / total_courses
            if hard_ratio > 0.6:
                score -= 30
        
        return max(0, score)
    
    def _count_failed_courses_covered(
        self, 
        recommendations: List[CourseRecommendation], 
        context: Dict[str, Any]
    ) -> int:
        """شمارش دروس مردودی پوشش داده شده"""
        
        failed_codes = {
            course["course_code"] 
            for course in context["academic_history"]["failed_courses"]["courses"]
        }
        
        recommended_codes = {rec.course_code for rec in recommendations}
        
        return len(failed_codes.intersection(recommended_codes))
    
    def _count_prerequisites_covered(
        self, 
        recommendations: List[CourseRecommendation], 
        context: Dict[str, Any]
    ) -> int:
        """شمارش پیش‌نیازهای پوشش داده شده"""
        
        unmet_prerequisites = set(
            context["academic_history"]["prerequisite_analysis"]["unmet_prerequisites"]
        )
        
        recommended_codes = {rec.course_code for rec in recommendations}
        
        return len(unmet_prerequisites.intersection(recommended_codes))
    
    def _generate_explanation(
        self,
        context: Dict[str, Any],
        recommendations: List[CourseRecommendation],
        schedule: WeeklySchedule
    ) -> Dict[str, Any]:
        """تولید توضیحات پیشنهاد"""
        
        student_profile = context["student_profile"]["basic_info"]
        failed_count = len(context["academic_history"]["failed_courses"]["courses"])
        
        explanation = {
            "strategy_rationale": "",
            "priority_explanation": {},
            "balance_analysis": {},
            "next_steps": []
        }
        
        # توضیح استراتژی
        strategy = context["recommendation_constraints"]["recommendation_strategy"]
        if strategy == "recovery_focused":
            explanation["strategy_rationale"] = f"با توجه به {failed_count} درس مردودی، تمرکز بر جبران دروس است"
        elif strategy == "gpa_improvement":
            explanation["strategy_rationale"] = f"با توجه به معدل {student_profile['current_gpa']}، تمرکز بر بهبود عملکرد است"
        elif strategy == "specialization_focused":
            explanation["strategy_rationale"] = "با توجه به ترم پیشرفته، تمرکز بر تقویت گرایش تخصصی است"
        else:
            explanation["strategy_rationale"] = "استراتژی متعادل برای پیشرفت تحصیلی"
        
        # توضیح اولویت‌ها
        priority_groups = {}
        for rec in recommendations:
            priority_range = self._get_priority_range(rec.priority_score)
            if priority_range not in priority_groups:
                priority_groups[priority_range] = []
            priority_groups[priority_range].append(rec.course_name)
        
        explanation["priority_explanation"] = priority_groups
        
        # تحلیل تعادل
        explanation["balance_analysis"] = {
            "total_credits": schedule.total_credits,
            "balance_score": schedule.balance_score,
            "conflicts_count": len(schedule.conflicts),
            "distribution_quality": "خوب" if schedule.balance_score >= 70 else "قابل بهبود"
        }
        
        # مراحل بعدی
        explanation["next_steps"] = [
            "بررسی جدول زمانی و تأیید عدم تداخل",
            "مطالعه سرفصل دروس پیشنهادی",
            "مشورت با استاد راهنما در صورت نیاز",
            "ثبت‌نام در زمان تعیین شده"
        ]
        
        return explanation
    
    def _get_priority_range(self, score: int) -> str:
        """تعیین دامنه اولویت"""
        if score >= 80:
            return "اولویت بالا"
        elif score >= 60:
            return "اولویت متوسط"
        else:
            return "اولویت پایین"