# CourseWise Project - Technical Context & Implementation Guide

## 🎯 Project Overview

**CourseWise** is a Telegram bot for Computer Engineering students at Azad University Shahrekord to receive intelligent course recommendations for upcoming semesters. The system uses LLM integration to analyze academic progress and provide personalized course selection guidance.

### Technology Stack
```python
# Core Framework
python-telegram-bot==21.8.0          # Async Telegram bot library
asyncio                               # Async runtime

# LLM Integration  
openai==1.54.4                       # OpenAI API client
pydantic==2.10.2                     # Data validation
pydantic-settings==2.6.1             # Settings management

# Database & ORM
sqlalchemy==2.0.36                   # Async SQLAlchemy 2.0
asyncpg==0.30.0                      # PostgreSQL async driver
alembic==1.14.0                      # Database migrations

# Configuration & Utils
python-dotenv==1.0.1                 # Environment variables
loguru==0.7.2                        # Advanced logging

# Development
python==3.12+                        # Modern Python with async support
postgresql==15+                      # Database server
```

---

## 🏗️ Project Architecture

### Directory Structure
```
coursewise/
├── app/
│   ├── config.py                    # ✅ Environment configuration
│   ├── core/
│   │   └── database.py              # ✅ Async database setup
│   ├── models/                      # ✅ SQLAlchemy domain models
│   │   ├── __init__.py              # Model exports
│   │   ├── base.py                  # Base model class
│   │   ├── student.py               # Student domain
│   │   ├── course.py                # Course domain  
│   │   └── elective.py              # Elective groups
│   ├── services/                    # 🔄 Business logic
│   │   ├── bot.py                   # Telegram bot service
│   │   ├── llm.py                   # OpenAI integration
│   │   ├── grade_parser.py          # Grade text parsing
│   │   └── recommendation.py        # Course recommendations
│   ├── handlers/                    # 🔄 Bot command handlers
│   │   ├── start.py                 # Registration flow
│   │   ├── grades.py                # Grade input flow
│   │   └── recommend.py             # Recommendation flow
│   └── utils/                       # 🔄 Helper functions
│       ├── session.py               # Session management
│       └── validation.py            # Data validation
├── data/                            # 📄 Static configuration
│   ├── curriculum_rules.md          # Academic rules & regulations
│   ├── curriculum_chart.json        # Course structure by entry year
│   └── offerings/                   # Course offerings per semester
│       ├── spring_1404.json         # Current semester
│       └── fall_1403.json           # Previous semester
├── alembic/                         # ✅ Database migrations
│   ├── env.py                       # Async migration config
│   └── versions/                    # Migration files
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment template
└── main.py                          # Application entry point
```

---

## 🗄️ Database Schema (SQLAlchemy 2.0)

### Implemented Models

All models inherit from `Base` with common fields: `id`, `created_at`, `updated_at`

#### **Core Tables**
1. **students** - Student profiles and Telegram integration
2. **courses** - Complete course catalog with metadata
3. **course_prerequisites** - Prerequisite/corequisite relationships
4. **student_grades** - Academic records with attempt tracking
5. **elective_groups** - Specialization track definitions  
6. **group_courses** - Course-to-specialization associations
7. **student_specializations** - Student specialization selections

#### **Key Features**
- **Async Support**: All models use `AsyncAttrs` for relationship loading
- **Business Methods**: Built-in GPA calculation, prerequisite checking
- **Constraint Validation**: Database-level data integrity
- **Attempt Tracking**: Multiple course attempts supported
- **Clean Architecture**: Domain-driven design principles

#### **Model Relationships**
```python
# One-to-Many
Student → StudentGrade (academic history)
Course → StudentGrade (enrollment tracking)
ElectiveGroup → GroupCourse (specialization structure)

# Many-to-Many  
Course ↔ Course (prerequisites via CoursePrerequisite)
Course ↔ ElectiveGroup (via GroupCourse)
Student ↔ ElectiveGroup (via StudentSpecialization)
```

---

## 📂 Static Data Management

### Academic Rules (`data/curriculum_rules.md`)
**Contains**: Complete course selection regulations extracted from university documents
- GPA requirements and credit limits
- Prerequisite and corequisite rules  
- Specialization requirements (12 credits from single track)
- Final semester regulations and exceptions
- Academic probation and standing rules

**Usage**: Loaded as LLM context for recommendation generation
**Format**: Markdown with structured sections for easy parsing

### Course Offerings (`data/offerings/semester.json`)
**Purpose**: Hardcoded course availability per semester
**Structure**:
```json
{
  "semester": "spring_1404",
  "last_updated": "2024-01-10",
  "offered_courses": [
    {
      "course_code": "CS201",
      "course_name": "ساختمان داده",
      "instructors": ["دکتر احمدی"],
      "time_slots": ["شنبه-دوشنبه 10:00-12:00"],
      "capacity": 30
    }
  ],
  "not_offered": ["CS401", "AI301"],
  "notes": ["دروس آزمایشگاهی نیاز به ثبت‌نام جداگانه"]
}
```

**Update Process**: Manual update at semester start by admin
**Advantage**: No database complexity, fast loading, version controlled

### Curriculum Chart (`data/curriculum_chart.json`)
**Purpose**: Official course sequences and dependencies by entry year
**Content**: Course flow, recommended semesters, credit requirements
**Usage**: Reference for LLM to understand academic progression

---

## 🧠 Session Management

### Memory-Based Sessions
```python
# Session structure (in-memory only)
session_data = {
    "user_id": 123456789,
    "step": "waiting_grades",              # Current interaction state
    "started_at": datetime,
    "last_activity": datetime,
    
    # Temporary data (cleared after confirmation)
    "temp_grades_text": "CS101: 18, Math: 17...",
    "parsed_grades": [...],                # LLM parsing results
    "recommendation_prefs": {
        "desired_credits": "16-18",
        "priorities": ["catch_up"]
    }
}
```

### Session Lifecycle
- **Creation**: User starts `/start` or new interaction
- **Timeout**: 30 minutes of inactivity
- **Cleanup**: Automatic garbage collection
- **Persistence**: Only confirmed data moves to database

### State Management
- **Simple Flow**: Registration → Grades → Recommendation
- **Error Recovery**: Graceful handling of invalid inputs
- **User Control**: Allow restart at any step

---

## 🤖 LLM Integration Strategy

### OpenAI API Configuration
```python
# Using OpenAI's GPT models
client = OpenAI(api_key=settings.OPENAI_API_KEY)
model = "gpt-4o"  # Cost-effective for production
```

### Two Primary LLM Use Cases

#### **1. Grade Text Parsing**
**Input**: Raw text from user (e.g., "Math1: 17, CS101: 18, Physics: failed")
**Context**: Valid course codes from database
**Output**: Structured JSON with course mappings
**Validation**: Against course database for accuracy

#### **2. Course Recommendation** 
**Input**: Complete academic context
**Context Assembly**:
```python
context = {
    # From Database
    "student_profile": get_student_data(student_id),
    "academic_history": get_grades_with_courses(student_id),
    
    # From Static Files
    "curriculum_rules": load_file("data/curriculum_rules.md"),
    "course_offerings": load_file(f"data/offerings/{semester}.json"),
    "curriculum_chart": load_file("data/curriculum_chart.json"),
    
    # From Session
    "user_preferences": session["recommendation_prefs"],
    "target_semester": semester
}
```
**Output**: Recommended courses with detailed explanations

### Error Handling
- **LLM Failures**: Fallback to rule-based recommendations
- **Parse Errors**: Request user clarification
- **Context Issues**: Graceful degradation with partial data

---

## 💾 Data Flow Principles

### What Gets Stored Where

#### **Database (Permanent)**
✅ **Store**:
- Student profiles (telegram_user_id, student_number, major, etc.)
- Confirmed academic grades and course history
- Specialization selections
- Course catalog and prerequisites

❌ **Don't Store**:
- Session states and temporary data
- Raw LLM prompts/responses
- Unconfirmed grade parsing results
- User preferences for individual sessions

#### **Memory (Temporary)**
✅ **Session Data**:
- Current interaction state
- Pending grade confirmations  
- User preferences for current recommendation
- Temporary files/uploads

🔄 **Cleared When**:
- User confirms data (moves to database)
- Session timeout (30 minutes)
- Error recovery or restart

#### **Files (Static)**
📄 **Configuration**:
- Academic rules and regulations
- Course availability by semester
- Curriculum structure by entry year

---

## 🔧 Implementation Guidelines

### Bot Flow Implementation
1. **Registration**: Collect basic student info → Save to database
2. **Grade Input**: Text parsing → LLM validation → User confirmation → Database
3. **Recommendation**: Context assembly → LLM analysis → User interaction

### Database Operations
- **Async Everywhere**: All database operations use async/await
- **Transaction Safety**: Critical operations wrapped in transactions
- **Error Handling**: Proper exception handling and rollback
- **Connection Pooling**: Efficient resource management

### LLM Best Practices
- **Structured Prompts**: Clear format expectations
- **Context Limitation**: Keep context under token limits
- **Retry Logic**: Handle API failures gracefully
- **Cost Optimization**: Use appropriate model for each task

### Session Management
- **Memory Efficiency**: Clean up expired sessions automatically
- **State Validation**: Verify session state before operations
- **Concurrent Users**: Support multiple simultaneous users
- **Error Recovery**: Allow users to restart from any point

---

## 🚀 Development Workflow

### Environment Setup
```bash
# Python environment
python -m venv coursewise
source coursewise/bin/activate  # Linux/Mac
# coursewise\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
# Edit .env with your credentials:
# - DATABASE_URL
# - TELEGRAM_BOT_TOKEN  
# - OPENAI_API_KEY

# Database setup
alembic upgrade head

# Run development server
python main.py
```

### Configuration Management
```python
# app/config.py
class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    openai_api_key: str
    log_level: str = "INFO"
    session_timeout_minutes: int = 30
    
    class Config:
        env_file = ".env"
```

---

## 🎯 Production Considerations

### Performance Optimization
- **Database Indexing**: Optimize queries with proper indexes
- **LLM Caching**: Cache common responses when appropriate
- **Session Cleanup**: Regular cleanup of expired sessions
- **Connection Pooling**: Efficient database connection management

### Monitoring & Logging
- **Structured Logging**: Use loguru for comprehensive logging
- **Error Tracking**: Monitor LLM failures and database errors
- **User Analytics**: Track bot usage patterns (privacy-compliant)
- **Performance Metrics**: Monitor response times and success rates

### Security & Privacy
- **Environment Variables**: No hardcoded secrets
- **Data Encryption**: Secure sensitive student information
- **Input Validation**: Validate all user inputs
- **Access Control**: Restrict admin functions appropriately

### Scalability
- **Stateless Design**: Sessions can be distributed across instances
- **Database Optimization**: Proper indexing and query optimization
- **File Caching**: Static data cached in memory
- **Horizontal Scaling**: Easy to add more bot instances

This technical context provides a comprehensive foundation for implementing and maintaining the CourseWise bot while ensuring code quality, performance, and maintainability.