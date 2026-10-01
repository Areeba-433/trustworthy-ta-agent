# Trustworthy TA Agent

# Project Setup Guide

## Epic 1 — User Management Module

**Version:** 1.0
**Status:** Final
**Project Management:** Jira
**Source Control:** GitHub
**Backend:** Python + FastAPI
**Frontend:** React + Vite
**Database:** PostgreSQL
**ORM:** SQLAlchemy
**Migrations:** Alembic
**Containerization:** Docker + Docker Compose

---

# 1. Purpose

This document defines the initial development environment required for the Trustworthy TA Agent project.

The setup must be completed before developers begin implementing individual Epic 1 user stories.

The goal is to ensure that every developer has the same:

* Repository structure
* Development tools
* Backend environment
* Frontend environment
* Database configuration
* Environment variables
* Docker configuration
* API configuration
* Testing setup
* Git branches

After completing this setup, developers should be ready to create feature branches and start implementing their assigned Jira tasks.

---

# 2. Required Software

Each developer should have the following installed:

| Tool                  | Purpose                     |
| --------------------- | --------------------------- |
| Git                   | Version control             |
| GitHub account/access | Source control              |
| Visual Studio Code    | Development                 |
| Python 3.x            | Backend                     |
| Node.js LTS           | Frontend                    |
| npm                   | Frontend package management |
| Docker Desktop        | Containerization            |
| Postman               | API testing                 |
| Web browser           | Application testing         |

PostgreSQL does not need to be installed separately if it is run through Docker Compose.

---

# 3. Repository Setup

The GitHub repository is:

`trustworthy-ta-agent`

The repository should contain the following top-level structure:

```text
trustworthy-ta-agent/

├── backend/
├── frontend/
├── docs/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

The `docs/` directory contains project requirements, architecture, database, API, security, development, and deployment documentation.

---

# 4. Clone the Repository

Each developer should clone the repository locally.

```bash
git clone https://github.com/Areeba-433/trustworthy-ta-agent.git
```

Move into the project:

```bash
cd trustworthy-ta-agent
```

Check the repository:

```bash
git status
```

---

# 5. Git Branch Setup

The project uses two shared branches:

```text
main
  │
  └── develop
        │
        ├── feature/TTA-101-user-registration
        ├── feature/TTA-102-login
        ├── feature/TTA-103-password-reset
        └── feature/TTA-104-profile
```

### `main`

Contains stable code.

### `develop`

Contains integrated development work.

### `feature/*`

Used for individual Jira tasks.

Developers must not directly develop features on `main` or `develop`.

---

# 6. Create the Develop Branch

If `develop` does not already exist:

```bash
git checkout -b develop
git push -u origin develop
```

After `develop` has been created, developers should normally start their work from it.

Update the local repository:

```bash
git checkout develop
git pull origin develop
```

---

# 7. Environment Configuration

The repository contains:

```text
.env.example
```

This file documents the environment variables required by the application.

Each developer creates their own local `.env` file.

Copy:

```text
.env.example
```

to:

```text
.env
```

Do not commit `.env`.

The `.env` file contains local configuration and secrets.

Example variables:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/trustworthy_ta

JWT_SECRET_KEY=change-this-in-local-development

ACCESS_TOKEN_EXPIRE_MINUTES=30

FRONTEND_URL=http://localhost:5173

CORS_ORIGINS=http://localhost:5173

SMTP_HOST=mailhog

SMTP_PORT=1025

SMTP_USERNAME=

SMTP_PASSWORD=
```

The exact values may be changed according to the project's Docker and application configuration.

---

# 8. Backend Setup

The backend uses:

* Python
* FastAPI
* SQLAlchemy
* Alembic
* Pydantic
* Pytest
* Ruff

The backend directory is:

```text
backend/
```

Expected structure:

```text
backend/

├── app/
│   ├── api/
│   │   └── v1/
│   ├── core/
│   ├── middleware/
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── utils/
│   └── main.py
│
├── tests/
├── alembic/
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

---

# 9. Backend Virtual Environment

For local backend development, create a virtual environment:

```bash
cd backend
```

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Verify Python:

```bash
python --version
```

Verify FastAPI installation:

```bash
python -c "import fastapi; print(fastapi.__version__)"
```

The `.venv` directory must not be committed to Git.

---

# 10. Backend Application Verification

Run the FastAPI application locally according to the project's configured entry point.

For the expected structure:

```bash
uvicorn app.main:app --reload
```

The API should be available at:

```text
http://localhost:8000
```

FastAPI documentation should be available at:

```text
http://localhost:8000/docs
```

The health endpoint should be available at:

```text
http://localhost:8000/health
```

The health endpoint should return a successful response when the backend is running correctly.

---

# 11. Frontend Setup

The frontend uses:

* React
* Vite
* Tailwind CSS
* ESLint
* Prettier
* Vitest / React Testing Library

The frontend directory is:

```text
frontend/
```

Expected structure:

```text
frontend/

├── src/
│   ├── components/
│   ├── pages/
│   ├── layouts/
│   ├── services/
│   ├── context/
│   ├── hooks/
│   ├── routes/
│   ├── utils/
│   ├── constants/
│   ├── App.jsx
│   └── main.jsx
│
├── package.json
├── Dockerfile
└── vite.config.js
```

Install dependencies:

```bash
cd frontend
npm install
```

Start the frontend:

```bash
npm run dev
```

The frontend should normally be available at:

```text
http://localhost:5173
```

---

# 12. Frontend Environment Configuration

Frontend environment variables must use the Vite convention.

Example:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Frontend environment variables must never contain private secrets.

Anything exposed through `VITE_*` should be considered publicly visible to the browser.

---

# 13. PostgreSQL Setup

PostgreSQL will be used as the project's relational database.

The preferred development setup is to run PostgreSQL through Docker Compose.

Expected database configuration:

```text
Database:
trustworthy_ta

Host:
postgres

Port:
5432
```

The exact username, password, and database URL must match the project's `.env` and Docker Compose configuration.

Developers should not manually create or modify database tables.

---

# 14. SQLAlchemy Setup

SQLAlchemy is used as the backend ORM.

Epic 1 database models include:

```text
User
Profile
Session
VerificationToken
PasswordResetToken
Role
Permission
AuditLog
```

Models must follow the approved database specification:

```text
docs/database/epic-1-database.md
```

Developers must not introduce database fields or relationships without coordinating the change with the team.

---

# 15. Alembic Setup

Alembic manages database schema changes.

The migration directory is:

```text
backend/alembic/
```

A schema change must follow:

```text
SQLAlchemy Model
       ↓
Alembic Migration
       ↓
Review
       ↓
Migration Applied
```

Create a migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

Check migration status:

```bash
alembic current
```

Never manually modify shared database tables as a replacement for migrations.

---

# 16. Docker Setup

The project uses Docker Compose to provide a consistent development environment.

Expected services:

```text
frontend
backend
postgres
```

Optional development service:

```text
mailhog
```

MailHog may be used for testing registration and email verification without sending real emails.

---

# 17. Start the Complete Project

From the repository root:

```bash
docker compose up --build
```

This should start the required project services.

Developers should verify:

```text
Frontend → http://localhost:5173

Backend  → http://localhost:8000

Swagger  → http://localhost:8000/docs

Health   → http://localhost:8000/health
```

---

# 18. Stop the Project

Stop the containers:

```bash
docker compose down
```

Do not routinely use:

```bash
docker compose down -v
```

The `-v` option removes Docker volumes and may delete local PostgreSQL data.

Use it only when intentionally resetting the local database.

---

# 19. Initial Database Migration

After PostgreSQL and the backend are running, apply the project's migrations:

```bash
alembic upgrade head
```

Verify that the migration completes successfully.

The database should match the approved Epic 1 database specification.

---

# 20. API Configuration

The API uses versioned routes:

```text
/api/v1
```

Epic 1 API endpoints must follow:

```text
docs/api/epic-1-api-contract.md
```

FastAPI Swagger is used to inspect and test the implemented API.

Swagger:

```text
http://localhost:8000/docs
```

The API contract document remains the agreed specification for the team.

---

# 21. CORS Configuration

The backend must allow requests from the configured frontend development URL.

Development example:

```text
http://localhost:5173
```

CORS configuration should be controlled through environment configuration rather than hard-coded production values.

---

# 22. Testing Setup

Backend tests use Pytest.

Run backend tests:

```bash
pytest
```

Frontend tests use the project's configured testing tools.

Run frontend tests:

```bash
npm test
```

If the project uses a different script defined in `package.json`, use the configured script.

Tests should run independently and must not depend on another developer's local database.

---

# 23. Code Quality Setup

Backend:

```text
Ruff
```

Frontend:

```text
ESLint
Prettier
```

Before opening a Pull Request, developers should run the configured formatting, linting, and testing commands.

Do not commit code that contains unresolved linting or formatting errors.

---

# 24. Verify the Complete Setup

Before starting feature development, every developer must verify:

### Repository

* [ ] Repository cloned successfully
* [ ] Git authentication works
* [ ] `develop` branch available
* [ ] Git status works

### Backend

* [ ] Python installed
* [ ] Virtual environment works
* [ ] Dependencies installed
* [ ] FastAPI starts
* [ ] `/health` works
* [ ] Swagger works

### Frontend

* [ ] Node.js installed
* [ ] npm dependencies installed
* [ ] React application starts
* [ ] Frontend opens successfully

### Database

* [ ] PostgreSQL starts
* [ ] Backend connects to PostgreSQL
* [ ] Alembic is configured
* [ ] Migrations run successfully

### Docker

* [ ] Docker Desktop running
* [ ] `docker compose up --build` works
* [ ] Backend container works
* [ ] Frontend container works
* [ ] PostgreSQL container works

### Configuration

* [ ] `.env` created
* [ ] `.env.example` understood
* [ ] `.env` is ignored by Git
* [ ] No secrets committed

### Testing

* [ ] Backend tests run
* [ ] Frontend tests run
* [ ] Linting works

---

# 25. Git Verification

Before beginning feature development:

```bash
git status
```

Expected result should show no unintended changes.

Verify branches:

```bash
git branch
```

Update `develop`:

```bash
git checkout develop
git pull origin develop
```

The developer is now ready to create a feature branch.

---

# 26. Starting a User Story

Once the project setup is complete, the developer should:

### Step 1 — Open Jira

Select the assigned user story/task.

Example:

```text
TTA-101 — User Registration
```

### Step 2 — Understand the requirements

Read:

```text
docs/requirements/epic-1-requirements.md
```

### Step 3 — Check architecture

Read:

```text
docs/architecture/epic-1-architecture.md
```

### Step 4 — Check database requirements

Read:

```text
docs/database/epic-1-database.md
```

### Step 5 — Check API requirements

Read:

```text
docs/api/epic-1-api-contract.md
```

### Step 6 — Check security requirements

Read:

```text
docs/security/authentication.md
```

### Step 7 — Create a feature branch

Example:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/TTA-101-user-registration
```

### Step 8 — Begin development

Follow:

```text
docs/development/coding-conventions.md
```

and:

```text
docs/development/git-workflow.md
```

---

# 27. Project Setup Completion Criteria

Project setup is considered complete when:

```text
Repository
    ↓
Git branches
    ↓
Backend
    ↓
Frontend
    ↓
PostgreSQL
    ↓
SQLAlchemy
    ↓
Alembic
    ↓
Docker Compose
    ↓
Environment configuration
    ↓
API
    ↓
Swagger
    ↓
Health check
    ↓
Testing
    ↓
Code quality
    ↓
Verification
```

have all been successfully configured and verified.

---

# 28. Ready for Development

After completing this document, developers should **not create their own project structure or architectural approach**.

They should proceed directly to their assigned Jira user story.

The development sequence is:

```text
Project Setup Complete
        ↓
Read Jira User Story
        ↓
Read Relevant Documentation
        ↓
Update develop
        ↓
Create Feature Branch
        ↓
Implement
        ↓
Test
        ↓
Commit
        ↓
Push
        ↓
Pull Request
        ↓
Code Review
        ↓
Merge into develop
```

The project setup is a one-time foundation. Individual user stories should then be implemented according to the approved requirements, architecture, database specification, API contract, security documentation, coding conventions, and Git workflow.
