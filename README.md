# CourseWise - Telegram Bot for University Course Selection

An intelligent Telegram bot that helps Computer Engineering students make optimal course selections using AI-powered recommendations and academic rule validation.

## Features

- **Student Registration**: Simple profile setup with Telegram integration
- **Grade Management**: Natural language grade input and parsing  
- **AI Recommendations**: Smart course suggestions based on academic history and rules
- **Menu Navigation**: Comprehensive bot interface with curriculum charts and academic rules
- **Persian Interface**: Full Farsi language support

## Tech Stack

**Backend**: Python 3.12, python-telegram-bot, AsyncIO  
**AI/LLM**: OpenAI GPT-4, Pydantic for data validation  
**Database**: PostgreSQL 15+, SQLAlchemy 2.0 with AsyncPG driver  
**Infrastructure**: Docker, Alembic migrations  
**Architecture**: Clean Architecture with async-first design

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- Telegram Bot Token
- OpenAI API Key

### Development Setup
```bash
# Clone and setup
git clone https://github.com/sajadsoltanist/course-wise.git
cd course-wise
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Start database
docker compose -f docker-compose.dev.yml up -d postgres

# Run migrations
python -m alembic upgrade head

# Start bot
python -m app.main
```

### Docker Development
```bash
# Start everything
docker compose -f docker-compose.dev.yml up -d

# Run migrations
docker exec coursewise-bot-dev python -m alembic upgrade head
```

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram      │    │   CourseWise    │    │   External      │
│   Ecosystem     │    │   Bot System    │    │   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  👤 Student     │◄────────┤  📱 Telegram    │         │  🧠 OpenAI      │
│     Users       │  HTTP   │    Bot API      │         │    GPT-4o       │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                     │                           ▲
                                     │ Webhook/                  │
                                     │ Polling                   │ API
                                     ▼                           │ Calls
                            ┌─────────────────┐                  │
                            │  🎛️ CourseWise  │──────────────────┘
                            │   Bot Handler   │
                            └─────────────────┘
                                     │
                            ┌────────┼────────┐
                            │                 │
                            ▼                 ▼
                   ┌─────────────────┐ ┌─────────────────┐
                   │  📋 Session     │ │  🧠 AI Service  │
                   │   Management    │ │   (RAG Engine)  │
                   └─────────────────┘ └─────────────────┘
                            │                 │
                            │                 │ Context
                            │                 │ Retrieval
                            ▼                 ▼
                   ┌─────────────────┐ ┌─────────────────┐
                   │  🐘 PostgreSQL  │ │  📚 Static      │
                   │   Database      │ │   Data Files    │
                   │                 │ │                 │
                   │ • Students      │ │ • Curriculum    │
                   │ • Grades        │ │ • Course Rules  │
                   │ • Sessions      │ │ • Offerings     │
                   └─────────────────┘ └─────────────────┘

Request Flow:
1. Student sends message → Telegram API
2. Telegram API → CourseWise Bot Handler  
3. Handler loads session state from PostgreSQL
4. Handler calls AI Service for intelligent processing
5. AI Service retrieves context from static data files
6. AI Service queries OpenAI GPT-4o with enriched context
7. Response flows back: AI → Handler → Telegram → Student
```

## Project Structure

```
app/
├── models/          # SQLAlchemy domain models
├── services/        # Business logic and AI integration
├── handlers/        # Telegram conversation flows
├── core/           # Database and configuration
└── main.py         # Application entry point

data/               # Static curriculum and rules
alembic/           # Database migrations
```

## Key Components

**Database Models**: Student profiles, courses, grades, sessions  
**LLM Service**: Grade parsing and recommendation generation  
**Menu System**: Comprehensive navigation with inline keyboards  
**Academic Rules**: University regulation validation  
**Session Management**: Database-backed conversation state

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `DEBUG` | Enable debug mode | No |

## Database Schema

- **students**: User profiles and academic info
- **user_sessions**: Bot conversation state with JSONB data
- **courses**: Course catalog (populated from static data)
- **student_grades**: Academic history with attempt tracking

## CI/CD & Deployment Pipeline

CourseWise uses modern DevOps practices with automated deployment pipeline:

```
Development Workflow:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Developer     │    │   GitHub        │    │   Production    │
│   Environment   │    │   Repository    │    │   Server        │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  💻 Local       │  git    │  📦 GitHub      │  SSH    │  🚀 Production  │
│   Development   │ push    │   Actions       │ Deploy  │   Server        │
│                 │────────▶│                 │────────▶│                 │
│ • Docker Compose│         │ • Build Image   │         │ • Docker Compose│
│ • Hot Reload    │         │ • Run Tests     │         │ • Auto Migration│
│ • Local DB      │         │ • Push to GHCR  │         │ • Health Check  │
└─────────────────┘         └─────────────────┘         └─────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  🐳 GitHub      │
                            │   Container     │
                            │   Registry      │
                            │   (GHCR)        │
                            └─────────────────┘

Deployment Steps:
1. Code push to main branch triggers GitHub Actions
2. Docker image built and pushed to GitHub Container Registry
3. SSH connection established to production server
4. Latest image pulled and containers updated
5. Database migrations run automatically
6. Health checks verify deployment success
```

### Development Environment

**Local Setup:**
```bash
# Development with hot reload
docker compose -f docker-compose.dev.yml up -d

# Production-like testing
docker compose -f docker-compose.prod.yml up -d
```

**Key Features:**
- **Hot Reload**: Code changes reflected immediately in development
- **Database Seeding**: Automatic population of course data
- **Environment Isolation**: Separate configs for dev/prod
- **Health Monitoring**: Container health checks and logging

### Production Deployment

**Infrastructure:**
- **Containerization**: Docker + Docker Compose
- **Image Registry**: GitHub Container Registry (GHCR)
- **Database**: PostgreSQL with automated migrations
- **Reverse Proxy**: Nginx (if applicable)
- **SSL/TLS**: Let's Encrypt certificates

**Deployment Process:**
1. **Build Stage**: Multi-stage Docker build for optimized images
2. **Test Stage**: Automated testing (if tests exist)
3. **Registry Push**: Secure push to GHCR with authentication
4. **Server Deployment**: SSH-based deployment with zero downtime
5. **Migration**: Automatic Alembic database migrations
6. **Verification**: Health checks and log monitoring

**Security & Best Practices:**
- SSH key-based authentication for deployment
- Environment variables for sensitive data
- Container security with non-root users
- Automated secret rotation capabilities
- Database backup strategies

## Academic Context

**Iranian University System**:
- Grading scale: 0-20 (passing ≥ 10.0)
- Credit system with theoretical + practical units
- Entry years: 1403+ vs before 1403 (different curricula)
- 7 specialization tracks available

