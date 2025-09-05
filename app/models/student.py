"""
Simplified Student model for CourseWise.

Contains only essential student information for LLM-based recommendations.
"""

from typing import Optional
from sqlalchemy import BigInteger, String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Student(Base):
    """
    Simplified Student model for LLM-based course recommendations.
    
    Stores only essential information:
    - Telegram integration (telegram_user_id)  
    - Academic identity (student_number)
    - Curriculum context (entry_year)
    - Current progress (current_semester)
    """
    
    __tablename__ = "students"
    
    # Telegram integration - primary identifier
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="Telegram user ID for bot integration"
    )
    
    # University identity
    student_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="University student number"
    )
    
    # Curriculum context - determines which curriculum chart to use
    entry_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Entry year (1401, 1402, 1403, etc.) - determines curriculum"
    )
    
    # Academic progress
    current_semester: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current semester number (1-8+)"
    )
    
    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the student account is active"
    )
    
    def __repr__(self) -> str:
        return f"<Student(telegram_id={self.telegram_user_id}, student_number={self.student_number}, entry_year={self.entry_year})>"
    
    @property
    def curriculum_type(self) -> str:
        """Determine which curriculum chart to use based on entry year"""
        if self.entry_year and self.entry_year >= 1403:
            return "1403_onwards" 
        else:
            return "before_1403"