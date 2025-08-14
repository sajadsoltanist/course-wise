"""
Student domain models for CourseWise.

This module contains all student-related SQLAlchemy models including
Student, StudentGrades, and StudentSpecializations following Clean Architecture.
"""

from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    BigInteger, String, Integer, Boolean, Numeric, 
    ForeignKey, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Student(Base):
    """
    Student model representing university students.
    
    Stores basic student information including Telegram integration,
    academic details, and enrollment information.
    """
    
    __tablename__ = "students"
    
    # Telegram integration
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="Telegram user ID for bot integration"
    )
    
    # Academic information
    student_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="University student number"
    )
    
    major: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Student's major (e.g., مهندسی کامپیوتر)"
    )
    
    entry_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Academic entry year (e.g., 1401, 1402)"
    )
    
    current_semester: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current semester number (1-8)"
    )
    
    # Relationships
    grades: Mapped[List["StudentGrade"]] = relationship(
        "StudentGrade",
        back_populates="student",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    specializations: Mapped[List["StudentSpecialization"]] = relationship(
        "StudentSpecialization",
        back_populates="student",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "current_semester >= 1 AND current_semester <= 8",
            name="check_valid_semester"
        ),
        CheckConstraint(
            "entry_year >= 1390 AND entry_year <= 1410",
            name="check_valid_entry_year"
        ),
        Index("idx_student_telegram_entry", "telegram_user_id", "entry_year"),
        Index("idx_student_major_year", "major", "entry_year"),
    )
    
    def __repr__(self) -> str:
        return f"<Student(id={self.id}, student_number='{self.student_number}', major='{self.major}')>"
    
    @property
    def display_name(self) -> str:
        """Get display name for the student."""
        return self.student_number or f"User_{self.telegram_user_id}"
    
    def get_current_gpa(self) -> Optional[Decimal]:
        """
        Calculate current GPA based on passed courses.
        
        Returns:
            Optional[Decimal]: GPA or None if no grades
        """
        passed_grades = [
            grade for grade in self.grades 
            if grade.status == "passed" and grade.grade is not None
        ]
        
        if not passed_grades:
            return None
            
        total_points = sum(grade.grade for grade in passed_grades)
        return Decimal(str(total_points / len(passed_grades)))
    
    def get_total_credits(self) -> int:
        """
        Get total credits for passed courses.
        
        Returns:
            int: Total credit units
        """
        return sum(
            grade.course.theoretical_credits + grade.course.practical_credits
            for grade in self.grades
            if grade.status == "passed"
        )


class StudentGrade(Base):
    """
    Student grade records for completed courses.
    
    Tracks academic performance, attempt history, and course completion status.
    """
    
    __tablename__ = "student_grades"
    
    # Foreign keys
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to student"
    )
    
    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to course"
    )
    
    # Grade information
    grade: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,
        comment="Numerical grade (0.00 to 20.00)"
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="passed",
        comment="Course completion status"
    )
    
    semester_taken: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Semester when course was taken"
    )
    
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Attempt number for this course"
    )
    
    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="grades",
        lazy="select"
    )
    
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="student_grades",
        lazy="select"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "grade IS NULL OR (grade >= 0.00 AND grade <= 20.00)",
            name="check_valid_grade"
        ),
        CheckConstraint(
            "status IN ('passed', 'failed', 'withdrawn')",
            name="check_valid_status"
        ),
        CheckConstraint(
            "attempt_number >= 1 AND attempt_number <= 5",
            name="check_valid_attempt"
        ),
        CheckConstraint(
            "semester_taken >= 1 AND semester_taken <= 8",
            name="check_valid_semester_taken"
        ),
        UniqueConstraint(
            "student_id", "course_id", "attempt_number",
            name="uq_student_course_attempt"
        ),
        Index("idx_grade_student_status", "student_id", "status"),
        Index("idx_grade_course_semester", "course_id", "semester_taken"),
        Index("idx_grade_status_grade", "status", "grade"),
    )
    
    def __repr__(self) -> str:
        return f"<StudentGrade(student_id={self.student_id}, course_id={self.course_id}, grade={self.grade}, status='{self.status}')>"
    
    @property
    def is_passed(self) -> bool:
        """Check if the grade represents a passing result."""
        return self.status == "passed" and (self.grade is None or self.grade >= 10.0)
    
    @property
    def grade_letter(self) -> str:
        """Convert numerical grade to letter grade."""
        if self.grade is None or self.status != "passed":
            return "N/A"
        
        if self.grade >= 17:
            return "A"
        elif self.grade >= 14:
            return "B"
        elif self.grade >= 10:
            return "C"
        else:
            return "F"


class StudentSpecialization(Base):
    """
    Student specialization selections for elective groups.
    
    Tracks which elective groups students have chosen for their specialization.
    """
    
    __tablename__ = "student_specializations"
    
    # Foreign keys
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to student"
    )
    
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("elective_groups.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to elective group"
    )
    
    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="specializations",
        lazy="select"
    )
    
    elective_group: Mapped["ElectiveGroup"] = relationship(
        "ElectiveGroup",
        back_populates="student_selections",
        lazy="select"
    )
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "student_id", "group_id",
            name="uq_student_group_specialization"
        ),
        Index("idx_specialization_student", "student_id"),
        Index("idx_specialization_group", "group_id"),
    )
    
    def __repr__(self) -> str:
        return f"<StudentSpecialization(student_id={self.student_id}, group_id={self.group_id})>"
