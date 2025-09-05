# CourseWise Bot - Complete Technical Context

## 🎯 Project Overview

**CourseWise** is a Telegram bot designed to help Computer Engineering students at Azad University Shahrekord select optimal courses for upcoming semesters. The system analyzes students' academic progress, grades, and curriculum requirements to provide intelligent course recommendations using LLM integration.

### Core Objectives
- **Simplify Course Selection**: Help students make informed academic decisions
- **Prevent Academic Issues**: Avoid probation, credit limit violations, and prerequisite conflicts
- **Intelligent Recommendations**: LLM-powered analysis of academic standing and requirements
- **User-Friendly Interface**: Simple Telegram bot interaction

---

## 🤖 Bot Flow Architecture

### **Phase 1: Registration & Authentication**
```
User: /start
Bot: "Welcome! Please provide your student number:"
User: "98123456789"
Bot: "Major and current semester?"
User: "Computer Engineering - Semester 4"

💾 Database: Save basic student info to `students` table
🧠 Session: Store temporary registration data
```

### **Phase 2: Academic History Input**
```
Bot: "Enter your grades in this format: Math1: 17, CS101: 18, Physics: failed, ..."
User: [Grade text input]

🤖 LLM: Parse text → Structured JSON grades
Bot: "I detected these grades... Is this correct? ✅❌"
User: ✅ Confirm

💾 Database: Save to `student_grades` table with course foreign keys
🧠 Session: Clear temporary data after confirmation
```

### **Phase 3: Course Recommendation**
```
Bot: "How many credits do you want? What are your priorities?"
User: "16-18 credits, focus on catching up with failed courses"

🤖 LLM Context Assembly:
- Student profile from database
- Academic history from database  
- Curriculum rules from static files
- Course offerings from semester JSON file
- User preferences from session

🤖 LLM: Generate intelligent course recommendation
Bot: "My recommendation: CS201, MATH301, ..."
User: ✅ Accept or ⚙️ Customize

🧠 Session: Store final recommendation (optional)
```

---

## 🗄️ Database Schema

### **Core Tables Structure**

#### **1. students**
```sql
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    student_number VARCHAR(20) UNIQUE,
    major VARCHAR(100),                    -- Computer Engineering, etc.
    entry_year INTEGER,                    -- 1403, 1402, etc.
    current_semester INTEGER,              -- 1-8
    specialization VARCHAR(50),            -- AI, Networks, etc. (for semester 6+)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### **2. courses**
```sql
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) UNIQUE NOT NULL,     -- CS101, MATH201
    course_name VARCHAR(200) NOT NULL,           -- "Data Structures"
    course_name_fa VARCHAR(200),                 -- "ساختمان داده"
    theoretical_credits INTEGER NOT NULL,        -- Theory units
    practical_credits INTEGER DEFAULT 0,         -- Lab units
    total_credits INTEGER GENERATED ALWAYS AS (theoretical_credits + practical_credits) STORED,
    course_type VARCHAR(50) NOT NULL,            -- 'foundation', 'core', 'specialized', 'general'
    semester_recommended INTEGER,                -- Recommended semester (1-8)
    is_mandatory BOOLEAN DEFAULT TRUE,           -- Mandatory/elective
    description TEXT,                            -- Course description
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### **3. course_prerequisites**
```sql
CREATE TABLE course_prerequisites (
    id SERIAL PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    is_corequisite BOOLEAN DEFAULT FALSE,        -- Co-requisite vs prerequisite
    minimum_grade DECIMAL(4,2) DEFAULT 10.0,     -- Minimum grade required
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(course_id, prerequisite_course_id)
);
```

#### **4. student_grades**
```sql
CREATE TABLE student_grades (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
    grade DECIMAL(4,2),                          -- 0.00 to 20.00 (NULL for failed)
    status VARCHAR(20) NOT NULL,                 -- 'passed', 'failed', 'withdrawn'
    semester_taken INTEGER,                      -- Semester when taken
    attempt_number INTEGER DEFAULT 1,           -- Attempt number (for retakes)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_grade_range CHECK (grade IS NULL OR (grade >= 0 AND grade <= 20)),
    CONSTRAINT chk_status CHECK (status IN ('passed', 'failed', 'withdrawn')),
    UNIQUE(student_id, course_id, attempt_number)
);
```

#### **5. elective_groups** (Optional - for specialization tracking)
```sql
CREATE TABLE elective_groups (
    id SERIAL PRIMARY KEY,
    group_name VARCHAR(100),                     -- 'artificial_intelligence', 'networks'
    group_name_fa VARCHAR(100),                  -- 'هوش مصنوعی', 'شبکه‌های کامپیوتری'
    required_courses_count INTEGER,              -- How many courses required
    description TEXT
);
```

### **Current SQLAlchemy Models (Already Implemented)**

The project already has well-designed SQLAlchemy 2.0 models with proper relationships:

#### **Base Model Structure**
- **Common Fields**: All models inherit `id`, `created_at`, `updated_at` from `Base` class
- **AsyncAttrs**: Async relationship loading support
- **Utility Methods**: `to_dict()`, `update_from_dict()` for data conversion
- **Proper Constraints**: Check constraints, unique constraints, and indexes

#### **Model Relationships**
- **Student ↔ StudentGrade**: One-to-many relationship for academic records
- **Course ↔ StudentGrade**: One-to-many for course enrollment tracking  
- **Course ↔ CoursePrerequisite**: Self-referencing for prerequisite chains
- **ElectiveGroup ↔ GroupCourse ↔ Course**: Many-to-many for specialization tracks
- **Student ↔ StudentSpecialization ↔ ElectiveGroup**: Specialization selection tracking

#### **Advanced Features Already Implemented**
- **Attempt Tracking**: Multiple attempts per course with `attempt_number`
- **Grade Validation**: Numeric grade constraints (0.00-20.00)
- **Status Tracking**: 'passed', 'failed', 'withdrawn' status management
- **Specialization Support**: Complete elective group and course association
- **Academic Integrity**: Proper foreign key cascades and constraints

### **Database Design Notes**
- **Production Ready**: Current models are well-architected and ready for production use
- **Flexible Structure**: Can be extended with additional fields as needed
- **Referential Integrity**: Foreign keys ensure data consistency
- **Performance Optimized**: Proper indexes for common queries
- **Support for Retakes**: Multiple attempts per course tracked
- **Clean Architecture**: Models follow domain-driven design principles

---

## 📂 Static Data Files

### **Curriculum Rules** (`data/curriculum_rules.md`)
- **Purpose**: Contains all academic regulations and course selection rules
- **Content**: GPA requirements, credit limits, prerequisite rules, graduation requirements
- **Usage**: Read by LLM as context for generating recommendations
- **Update Frequency**: Annually or when university regulations change

### **Course Offerings** (`data/offerings/`)
- **Structure**: 
  ```
  data/offerings/
  ├── spring_1404.json    # Current semester offerings
  ├── fall_1403.json      # Previous semester
  └── summer_1404.json    # Summer session
  ```
- **Content**: Hardcoded list of courses offered each semester with instructor, time slots, capacity
- **Usage**: LLM uses this to filter available courses for recommendations
- **Update Process**: Manual update at beginning of each semester

### **Curriculum Chart** (`data/curriculum_chart.json`)
- **Purpose**: Official curriculum structure for different entry years
- **Content**: Course sequences, recommended semesters, specialization tracks
- **Usage**: Reference for LLM to understand course flow and dependencies
- **Format**: JSON structure with course mappings and semester recommendations

---

## 🧠 Session Management

### **Session Data Structure**
```python
session_data = {
    "user_id": 123456789,
    "step": "current_step",                    # State tracking
    "started_at": "2024-01-15T10:30:00Z",
    "last_activity": "2024-01-15T10:35:00Z",
    
    # Temporary data (cleared after confirmation)
    "temp_grades_text": "Math1: 17, CS101: 18...",
    "parsed_grades": [...],                    # LLM parsed results
    "recommendation_preferences": {
        "desired_credits": "16-18",
        "priorities": ["catch_up", "prerequisites"]
    },
    
    # Current recommendation (optional storage)
    "current_recommendation": {
        "courses": [...],
        "total_credits": 18,
        "warnings": [...]
    }
}
```

### **Session Lifecycle**
- **Creation**: When user starts interaction
- **Duration**: 30 minutes of inactivity timeout
- **Cleanup**: Automatic cleanup of expired sessions
- **Persistence**: Only essential data saved to database after user confirmation

---

## 🤖 LLM Integration Architecture

### **Context Assembly Process**
```python
def prepare_llm_context(student_id, semester, user_preferences):
    context = {
        # From Database
        "student_profile": get_student_from_db(student_id),
        "academic_history": get_student_grades_with_courses(student_id),
        
        # From Static Files  
        "curriculum_rules": load_file("data/curriculum_rules.md"),
        "course_offerings": load_file(f"data/offerings/{semester}.json"),
        "curriculum_chart": load_file("data/curriculum_chart.json"),
        
        # From Session
        "user_preferences": user_preferences,
        "target_semester": semester
    }
    return context
```

### **LLM Usage Points**

#### **1. Grade Parsing**
- **Input**: Raw text from user
- **Context**: List of valid course codes from database
- **Output**: Structured JSON with course_code, grade, status
- **Validation**: Against course database for accuracy

#### **2. Course Recommendation**
- **Input**: Complete academic context
- **Context**: Student data + rules + offerings + preferences
- **Output**: Recommended courses with explanations
- **Processing**: Complex analysis of prerequisites, GPA, credit limits, etc.

### **LLM Prompting Strategy**
- **Structured Prompts**: Clear format expectations for consistent outputs
- **Context Injection**: Dynamic loading of relevant data files
- **Validation Loops**: Multiple validation steps for critical data
- **Error Handling**: Fallback strategies when LLM fails

---

## 💾 Data Flow Management

### **Persistent Storage (Database)**
```
✅ Store permanently:
- Student profiles and basic information
- Confirmed academic grades and history
- Course catalog and prerequisites
- Final course selections (optional)

❌ Don't store:
- Session states and temporary data
- Raw LLM responses and prompts  
- User preferences for individual sessions
- Temporary file uploads
```

### **Session Storage (Memory)**
```
✅ Store temporarily:
- Current interaction state
- Unconfirmed grade parsing results
- User preferences for current session
- LLM responses awaiting confirmation

🔄 Clear when:
- User confirms data (move to DB)
- Session timeout (30 minutes)
- User starts new session
- Error recovery needed
```

### **File-Based Storage (Static)**
```
📄 Configuration files:
- Academic rules and regulations
- Curriculum charts and requirements
- Course offerings per semester
- System configuration

🔄 Update process:
- Manual updates by administrators
- Version controlled through Git
- Validated before deployment
```

---

## 🔧 Technical Implementation Notes

### **Database Flexibility**
- **Schema Evolution**: Tables can be extended with additional fields
- **Index Optimization**: Add indexes based on query patterns
- **Constraint Adjustments**: Modify validation rules as requirements change
- **Migration Support**: Alembic migrations for schema changes

### **LLM Context Optimization**
- **Selective Loading**: Only load relevant data for current operation
- **Context Compression**: Summarize large datasets when needed
- **Caching Strategy**: Cache frequently accessed static data
- **Error Recovery**: Graceful degradation when context is incomplete

### **Session Scalability**
- **Memory Management**: Automatic cleanup of expired sessions
- **State Persistence**: Option to persist critical session data
- **Concurrent Users**: Support for multiple simultaneous users
- **Resource Limits**: Prevent memory exhaustion from session accumulation

### **File Management**
- **Version Control**: Track changes to curriculum and rules
- **Validation**: Ensure file format correctness before use
- **Fallback Data**: Maintain backup data for system reliability
- **Hot Reloading**: Update static data without system restart

---

## 🎯 System Architecture Principles

### **Separation of Concerns**
- **Database**: Persistent student and course data
- **Files**: Static configuration and rules
- **Sessions**: Temporary interaction state
- **LLM**: Intelligence and analysis layer

### **Data Consistency**
- **Single Source of Truth**: Each data type has one authoritative source
- **Referential Integrity**: Database foreign keys ensure consistency
- **Validation Layers**: Multiple validation points prevent bad data
- **Atomic Operations**: Transactions ensure data integrity

### **Scalability Considerations**
- **Stateless Design**: Sessions are independent and can be distributed
- **Database Optimization**: Proper indexing and query optimization
- **File Caching**: Static data cached in memory for performance
- **Modular Architecture**: Easy to scale individual components

### **Maintainability**
- **Clear Data Flow**: Easy to understand data movement
- **Configuration Management**: Centralized configuration files
- **Error Handling**: Comprehensive error recovery strategies
- **Documentation**: Self-documenting code and clear interfaces

This architecture provides a robust foundation for the CourseWise bot while maintaining flexibility for future enhancements and scaling requirements.