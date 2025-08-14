"""
Elective domain models for CourseWise.

This module contains elective group-related SQLAlchemy models including
ElectiveGroup and GroupCourse following Clean Architecture principles.
"""

from typing import List, Optional
from sqlalchemy import (
    String, Integer, Text, ForeignKey,
    Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ElectiveGroup(Base):
    """
    Elective group model representing specialization areas.
    
    Groups related elective courses together (e.g., AI, Networks, Security)
    and defines how many courses students must select from each group.
    """
    
    __tablename__ = "elective_groups"
    
    # Group identification
    group_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Name of the elective group (e.g., هوش مصنوعی, شبکه‌های کامپیوتری)"
    )
    
    required_courses_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of courses student must select from this group"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the elective group and its focus area"
    )
    
    # Optional: Entry year specific groups
    entry_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Specific entry year this group applies to (optional)"
    )
    
    # Optional: Minimum semester for this group
    min_semester: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum semester when students can select from this group"
    )
    
    # Relationships
    courses: Mapped[List["GroupCourse"]] = relationship(
        "GroupCourse",
        back_populates="elective_group",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    student_selections: Mapped[List["StudentSpecialization"]] = relationship(
        "StudentSpecialization",
        back_populates="elective_group",
        lazy="select",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "required_courses_count >= 1 AND required_courses_count <= 10",
            name="check_valid_required_courses_count"
        ),
        CheckConstraint(
            "entry_year IS NULL OR (entry_year >= 1390 AND entry_year <= 1410)",
            name="check_valid_entry_year"
        ),
        CheckConstraint(
            "min_semester IS NULL OR (min_semester >= 1 AND min_semester <= 8)",
            name="check_valid_min_semester"
        ),
        Index("idx_elective_group_year", "entry_year"),
        Index("idx_elective_group_semester", "min_semester"),
    )
    
    def __repr__(self) -> str:
        return f"<ElectiveGroup(name='{self.group_name}', required_count={self.required_courses_count})>"
    
    @property
    def total_available_courses(self) -> int:
        """Get total number of courses available in this group."""
        return len(self.courses)
    
    def get_course_codes(self) -> List[str]:
        """
        Get list of course codes in this elective group.
        
        Returns:
            List[str]: List of course codes in this group
        """
        return [group_course.course.course_code for group_course in self.courses]
    
    def get_course_names(self) -> List[str]:
        """
        Get list of course names in this elective group.
        
        Returns:
            List[str]: List of course names in this group
        """
        return [group_course.course.course_name for group_course in self.courses]
    
    def is_requirement_satisfied(self, completed_course_codes: List[str]) -> bool:
        """
        Check if student has satisfied the requirement for this group.
        
        Args:
            completed_course_codes: List of completed course codes
            
        Returns:
            bool: True if requirement is satisfied
        """
        group_course_codes = set(self.get_course_codes())
        completed_from_group = set(completed_course_codes).intersection(group_course_codes)
        return len(completed_from_group) >= self.required_courses_count
    
    def get_remaining_requirement(self, completed_course_codes: List[str]) -> int:
        """
        Get number of additional courses needed from this group.
        
        Args:
            completed_course_codes: List of completed course codes
            
        Returns:
            int: Number of additional courses needed (0 if satisfied)
        """
        group_course_codes = set(self.get_course_codes())
        completed_from_group = set(completed_course_codes).intersection(group_course_codes)
        remaining = self.required_courses_count - len(completed_from_group)
        return max(0, remaining)


class GroupCourse(Base):
    """
    Association model between elective groups and courses.
    
    Defines which courses belong to which elective groups.
    A course can belong to multiple groups.
    """
    
    __tablename__ = "group_courses"
    
    # Foreign keys
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("elective_groups.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to elective group"
    )
    
    course_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to course"
    )
    
    # Optional: Priority or order within the group
    priority: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Priority or order of this course within the group"
    )
    
    # Optional: Recommendation level
    recommendation_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Recommendation level: strongly_recommended, recommended, optional"
    )
    
    # Relationships
    elective_group: Mapped["ElectiveGroup"] = relationship(
        "ElectiveGroup",
        back_populates="courses",
        lazy="select"
    )
    
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="group_memberships",
        lazy="select"
    )
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "group_id", "course_id",
            name="uq_group_course"
        ),
        CheckConstraint(
            "priority IS NULL OR priority >= 1",
            name="check_valid_priority"
        ),
        CheckConstraint(
            "recommendation_level IS NULL OR recommendation_level IN ('strongly_recommended', 'recommended', 'optional')",
            name="check_valid_recommendation_level"
        ),
        Index("idx_group_course_group", "group_id"),
        Index("idx_group_course_course", "course_id"),
        Index("idx_group_course_priority", "group_id", "priority"),
        Index("idx_group_course_recommendation", "recommendation_level"),
    )
    
    def __repr__(self) -> str:
        return f"<GroupCourse(group_id={self.group_id}, course_id={self.course_id}, priority={self.priority})>"
    
    @property
    def is_strongly_recommended(self) -> bool:
        """Check if this course is strongly recommended in the group."""
        return self.recommendation_level == "strongly_recommended"
    
    @property
    def is_recommended(self) -> bool:
        """Check if this course is recommended (any level) in the group."""
        return self.recommendation_level in ("strongly_recommended", "recommended")
    
    def get_course_info(self) -> dict:
        """
        Get course information for this group membership.
        
        Returns:
            dict: Course information including group context
        """
        return {
            "course_code": self.course.course_code,
            "course_name": self.course.course_name,
            "total_credits": self.course.total_credits,
            "group_name": self.elective_group.group_name,
            "priority": self.priority,
            "recommendation_level": self.recommendation_level,
            "is_recommended": self.is_recommended
        } 