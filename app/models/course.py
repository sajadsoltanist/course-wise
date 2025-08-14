"""
Course domain models for CourseWise.

This module contains course-related SQLAlchemy models including
Course and CoursePrerequisites following Clean Architecture principles.
"""

from typing import List, Optional, Set
from sqlalchemy import (
    String, Integer, Boolean, Text, ForeignKey, 
    Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Course(Base):
    """
    Course model representing university courses.
    
    Stores course information including credits, prerequisites, 
    and curriculum details for different entry years.
    """
    
    __tablename__ = "courses"
    
    # Course identification
    course_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique course code (e.g., CS101, MATH201)"
    )
    
    course_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Full course name"
    )
    
    # Credit information
    theoretical_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of theoretical credit units"
    )
    
    practical_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of practical/lab credit units"
    )
    
    # Course classification
    course_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Course type: foundation, core, specialized, general"
    )
    
    semester_recommended: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Recommended semester for taking this course (1-8)"
    )
    
    entry_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Academic entry year this course applies to"
    )
    
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this course is mandatory or elective"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Course description and details"
    )
    
    # Relationships
    student_grades: Mapped[List["StudentGrade"]] = relationship(
        "StudentGrade",
        back_populates="course",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Prerequisites (courses that are required before taking this course)
    prerequisites: Mapped[List["CoursePrerequisite"]] = relationship(
        "CoursePrerequisite",
        foreign_keys="CoursePrerequisite.course_id",
        back_populates="course",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Dependent courses (courses that require this course as prerequisite)
    dependent_courses: Mapped[List["CoursePrerequisite"]] = relationship(
        "CoursePrerequisite",
        foreign_keys="CoursePrerequisite.prerequisite_course_id",
        back_populates="prerequisite_course",
        lazy="select"
    )
    
    # Elective group memberships
    group_memberships: Mapped[List["GroupCourse"]] = relationship(
        "GroupCourse",
        back_populates="course",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "theoretical_credits >= 0 AND theoretical_credits <= 6",
            name="check_valid_theoretical_credits"
        ),
        CheckConstraint(
            "practical_credits >= 0 AND practical_credits <= 6",
            name="check_valid_practical_credits"
        ),
        CheckConstraint(
            "theoretical_credits + practical_credits > 0",
            name="check_has_credits"
        ),
        CheckConstraint(
            "semester_recommended IS NULL OR (semester_recommended >= 1 AND semester_recommended <= 8)",
            name="check_valid_recommended_semester"
        ),
        CheckConstraint(
            "entry_year >= 1390 AND entry_year <= 1410",
            name="check_valid_entry_year"
        ),
        CheckConstraint(
            "course_type IN ('foundation', 'core', 'specialized', 'general')",
            name="check_valid_course_type"
        ),
        Index("idx_course_type_year", "course_type", "entry_year"),
        Index("idx_course_semester_year", "semester_recommended", "entry_year"),
        Index("idx_course_mandatory_type", "is_mandatory", "course_type"),
    )
    
    def __repr__(self) -> str:
        return f"<Course(code='{self.course_code}', name='{self.course_name}', credits={self.total_credits})>"
    
    @property
    def total_credits(self) -> int:
        """Get total credit units for this course."""
        return self.theoretical_credits + self.practical_credits
    
    @property
    def is_elective(self) -> bool:
        """Check if this course is elective."""
        return not self.is_mandatory
    
    def get_prerequisite_codes(self) -> List[str]:
        """
        Get list of prerequisite course codes.
        
        Returns:
            List[str]: List of prerequisite course codes
        """
        return [
            prereq.prerequisite_course.course_code 
            for prereq in self.prerequisites
            if not prereq.is_corequisite
        ]
    
    def get_corequisite_codes(self) -> List[str]:
        """
        Get list of corequisite course codes.
        
        Returns:
            List[str]: List of corequisite course codes
        """
        return [
            prereq.prerequisite_course.course_code 
            for prereq in self.prerequisites
            if prereq.is_corequisite
        ]
    
    def check_prerequisites_met(self, completed_courses: Set[str]) -> bool:
        """
        Check if prerequisites are met for this course.
        
        Args:
            completed_courses: Set of completed course codes
            
        Returns:
            bool: True if all prerequisites are met
        """
        prerequisite_codes = set(self.get_prerequisite_codes())
        return prerequisite_codes.issubset(completed_courses)
    
    def get_blocking_courses(self) -> List[str]:
        """
        Get courses that would be blocked if this course is not completed.
        
        Returns:
            List[str]: List of course codes that depend on this course
        """
        return [
            dep.course.course_code 
            for dep in self.dependent_courses
            if not dep.is_corequisite
        ]


class CoursePrerequisite(Base):
    """
    Course prerequisite relationships.
    
    Defines prerequisite and corequisite relationships between courses.
    """
    
    __tablename__ = "course_prerequisites"
    
    # Foreign keys
    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        comment="The course that has prerequisites"
    )
    
    prerequisite_course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        comment="The prerequisite course"
    )
    
    is_corequisite: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this is a corequisite (must be taken together)"
    )
    
    # Relationships
    course: Mapped["Course"] = relationship(
        "Course",
        foreign_keys=[course_id],
        back_populates="prerequisites",
        lazy="select"
    )
    
    prerequisite_course: Mapped["Course"] = relationship(
        "Course",
        foreign_keys=[prerequisite_course_id],
        back_populates="dependent_courses",
        lazy="select"
    )
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "course_id", "prerequisite_course_id",
            name="uq_course_prerequisite"
        ),
        CheckConstraint(
            "course_id != prerequisite_course_id",
            name="check_no_self_prerequisite"
        ),
        Index("idx_prerequisite_course", "course_id"),
        Index("idx_prerequisite_dependency", "prerequisite_course_id"),
        Index("idx_prerequisite_type", "is_corequisite"),
    )
    
    def __repr__(self) -> str:
        prereq_type = "corequisite" if self.is_corequisite else "prerequisite"
        return f"<CoursePrerequisite(course_id={self.course_id}, prerequisite_id={self.prerequisite_course_id}, type='{prereq_type}')>" 