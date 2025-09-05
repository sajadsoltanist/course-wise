# CourseWise Project Memory

## 🎯 Project Identity & Context

**Project Name**: CourseWise - Telegram Bot for University Course Selection  
**Domain**: Iranian University System (Azad University Shahrekord)  
**Target Users**: Computer Engineering Students  
**Core Purpose**: LLM-powered academic course recommendations and intelligent course selection guidance

### Mission Statement
Help Computer Engineering students make optimal course selections by analyzing their academic progress, grades, and curriculum requirements through intelligent LLM integration, preventing academic issues and ensuring graduation requirements are met.

---

## 🏗️ Technical Stack & Versions

### Core Framework
```python
python==3.12+                        # Modern Python with full async support
python-telegram-bot==21.8.0          # Async Telegram bot library
asyncio                               # Async runtime foundation
```

### LLM & AI Integration
```python
openai==1.54.4                       # OpenAI API client for GPT models
pydantic==2.10.2                     # Data validation and serialization
pydantic-settings==2.6.1             # Environment-based configuration
```

### Database & ORM
```python
sqlalchemy==2.0.36                   # Async SQLAlchemy 2.0 with modern patterns
asyncpg==0.30.0                      # PostgreSQL async driver (mandatory)
alembic==1.14.0                      # Database migrations with async support
postgresql==15+                      # Database server (production requirement)
```

### Configuration & Utilities
```python
python-dotenv==1.0.1                 # Environment variable management
loguru==0.7.2                        # Advanced structured logging
```

### Architecture Rationale
- **Async-First Design**: All operations use async/await for scalability
- **Modern Python**: 3.12+ required for performance and async improvements
- **Production-Grade**: Technology choices support real-world deployment

---

## 🏛️ Clean Architecture Implementation

### Layer Structure
```
CourseWise/
├── Models Layer (Domain)         # ✅ COMPLETE
│   ├── Student entities
│   ├── Course entities  
│   ├── Grade tracking
│   └── Specialization management
├── Services Layer (Application)  # 🔄 NEEDS IMPLEMENTATION
│   ├── LLM integration
│   ├── Grade parsing
│   ├── Recommendation engine
│   └── Session management
├── Handlers Layer (Interface)    # 🔄 NEEDS IMPLEMENTATION
│   ├── Telegram command handlers
│   ├── Conversation flows
│   └── User interaction logic
└── Infrastructure Layer          # ✅ COMPLETE
    ├── Database connections
    ├── Configuration management
    └── External API clients
```

### Design Principles
1. **Separation of Concerns**: Each layer has distinct responsibilities
2. **Dependency Inversion**: High-level modules don't depend on low-level details
3. **Async Throughout**: Consistent async patterns across all layers
4. **Domain-Driven Design**: Models reflect real university domain concepts

---

## 📊 Current Implementation Status

### ✅ **COMPLETED COMPONENTS** (Production Ready)

#### **1. Database Models Layer** (`app/models/`)
**Status**: Professional-grade, production-ready SQLAlchemy 2.0 implementation

**Models Implemented**:
- **`Student`** (`student.py:19-133`): Telegram integration + academic profile tracking
- **`StudentGrade`** (`student.py:135-248`): Grade records with attempt tracking
- **`Course`** (`course.py:18-219`): Complete course catalog with business methods
- **`CoursePrerequisite`** (`course.py:221-284`): Complex prerequisite relationships
- **`ElectiveGroup`** (`elective.py:18-151`): Specialization area definitions
- **`GroupCourse`** (`elective.py:153-253`): Course-to-specialization associations
- **`StudentSpecialization`** (`student.py:250-299`): Student track selections

**Models Required**:
- **`UserSession`** (🔄 Needs Implementation): Database-based session storage with JSONB field

**Advanced Features**:
- **AsyncAttrs**: Async relationship loading throughout
- **Business Methods**: Built-in GPA calculation, prerequisite checking
- **Data Integrity**: Comprehensive constraints and validation
- **Attempt Tracking**: Support for course retakes and multiple attempts
- **Flexible Design**: Entry year support for curriculum changes

#### **2. Infrastructure Layer** (`app/core/`, `app/config.py`)
**Status**: Production-grade async infrastructure

**Database Infrastructure** (`app/core/database.py`):
- **Async Engine**: SQLAlchemy 2.0 with asyncpg driver
- **Connection Pooling**: Configurable pool settings for production
- **Health Checks**: Database connectivity monitoring
- **Session Management**: Proper commit/rollback with context managers
- **Resource Cleanup**: Graceful connection disposal

**Configuration Management** (`app/config.py`):
- **Pydantic Validation**: Type-safe environment variable loading
- **Security Checks**: API key format validation
- **Database URL Validation**: Ensures PostgreSQL+asyncpg usage
- **Pool Configuration**: Production-ready connection pool settings

#### **3. Migration System** (`alembic/`)
**Status**: Ready for database deployment

**Alembic Configuration**:
- **Async Support**: Full async migration capabilities
- **Model Integration**: Automatic metadata import from models
- **Environment Integration**: Uses project configuration system
- **Production Ready**: Proper datetime naming and logging

### 🔄 **MISSING COMPONENTS** (Requires Implementation)

#### **1. Bot Handlers** (`app/handlers/` - Empty Directory)
**Required Implementation**:
- **Registration Handler**: Student profile creation and Telegram integration
- **Grade Input Handler**: Text parsing and confirmation workflow
- **Recommendation Handler**: Course suggestion and interaction logic
- **Command Routing**: `/start`, `/grades`, `/recommend` command processing

#### **2. LLM Services** (`app/services/llm.py` - Placeholder File)
**Required Implementation**:
- **Grade Parsing Service**: Raw text → structured JSON conversion
- **Context Assembly**: Student data + rules + offerings integration
- **Recommendation Engine**: LLM-powered course suggestions
- **Error Handling**: Fallback strategies for LLM failures

#### **3. Session Management** (Not Implemented)
**Required Implementation**:
- **Database Session Store**: PostgreSQL table with JSONB field for session data
- **UserSession Model**: SQLAlchemy model for persistent session storage
- **State Management**: Registration → Grades → Recommendation flow
- **Cleanup Logic**: Automatic expired session removal via database queries
- **Multi-Instance Support**: Database-based sessions support multiple bot instances

#### **4. Static Data Files** (`data/` - Empty Directory)
**Required Files**:
- **Curriculum Rules** (`data/curriculum_rules.md`): Academic regulations for LLM context
- **Course Offerings** (`data/offerings/semester.json`): Available courses per semester
- **Curriculum Chart** (`data/curriculum_chart.json`): Official course sequences

#### **5. Application Entry Point** (`app/main.py` - Placeholder)
**Required Implementation**:
- **Bot Initialization**: Telegram bot setup and configuration
- **Database Startup**: Connection initialization and health checks
- **Handler Registration**: Command and conversation handler setup
- **Graceful Shutdown**: Resource cleanup on application termination

---

## 💾 Data Architecture Strategy

### **Hybrid Data Approach**
CourseWise uses a sophisticated data strategy optimizing for different data types:

#### **Database Storage** (Persistent)
**Purpose**: Long-term student and academic data
**What to Store**:
- Student profiles and Telegram integration data
- Confirmed academic grades and course history
- Course catalog with prerequisites and metadata
- Specialization selections and academic standing

**What NOT to Store**:
- temporary interaction data
- Raw LLM responses and prompts
- Unconfirmed grade parsing results
- User preferences for individual sessions

#### **Static Files** (Configuration)
**Purpose**: Academic rules and semester-specific data
**Advantages**:
- **Version Control**: Track curriculum changes over time
- **Fast Loading**: No database queries for rules
- **Manual Curation**: Admin-controlled academic data
- **LLM Context**: Direct file loading for prompts

**File Structure**:
```
data/
├── curriculum_rules.md           # Academic regulations and requirements
├── curriculum_chart.json         # Official course sequences by entry year
└── offerings/                    # Course availability per semester
    ├── spring_1404.json          # Current semester offerings
    ├── fall_1403.json            # Previous semester
    └── summer_1404.json          # Summer session
```

#### **Database Sessions** (Persistent)
**Purpose**: Bot interaction state management with persistence
**Storage**: PostgreSQL table with JSONB field for flexible session data
**Lifecycle**: Configurable timeout with database-based cleanup
**Content**:
- Current conversation step and user state
- Unconfirmed grade parsing results
- User preferences for current recommendation session
- Temporary data awaiting user confirmation
**Benefits**:
- **Persistence**: Survives bot restarts and server failures
- **Scalability**: Multiple bot instances can share session data
- **Flexibility**: JSONB allows dynamic session data structures

---

## 🤖 Bot Flow Architecture

### **Three-Phase Interaction Pattern**

#### **Phase 1: Registration & Authentication**
```
User: /start
Bot: "Welcome! Please provide your student number:"
User: "98123456789"
Bot: "Major and current semester?"
User: "Computer Engineering - Semester 4"

💾 Database: Save basic student info to `students` table
🗄️ Session: Store temporary registration data in `user_sessions` table
```

#### **Phase 2: Academic History Input**
```
Bot: "Enter your grades: Math1: 17, CS101: 18, Physics: failed..."
User: [Grade text input]

🤖 LLM: Parse text → Structured JSON grades
Bot: "I detected these grades... Is this correct? ✅❌"
User: ✅ Confirm

💾 Database: Save to `student_grades` table with course foreign keys
🗄️ Session: Clear temporary data from `user_sessions` after confirmation
```

#### **Phase 3: Course Recommendation**
```
Bot: "How many credits? What are your priorities?"
User: "16-18 credits, focus on catching up with failed courses"

🤖 LLM Context Assembly:
- Student profile from database
- Academic history from database  
- Curriculum rules from static files
- Course offerings from semester JSON
- User preferences from session

🤖 LLM: Generate intelligent course recommendation
Bot: "My recommendation: CS201, MATH301, ..."
User: ✅ Accept or ⚙️ Customize

🗄️ Session: Store final recommendation in `user_sessions` (optional)
```

---

## 🧠 LLM Integration Architecture

### **OpenAI Configuration**
```python
client = OpenAI(api_key=settings.openai_api_key)
model = "gpt-4o"  # High-accuracy model for better parsing
```

### **Two Primary LLM Use Cases**

#### **1. Grade Text Parsing**
**Input**: Raw user text (e.g., "Math1: 17, CS101: 18, Physics: failed")
**Context**: Valid course codes from database
**Output**: Structured JSON with course mappings
**Validation**: Against course database for accuracy
**Fallback**: Request user clarification for parsing errors

#### **2. Course Recommendation**
**Input**: Complete academic context assembly
**Context Components**:
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
**Fallback**: Rule-based recommendations when LLM unavailable

### **Error Handling Strategy**
- **LLM Failures**: Graceful degradation to rule-based logic
- **Parse Errors**: Multi-step clarification with user
- **Context Issues**: Partial data processing with warnings
- **Rate Limits**: Retry logic with exponential backoff

---

## 🏫 Domain Knowledge & Academic Context

### **Iranian University System Specifics**
- **Course Codes**: Format like CS101, MATH201, etc.
- **Credit Units**: Theoretical + Practical credits (typically 1-4 units each)
- **GPA Scale**: 0.00 to 20.00 (passing grade ≥ 10.0)
- **Entry Years**: 1401, 1402, 1403, etc. (Iranian calendar)
- **Semester System**: 8 semesters for undergraduate degree

### **Academic Standing Rules**
- **GPA Requirements**: Minimum thresholds for course enrollment
- **Credit Limits**: Maximum credits per semester based on GPA
- **Prerequisite Enforcement**: Strict prerequisite checking
- **Probation Rules**: Academic standing and course restrictions
- **Graduation Requirements**: Total credits and specialization requirements

### **Specialization Tracks** (7 Available)
Each track requires **12 credits** minimum from specialized courses:
1. Artificial Intelligence
2. Computer Networks
3. Software Engineering
4. Computer Graphics
5. Database Systems
6. Computer Security
7. Computer Architecture

### **Course Selection Regulations**
- **Foundation Courses**: Must be completed before specialized courses
- **Corequisites**: Courses that must be taken together
- **Final Semester Rules**: Special regulations for last semester
- **Failed Course Recovery**: Rules for retaking failed courses

---

## 🗄️ Database Schema Summary

### **Core Table Relationships**
```sql
-- Primary entities
students (id, telegram_user_id, student_number, major, entry_year, current_semester)
courses (id, course_code, course_name, theoretical_credits, practical_credits, course_type, entry_year)

-- Session management
user_sessions (id, telegram_user_id, session_data, current_step, expires_at, created_at, updated_at)

-- Academic tracking
student_grades (student_id, course_id, grade, status, attempt_number)
course_prerequisites (course_id, prerequisite_course_id, is_corequisite)

-- Specialization system
elective_groups (id, group_name, required_courses_count, entry_year)
group_courses (group_id, course_id, priority, recommendation_level)
student_specializations (student_id, group_id)
```

### **Key Relationship Patterns**
- **One-to-Many**: Student → StudentGrade (academic history)
- **Self-Referencing**: Course → CoursePrerequisite (prerequisite chains)
- **Many-to-Many**: Course ↔ ElectiveGroup (via GroupCourse)
- **Association**: Student ↔ ElectiveGroup (via StudentSpecialization)

### **Advanced Features**
- **Attempt Tracking**: Multiple attempts per course with `attempt_number`
- **Entry Year Support**: Curriculum changes over time
- **Constraint Validation**: Database-level data integrity
- **Performance Optimization**: Strategic indexes for common queries

---

## 📁 File Structure Reference

### **Current Structure**
```
coursewise/
├── app/
│   ├── config.py                    # ✅ Production-ready configuration
│   ├── core/
│   │   └── database.py              # ✅ Async database infrastructure
│   ├── models/                      # ✅ Complete domain models
│   │   ├── __init__.py              # Model exports and registry
│   │   ├── base.py                  # Base model with common functionality
│   │   ├── student.py               # Student domain entities
│   │   ├── course.py                # Course domain entities
│   │   └── elective.py              # Elective group entities
│   ├── services/                    # 🔄 NEEDS IMPLEMENTATION
│   │   ├── __init__.py              # Service layer exports
│   │   ├── bot.py                   # 🔄 Telegram bot service
│   │   ├── llm.py                   # 🔄 OpenAI integration service
│   │   ├── grade_parser.py          # 🔄 Grade text parsing logic
│   │   └── recommendation.py        # 🔄 Course recommendation engine
│   ├── handlers/                    # 🔄 NEEDS IMPLEMENTATION
│   │   ├── start.py                 # 🔄 Registration flow handler
│   │   ├── grades.py                # 🔄 Grade input flow handler
│   │   └── recommend.py             # 🔄 Recommendation flow handler
│   ├── utils/                       # 🔄 NEEDS IMPLEMENTATION
│   │   ├── session.py               # 🔄 Database session management utilities
│   │   └── validation.py            # 🔄 Data validation helpers
│   └── main.py                      # 🔄 NEEDS IMPLEMENTATION
├── data/                            # 🔄 NEEDS STATIC FILES
│   ├── curriculum_rules.md          # 🔄 Academic rules for LLM context
│   ├── curriculum_chart.json        # 🔄 Course structure by entry year
│   └── offerings/                   # 🔄 Course offerings per semester
│       ├── spring_1404.json         # 🔄 Current semester
│       └── fall_1403.json           # 🔄 Previous semester
├── alembic/                         # ✅ Migration system configured
│   ├── env.py                       # Async migration configuration
│   └── versions/                    # Migration files
├── docs/                            # ✅ Technical documentation
│   ├── context.md                   # Technical context and implementation guide
│   └── project.md                   # Complete project technical context
├── requirements.txt                 # ✅ Dependencies defined
├── .env.example                     # 🔄 NEEDS CREATION
└── README.md                        # 🔄 NEEDS CONTENT
```

---

## 🔧 Development Priorities & Critical Path

### **Phase 1: Foundation Setup** (Week 1)
```bash
# 1. Create UserSession model
# Add UserSession SQLAlchemy model to app/models/

# 2. Database initialization
alembic revision --autogenerate -m "Add UserSession model"
alembic upgrade head                 # Create database schema with sessions

# 3. Environment setup
cp .env.example .env                 # Configure environment variables
# Set: DATABASE_URL, TELEGRAM_BOT_TOKEN, OPENAI_API_KEY

# 4. Basic application structure
python main.py                       # Basic bot startup and health check
```

#### **UserSession Model Requirements**
```python
# Required fields for UserSession model:
class UserSession(Base):
    __tablename__ = "user_sessions"
    
    telegram_user_id: BigInteger      # Foreign key to identify user
    session_data: JSONB               # Flexible JSON field for any session data
    current_step: String              # Current conversation state
    expires_at: DateTime              # Session expiration timestamp
    # + inherited: id, created_at, updated_at from Base
```

### **Phase 2: Core Functionality** (Week 2-3)
1. **Session Management** (`app/utils/session.py`):
   - Database-based session store with configurable timeout
   - UserSession SQLAlchemy model implementation
   - JSONB-based flexible session data storage
   - Multi-instance bot support via database sharing

2. **Static Data Creation** (`data/`):
   - Basic curriculum rules in Markdown format
   - Sample course offerings JSON files
   - Curriculum chart for Computer Engineering

3. **Bot Handlers** (`app/handlers/`):
   - Registration flow: `/start` command and student profile creation
   - Grade input flow: Text processing and confirmation workflow
   - Basic recommendation logic (rule-based fallback)

### **Phase 3: LLM Integration** (Week 4)
1. **LLM Services** (`app/services/llm.py`):
   - OpenAI client configuration and error handling
   - Grade parsing: text → structured data conversion
   - Context assembly: combining database + static file data

2. **Recommendation Engine** (`app/services/recommendation.py`):
   - Intelligent course suggestions using LLM
   - Academic rule validation and constraint checking
   - Fallback to rule-based recommendations

3. **Production Readiness**:
   - Error handling and recovery strategies
   - Logging and monitoring integration
   - Performance optimization and testing

### **Critical Dependencies**
- **Database First**: Cannot test models without schema
- **Static Data Required**: LLM needs curriculum context
- **Session Management**: Foundation for all bot interactions
- **Environment Variables**: Required for all external integrations

---

## ⚙️ Environment Configuration

### **Required Environment Variables**
```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/coursewise

# Telegram Integration
TELEGRAM_BOT_TOKEN=1234567890:ABC123DEF456GHI789JKL012MNO345PQR678

# LLM Integration
OPENAI_API_KEY=sk-proj-1234567890abcdef1234567890abcdef12345678

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### **Development vs Production**
- **Development**: DEBUG=true, LOG_LEVEL=DEBUG, smaller pool sizes
- **Production**: DEBUG=false, LOG_LEVEL=INFO, optimized pool configuration
- **Security**: Never commit secrets, use environment-specific .env files

---

## 🎯 Key Design Decisions & Rationale

### **1. Async-First Architecture**
**Decision**: All database and bot operations use async/await
**Rationale**: 
- Telegram bots are I/O intensive (user interactions, database, LLM calls)
- Async patterns provide better resource utilization
- SQLAlchemy 2.0 async support is mature and performant

### **2. Hardcoded Course Offerings**
**Decision**: Static JSON files instead of dynamic database tables
**Rationale**:
- Course offerings change once per semester (low frequency)
- Manual curation ensures accuracy for academic data
- Faster loading for LLM context (no database joins)
- Version control tracks offering changes over time

### **3. Database-Based Sessions**
**Decision**: Database session storage with JSONB field, persistent across restarts
**Rationale**:
- Bot conversations may span multiple interactions over time
- Persistence improves user experience (survives bot restarts)
- Multiple bot instances can share session state
- JSONB provides flexibility while maintaining database benefits
- Automatic cleanup via database queries (scheduled or on-access)

### **4. Clean Architecture Implementation**
**Decision**: Strict separation between Models, Services, Handlers, Infrastructure
**Rationale**:
- Maintainable codebase as features grow
- Testable components (when testing is added later)
- Easy to modify business logic without affecting UI
- Professional software engineering practices

### **5. No Automated Testing Framework**
**Decision**: Focus on rapid development without test coverage
**Rationale**:
- University project with time constraints
- Manual testing through Telegram bot interaction
- Clean architecture enables easy testing addition later
- Production monitoring will catch issues

### **6. Iranian University Domain Focus**
**Decision**: Hardcoded academic rules specific to Iranian system
**Rationale**:
- Target users are from specific university system
- Academic rules are stable and well-defined
- Reduces complexity compared to generic solution
- LLM can understand domain-specific context better

---

## 🚨 Important Notes & Constraints

### **Testing Strategy**
- **No Automated Tests**: Project prioritizes rapid development over test coverage
- **Manual Testing**: Use actual Telegram bot for end-to-end testing
- **Future Extensibility**: Clean architecture enables easy test addition later
- **Production Monitoring**: Rely on logging and error tracking in production

### **Performance Considerations**
- **Database Indexing**: Strategic indexes on foreign keys and search columns
- **Connection Pooling**: Configured for concurrent user support
- **LLM Caching**: Consider caching common recommendations (future optimization)
- **Session Cleanup**: Database-based cleanup of expired sessions

### **Security Requirements**
- **Environment Variables**: No hardcoded secrets in codebase
- **Input Validation**: Validate all user inputs (Telegram, grades, preferences)
- **Database Security**: Use proper PostgreSQL user permissions
- **API Key Protection**: Secure storage of Telegram and OpenAI keys

### **Production Deployment Notes**
- **Database**: PostgreSQL 15+ required for optimal async performance
- **Python**: 3.12+ required for modern async features
- **Session Storage**: Monitor database session table size and cleanup effectiveness
- **Logging**: Use structured logging for debugging and monitoring

---

## 📚 Additional Context for Future Development

### **Common Development Patterns**
```python
# Database operations pattern
async with get_db() as db:
    result = await db.execute(select(Student).where(Student.telegram_user_id == user_id))
    student = result.scalar_one_or_none()

# LLM integration pattern
context = assemble_recommendation_context(student_id, semester, preferences)
recommendation = await llm_service.generate_recommendation(context)

# Database session management pattern
async with get_db() as db:
    session = await session_manager.get_session(db, user_id)
    await session_manager.update_session(db, user_id, "waiting_grade_confirmation", temp_data=parsed_grades)
```

### **Academic Rule Examples**
- Students cannot take more than 20 credits if GPA < 14.0
- Prerequisites must be passed with grade ≥ 10.0
- Specialization requires 12 credits from single elective group
- Final semester has special enrollment rules

### **Future Enhancement Opportunities**
- **Web Dashboard**: Admin interface for managing static data
- **Analytics**: Student success tracking and recommendation effectiveness
- **Mobile App**: Native mobile application in addition to Telegram
- **Multi-University**: Extend to support other Iranian universities

This CLAUDE.md file serves as the definitive project memory and should be referenced in all future development sessions to maintain consistency and context.