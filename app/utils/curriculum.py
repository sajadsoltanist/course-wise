"""
Curriculum data utilities for CourseWise.

This module provides functions to load and work with curriculum data
from JSON files organized by entry year.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger


class CurriculumManager:
    """
    Manager class for handling curriculum data from JSON files.
    
    Supports different entry years and provides course lookup functionality.
    """
    
    def __init__(self, data_dir: str = "data/curriculum"):
        """
        Initialize curriculum manager.
        
        Args:
            data_dir: Directory containing curriculum JSON files
        """
        self.data_dir = Path(data_dir)
        self._curricula: Dict[int, Dict[str, Any]] = {}
        self._course_mappings: Dict[int, Dict[str, Dict[str, Any]]] = {}
        
    def load_curriculum(self, entry_year: int) -> Optional[Dict[str, Any]]:
        """
        Load curriculum data for a specific entry year.
        
        Args:
            entry_year: The entry year (e.g., 1403, 1393)
            
        Returns:
            Curriculum data dictionary or None if not found
        """
        if entry_year in self._curricula:
            return self._curricula[entry_year]
            
        file_path = self.data_dir / f"entry_{entry_year}.json"
        
        if not file_path.exists():
            logger.warning(f"Curriculum file not found: {file_path}")
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                curriculum_data = json.load(f)
                
            self._curricula[entry_year] = curriculum_data
            self._build_course_mapping(entry_year, curriculum_data)
            
            logger.info(f"Loaded curriculum for entry year {entry_year}")
            return curriculum_data
            
        except Exception as e:
            logger.error(f"Error loading curriculum for {entry_year}: {e}")
            return None
    
    def _build_course_mapping(self, entry_year: int, curriculum_data: Dict[str, Any]) -> None:
        """
        Build a flat course mapping from curriculum data for fast lookup.
        
        Args:
            entry_year: Entry year
            curriculum_data: Curriculum data dictionary
        """
        course_mapping = {}
        
        # Add courses from semesters
        for semester_data in curriculum_data.get("semesters", {}).values():
            for course in semester_data.get("courses", []):
                course_code = course["course_code"]
                course_mapping[course_code] = {
                    "course_name": course["course_name"],
                    "theoretical_credits": course["theoretical_credits"],
                    "practical_credits": course["practical_credits"],
                    "course_type": course["course_type"],
                    "is_mandatory": course["is_mandatory"],
                    "prerequisites": course["prerequisites"],
                    "semester_recommended": semester_data["semester"]
                }
        
        # Add elective courses
        for group_type, groups in curriculum_data.get("elective_groups", {}).items():
            for group in groups:
                for course in group.get("courses", []):
                    course_code = course["course_code"]
                    if course_code not in course_mapping:  # Don't override semester courses
                        course_mapping[course_code] = {
                            "course_name": course["course_name"],
                            "theoretical_credits": course["credits"]["theoretical"],
                            "practical_credits": course["credits"]["practical"],
                            "course_type": "specialized" if group_type == "specialized" else "general",
                            "is_mandatory": False,
                            "prerequisites": [],
                            "semester_recommended": None,
                            "elective_group": group["group_name"]
                        }
        
        self._course_mappings[entry_year] = course_mapping
        logger.debug(f"Built course mapping for {entry_year}: {len(course_mapping)} courses")
    
    def get_course_info(self, course_code: str, entry_year: int) -> Optional[Dict[str, Any]]:
        """
        Get course information by course code and entry year.
        
        Args:
            course_code: Course code (e.g., "MATH101", "CS201")
            entry_year: Student's entry year
            
        Returns:
            Course information dictionary or None if not found
        """
        if entry_year not in self._course_mappings:
            if not self.load_curriculum(entry_year):
                # Try to find the closest available curriculum
                fallback_year = self._find_closest_curriculum(entry_year)
                if fallback_year and self.load_curriculum(fallback_year):
                    logger.info(f"Using curriculum {fallback_year} as fallback for entry year {entry_year}")
                    entry_year = fallback_year
                else:
                    return None
                
        course_mapping = self._course_mappings[entry_year]
        return course_mapping.get(course_code)
    
    def _find_closest_curriculum(self, entry_year: int) -> Optional[int]:
        """
        Find the closest available curriculum year.
        
        Args:
            entry_year: Target entry year
            
        Returns:
            Closest available entry year or None
        """
        # Check what curriculum files we have
        available_years = []
        for file_path in self.data_dir.glob("entry_*.json"):
            try:
                year = int(file_path.stem.split("_")[1])
                available_years.append(year)
            except (ValueError, IndexError):
                continue
        
        if not available_years:
            return None
            
        # Find the closest year
        available_years.sort()
        closest_year = min(available_years, key=lambda x: abs(x - entry_year))
        
        logger.debug(f"Available curricula: {available_years}, closest to {entry_year}: {closest_year}")
        return closest_year
    
    def find_course_by_name(self, course_name: str, entry_year: int) -> Optional[Dict[str, Any]]:
        """
        Find course by name (fuzzy matching).
        
        Args:
            course_name: Persian or English course name
            entry_year: Student's entry year
            
        Returns:
            Course information with course_code or None if not found
        """
        if entry_year not in self._course_mappings:
            if not self.load_curriculum(entry_year):
                return None
                
        course_mapping = self._course_mappings[entry_year]
        
        # Normalize input for comparison
        normalized_input = course_name.strip().replace('_', ' ').replace('-', ' ').lower()
        
        # Try exact match first
        for course_code, course_info in course_mapping.items():
            course_name_normalized = course_info["course_name"].replace('_', ' ').replace('-', ' ').lower()
            if normalized_input == course_name_normalized:
                result = course_info.copy()
                result["course_code"] = course_code
                return result
        
        # Try partial match
        for course_code, course_info in course_mapping.items():
            course_name_normalized = course_info["course_name"].replace('_', ' ').replace('-', ' ').lower()
            if normalized_input in course_name_normalized or course_name_normalized in normalized_input:
                result = course_info.copy()
                result["course_code"] = course_code
                return result
                
        return None
    
    def get_available_courses(self, entry_year: int, semester: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get list of available courses for an entry year and optional semester.
        
        Args:
            entry_year: Student's entry year
            semester: Optional semester filter
            
        Returns:
            List of course dictionaries with course_code included
        """
        if entry_year not in self._course_mappings:
            if not self.load_curriculum(entry_year):
                return []
                
        course_mapping = self._course_mappings[entry_year]
        courses = []
        
        for course_code, course_info in course_mapping.items():
            if semester is None or course_info.get("semester_recommended") == semester:
                result = course_info.copy()
                result["course_code"] = course_code
                courses.append(result)
                
        return courses
    
    def get_graduation_requirements(self, entry_year: int) -> Optional[Dict[str, Any]]:
        """
        Get graduation requirements for an entry year.
        
        Args:
            entry_year: Student's entry year
            
        Returns:
            Graduation requirements dictionary or None
        """
        curriculum = self.load_curriculum(entry_year)
        if curriculum:
            return curriculum.get("graduation_requirements")
        return None
    
    def validate_prerequisites(self, course_code: str, completed_courses: List[str], entry_year: int) -> bool:
        """
        Check if a student has completed prerequisites for a course.
        
        Args:
            course_code: Target course code
            completed_courses: List of completed course codes
            entry_year: Student's entry year
            
        Returns:
            True if prerequisites are met, False otherwise
        """
        course_info = self.get_course_info(course_code, entry_year)
        if not course_info:
            return False
            
        prerequisites = course_info.get("prerequisites", [])
        return all(prereq in completed_courses for prereq in prerequisites)


# Global instance for easy access
curriculum_manager = CurriculumManager()


def get_course_info_by_code_or_name(identifier: str, entry_year: int) -> Optional[Dict[str, Any]]:
    """
    Get course info by code or name (convenience function).
    
    Args:
        identifier: Course code or course name
        entry_year: Student's entry year
        
    Returns:
        Course information dictionary or None
    """
    # Try as course code first
    course_info = curriculum_manager.get_course_info(identifier, entry_year)
    if course_info:
        course_info["course_code"] = identifier
        return course_info
    
    # Try as course name
    return curriculum_manager.find_course_by_name(identifier, entry_year)


def get_course_code_by_name(course_name: str) -> Optional[str]:
    """
    Get course code by name using name mappings.
    
    Args:
        course_name: Persian course name
        
    Returns:
        Course code or None if not found
    """
    mappings_file = Path("data/course_name_mappings.json")
    if not mappings_file.exists():
        return None
        
    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            mappings = data.get("course_name_mappings", {})
            
        # Direct match
        if course_name in mappings:
            return mappings[course_name]
            
        # Fuzzy match with priority (exact substring match first)
        course_name_clean = course_name.strip()
        
        # First try exact substring matches
        for mapping_name, code in mappings.items():
            if course_name_clean == mapping_name:
                return code
        
        # Then try partial matches, but prefer longer matches
        best_match = None
        best_length = 0
        for mapping_name, code in mappings.items():
            if mapping_name in course_name_clean:
                if len(mapping_name) > best_length:
                    best_match = code
                    best_length = len(mapping_name)
        
        if best_match:
            return best_match
            
        # Finally try reverse matches (course name contains mapping)
        for mapping_name, code in mappings.items():
            if course_name_clean in mapping_name:
                return code
                
        return None
        
    except Exception as e:
        logger.error(f"Error loading course name mappings: {e}")
        return None


def load_all_curricula() -> None:
    """Load all available curriculum files."""
    data_dir = Path("data/curriculum")
    if not data_dir.exists():
        logger.warning(f"Curriculum directory not found: {data_dir}")
        return
    
    for file_path in data_dir.glob("entry_*.json"):
        try:
            entry_year = int(file_path.stem.split("_")[1])
            curriculum_manager.load_curriculum(entry_year)
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid curriculum filename: {file_path} - {e}")