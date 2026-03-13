# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SoundVerse (听听·原声态) is an AI-powered "sound encyclopedia + social audio library" WeChat mini-program project. The project reconstructs radio programs into granular audio segments using AI technology, establishes a sound library, and enables intelligent audio interaction and generation.

### Project Structure
```
SoundVerse/
├── wechat-miniprogram/          # WeChat mini-program frontend
│   ├── src/pages/              # Pages (index, chat, generate, upload, profile)
│   ├── src/components/         # Reusable components (audio-player, etc.)
│   ├── src/services/           # API services and business logic
│   ├── src/stores/             # State management
│   ├── src/utils/              # Utility functions
│   └── src/types/              # TypeScript type definitions
├── backend/                    # Python backend service
│   ├── api/v1/                 # API routes (auth, audio, chat, generate)
│   ├── services/               # Business services
│   ├── shared/                 # Shared code
│   │   ├── database/          # Database models and session
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── utils/             # Utilities and logging
│   ├── ai-models/             # AI service integrations
│   ├── infrastructure/        # Infrastructure configs
│   ├── scripts/               # Development and deployment scripts
│   └── tests/                 # Test files
└── CLAUDE.md                  # This file - project guidance
```

### Core Technologies
- **Frontend**: WeChat mini-program (TypeScript, Vant Weapp)
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy, Celery, Redis
- **Database**: MySQL, FAISS for vector search
- **AI Services**: Alibaba Cloud ASR/TTS/NLP APIs
- **Storage**: Alibaba Cloud OSS
- **Containerization**: Docker, Docker Compose

## Development Environment

### Python Version
Check for `.python-version`, `pyproject.toml`, or `runtime.txt` to determine the required Python version. If none exist, assume Python 3.11+.

### Dependency Management
- Look for `pyproject.toml`, `requirements.txt`, `Pipfile`, `poetry.lock`, or `uv.lock` to identify the package manager.
- If using **Poetry**: `poetry install` to install dependencies, `poetry run` to execute commands.
- If using **UV**: `uv sync` to install dependencies.
- If using **pip**: `pip install -r requirements.txt` or `pip install -e .` for editable installs.
- If no dependency manager is configured, suggest adding one.

### Virtual Environment
A virtual environment is recommended. Look for `.venv`, `venv`, `env`, or `.pixi` directories. If none exist, create one with `python -m venv .venv` and activate it.

### WeChat Mini-program Development
- **Development Tool**: WeChat Developer Tools (required)
- **Package Manager**: npm (Node.js required)
- **Build Tool**: TypeScript compiler (tsc)
- **UI Framework**: Vant Weapp component library
- **To install dependencies**: `cd wechat-miniprogram && npm install`
- **To build**: `npm run build` or use WeChat Developer Tools build feature

## Common Development Tasks

### Backend Development

#### Starting Development Environment
```bash
cd backend
chmod +x scripts/start_dev.sh
./scripts/start_dev.sh
```

#### Installing Dependencies
```bash
cd backend
# Using pip (recommended for development)
pip install -e ".[dev]"

# Or using the Docker development environment
docker-compose build api
```

#### Running Tests
- Tests are not yet implemented. When added:
  - Run tests: `pytest`
  - Run specific test: `pytest tests/test_auth.py -v`
  - Run with coverage: `pytest --cov=backend tests/`

#### Linting and Formatting
- **Black** (formatting): `black .`
- **Ruff** (linting): `ruff check .` or `ruff check . --fix`
- Both are configured in `pyproject.toml`

#### Type Checking
- **mypy**: `mypy .` (configured in `pyproject.toml`)
- Type checking is strict - fix all type errors before committing

#### Database Migrations
- **Alembic** is configured but migrations are not yet created
- Create migration: `alembic revision --autogenerate -m "description"`
- Apply migration: `alembic upgrade head`

### Frontend Development (WeChat Mini-program)

#### Installing Dependencies
```bash
cd wechat-miniprogram
npm install
```

#### Building and Development
- **Development**: Use WeChat Developer Tools for live preview
- **Build TypeScript**: `npm run build`
- **Watch mode**: `npm run watch`
- **Linting**: `npm run lint` (ESLint configured)
- **Formatting**: `npm run format` (Prettier configured)

#### WeChat Developer Tools
1. Open WeChat Developer Tools
2. Import project from `wechat-miniprogram/` directory
3. Configure AppID in `project.config.json`
4. Use built-in preview, debug, and upload features

### Docker Development

#### Starting Services
```bash
cd backend
docker-compose up -d  # Start all services
docker-compose ps     # Check service status
docker-compose logs -f api  # View API logs
```

#### Stopping Services
```bash
cd backend
docker-compose down  # Stop and remove containers
docker-compose down -v  # Also remove volumes (data will be lost)
```

#### Rebuilding Services
```bash
cd backend
docker-compose up -d --build  # Rebuild and restart
```

### API Documentation
- Start backend services
- Access Swagger UI: http://localhost:8000/docs
- Access ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics (Prometheus format)

## Project Structure (Current)

The project follows a multi-repo structure within a single repository:

### Backend (Python)
- `backend/` - Main backend service directory
  - `main.py` - FastAPI application entry point
  - `config.py` - Configuration management
  - `pyproject.toml` - Python project configuration and dependencies
  - `docker-compose.yml` - Docker development environment
  - `api/v1/` - API routes organized by version
  - `services/` - Business logic services
  - `shared/` - Shared database models, schemas, utilities
  - `ai-models/` - AI service integrations (ASR, TTS, NLP)
  - `infrastructure/` - Deployment and monitoring configs
  - `scripts/` - Development and deployment scripts
  - `tests/` - Test files (to be implemented)

### Frontend (WeChat Mini-program)
- `wechat-miniprogram/` - WeChat mini-program frontend
  - `src/pages/` - Mini-program pages
  - `src/components/` - Reusable components
  - `src/services/` - API services and business logic
  - `src/stores/` - State management (if needed)
  - `src/utils/` - Utility functions
  - `src/types/` - TypeScript type definitions
  - `app.json` - Mini-program configuration
  - `app.ts` - Mini-program entry point
  - `package.json` - npm dependencies

### Key Development Patterns
- **Backend**: Follows FastAPI patterns with dependency injection
- **Database**: SQLAlchemy async ORM with Alembic for migrations
- **API**: RESTful design with OpenAPI documentation
- **Frontend**: Component-based architecture with TypeScript
- **AI Integration**: Alibaba Cloud APIs with local caching and fallbacks

## Configuration Files

### Backend Configuration
- `backend/pyproject.toml` – Python project configuration, dependencies, and tool settings (black, ruff, mypy)
- `backend/.env.example` – Environment variable template (copy to `.env` for local development)
- `backend/docker-compose.yml` – Docker development environment
- `backend/Dockerfile.dev` – Development Dockerfile

### Frontend Configuration
- `wechat-miniprogram/project.config.json` – WeChat Developer Tools project configuration
- `wechat-miniprogram/app.json` – Mini-program global configuration
- `wechat-miniprogram/tsconfig.json` – TypeScript compiler configuration
- `wechat-miniprogram/package.json` – npm dependencies and scripts

### Key Environment Variables (Backend)
- `DATABASE_URL` – MySQL database connection string
- `REDIS_URL` – Redis connection string
- `ALIYUN_ACCESS_KEY_ID` – Alibaba Cloud API access key
- `ALIYUN_ACCESS_KEY_SECRET` – Alibaba Cloud API secret key
- `WECHAT_APP_ID` – WeChat mini-program AppID
- `WECHAT_APP_SECRET` – WeChat mini-program AppSecret

**Important**: Never commit `.env` files with secrets to version control.

## Git Hooks

### Pre-commit Hooks
Pre-commit hooks are configured for backend development:
- Install: `pre-commit install` (in backend directory)
- Run manually: `pre-commit run --all-files`
- Hooks include: black, ruff, mypy, and other code quality checks

### Commit Message Convention
Follow conventional commits format:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Test-related changes
- `chore:` Maintenance tasks

Example: `feat(auth): add WeChat login support`

## CI/CD

### Backend CI/CD (Planned)
- GitHub Actions workflows will be added in `.github/workflows/`
- Automated testing on pull requests
- Docker image building and pushing
- Deployment to staging/production environments

### Frontend Deployment
- WeChat mini-programs are deployed via WeChat Developer Tools
- Development, trial, and production environments in WeChat platform
- Version management through WeChat mini-program backend

### Environment Strategy
1. **Development**: Local Docker environment
2. **Staging**: Test environment with real cloud services
3. **Production**: Production deployment with monitoring and alerts

## Monitoring and Observability

### Backend Monitoring
- Prometheus metrics exposed at `/metrics`
- Structured logging with log levels
- Health check endpoint at `/health`
- Performance monitoring planned (APM tools)

### Error Tracking
- Application errors are logged with context
- User-facing error messages are friendly
- Technical details are logged for debugging

## Security Considerations

### API Security
- JWT token authentication
- Rate limiting on sensitive endpoints
- CORS configured for specific origins
- Input validation with Pydantic

### Data Security
- Database connection pooling with SSL
- Redis with authentication
- Environment variables for secrets
- Regular dependency updates for security patches

### WeChat Mini-program Security
- Official WeChat login flow
- Secure storage of user tokens
- Content moderation for user-generated content
- Privacy policy compliance

## Cursor / Copilot Rules

If `.cursor/rules/` or `.cursorrules` exist, incorporate those guidelines. Similarly for `.github/copilot-instructions.md`. Currently none are present.

## Notes

### Current Project Status (March 2026)
The project has been initialized with the complete technical implementation plan. The following has been implemented:

#### ✅ Completed
1. **Project structure** - Complete directory organization for both backend and frontend
2. **Backend foundation** - FastAPI application with configuration management
3. **Database models** - SQLAlchemy models for users, audio, chat sessions
4. **API endpoints** - Basic endpoints for authentication, audio, chat, and generation
5. **Service layer** - Business logic services with proper separation
6. **AI integration** - NLP service structure with Alibaba Cloud integration pattern
7. **WeChat mini-program** - Basic structure with TypeScript, components, and services
8. **Development environment** - Docker Compose setup for local development
9. **Documentation** - README and CLAUDE.md updated with project guidance

#### 🔄 In Progress / To Be Implemented
1. **Database migrations** - Alembic migration scripts
2. **AI service implementation** - Actual Alibaba Cloud API integration
3. **Audio processing** - Actual audio segmentation and processing logic
4. **Vector search** - FAISS index population and search optimization
5. **WeChat login** - Actual WeChat API integration
6. **Testing** - Unit and integration tests
7. **Frontend pages** - Complete implementation of all mini-program pages
8. **Deployment scripts** - Production deployment configuration

### Development Priorities (MVP Phase)
1. **Core chat functionality** - Text-to-audio matching and playback
2. **User authentication** - WeChat login integration
3. **Basic audio generation** - Template-based audio generation
4. **Audio upload and processing** - User audio upload and basic processing
5. **Performance optimization** - Caching, indexing, and API optimization

### Dependencies and Requirements
- **Alibaba Cloud account** with ASR, TTS, NLP, OSS, RDS, Redis services
- **WeChat mini-program account** with AppID and AppSecret
- **Development tools**: Docker, Python 3.11+, Node.js, WeChat Developer Tools
- **Team skills**: Python (FastAPI), TypeScript, WeChat mini-program development, AI/ML basics

### Cost Management
- **Development phase**: < 500 RMB/month (free tiers and development resources)
- **MVP phase**: < 2000 RMB/month (carefully managed API calls)
- **Growth phase**: Implement user quotas, premium features, monetization

### Next Steps for Development Team
1. Set up Alibaba Cloud services and obtain API credentials
2. Configure WeChat mini-program in WeChat platform
3. Implement database migrations and populate with test data
4. Complete AI service integrations (ASR, TTS, NLP)
5. Develop core chat interface in WeChat mini-program
6. Test end-to-end flow and iterate based on feedback

### Best Practices to Follow
- Always use type hints in Python code
- Write tests for new functionality
- Follow the established project structure
- Update documentation when making changes
- Use environment variables for configuration
- Implement proper error handling and logging
- Consider security implications of all changes

### Contact and Support
- Technical issues: Check documentation first, then create GitHub issues
- Development questions: Review code structure and existing implementations
- Feature requests: Discuss with product team before implementation