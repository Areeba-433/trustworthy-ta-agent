# Trustworthy TA Agent

## Deployment Guide — Epic 1: User Management Module

**Version:** 1.0
**Status:** Final

---

## 1. Overview

This document defines the deployment and local development process for the **Trustworthy TA Agent — User Management Module**.

The application uses:

* **React** — Frontend
* **FastAPI** — Backend/API
* **PostgreSQL** — Database
* **Docker & Docker Compose** — Containerization
* **Alembic** — Database migrations

The deployment setup allows all team members and supervisors to run and test the application without manually installing the complete development environment.

---

## 2. Application Architecture

```text
                    Internet
                       │
                    HTTPS
                       │
                Reverse Proxy
                       │
             ┌─────────┴─────────┐
             │                   │
          React              FastAPI
        Frontend               API
                                 │
                                 ▼
                            PostgreSQL
```

### Docker Services

The local development environment contains:

```text
frontend
backend
postgres
```

An optional `mailhog` service may be added for testing registration and password-reset emails without sending real emails.

---

## 3. Repository Structure

The deployment-related files should be maintained at the repository root:

```text
trustworthy-ta-agent/
│
├── frontend/
├── backend/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── deployment.md
└── README.md
```

---

## 4. Environment Configuration

All environment-specific configuration must use environment variables.

### `.env.example`

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/trustworthy_ta

JWT_SECRET_KEY=change_this_secret

ACCESS_TOKEN_EXPIRE_MINUTES=30

FRONTEND_URL=http://localhost:5173

CORS_ORIGINS=http://localhost:5173

SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
```

Create a local `.env` file from `.env.example`.

**Never commit `.env` or production secrets to GitHub.**

The following must remain secret:

* Database passwords
* JWT secret keys
* API keys
* SMTP passwords
* Authentication tokens
* Reset/verification tokens

---

## 5. Local Deployment

### Prerequisites

Install:

* Git
* Docker Desktop
* VS Code

No separate Python, Node.js, or PostgreSQL installation should be required when using Docker.

### Clone the Repository

```bash
git clone <repository-url>
cd trustworthy-ta-agent
```

### Configure Environment

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update `.env` with the required local configuration.

### Start the Application

```bash
docker compose up --build
```

To run containers in the background:

```bash
docker compose up --build -d
```

### Application URLs

After successful startup:

| Service          | URL                              |
| ---------------- | -------------------------------- |
| Frontend         | `http://localhost:5173`          |
| Backend          | `http://localhost:8000`          |
| Swagger API Docs | `http://localhost:8000/api/docs` |
| Health Check     | `http://localhost:8000/health`   |

The exact ports may be changed in `docker-compose.yml`, but the team should use one shared configuration.

---

## 6. Database

PostgreSQL runs inside Docker and should use a named volume:

```text
postgres
   │
   └── postgres_data
```

The volume ensures that restarting containers does not automatically delete database data.

### Database Migration

Apply migrations using:

```bash
alembic upgrade head
```

If Alembic runs inside the backend container:

```bash
docker compose exec backend alembic upgrade head
```

Database migrations must be committed to GitHub whenever the database schema changes.

---

## 7. Backend Deployment

The backend container must:

1. Install Python dependencies.
2. Copy the backend source code.
3. Load environment variables.
4. Connect to PostgreSQL.
5. Apply database migrations.
6. Start the FastAPI application.
7. Expose the API and health endpoint.

Example startup command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The exact module path should match the project's backend structure.

---

## 8. Frontend Deployment

The frontend container must:

1. Install Node dependencies.
2. Build/run the React application.
3. Use the configured backend API URL.
4. Expose the frontend application.

For production, the React application should be built into static files and served through a production web server or reverse proxy.

---

## 9. Health Check

The backend must provide:

```http
GET /health
```

Expected response:

```json
{
  "status": "healthy"
}
```

The endpoint should confirm that the backend is running and required infrastructure, particularly PostgreSQL, is available.

---

## 10. Production Deployment

The production architecture should be:

```text
                    HTTPS
                      │
                      ▼
               Reverse Proxy
                      │
              ┌───────┴───────┐
              │               │
            React          FastAPI
           Frontend           │
                              ▼
                         PostgreSQL
                         (Private)
```

Production deployment must provide:

* HTTPS
* Secure environment variables
* Restricted CORS
* Private PostgreSQL access
* Database backups
* Production logging
* Health checks

---

## 11. Production Environment

Production configuration must include appropriate values for:

```env
DEBUG=false
DATABASE_URL=<production-database-url>
JWT_SECRET_KEY=<strong-secret>
FRONTEND_URL=<production-frontend-url>
CORS_ORIGINS=<production-frontend-url>
SMTP_HOST=<production-smtp-host>
SMTP_PORT=<production-smtp-port>
SMTP_USERNAME=<production-smtp-user>
SMTP_PASSWORD=<production-smtp-password>
```

Production secrets must be stored using the hosting provider's secret manager or GitHub Actions Secrets.

---

## 12. Security Requirements

Production authentication must use HTTPS.

Authentication cookies, where applicable, should use:

* `Secure`
* `HttpOnly`
* Appropriate `SameSite` configuration

Production CORS must allow only the actual frontend domain.

Never use unrestricted:

```text
*
```

for production authentication APIs.

PostgreSQL must not be publicly accessible. Only the backend should connect to the production database.

---

## 13. Logging

Production logs should contain:

* Timestamp
* Service
* Log level
* Request ID
* Endpoint
* HTTP status
* Safe error information

Never log:

* Passwords
* JWTs
* Reset tokens
* Verification tokens
* Database passwords
* API keys

---

## 14. CI/CD

GitHub Actions should eventually automate:

```text
Feature Branch
      ↓
Pull Request
      ↓
Code Review
      ↓
CI Checks
      ↓
develop
      ↓
Integration Testing
      ↓
main
      ↓
Docker Build
      ↓
Deployment
      ↓
Migration
      ↓
Health Check
      ↓
Smoke Tests
```

CI should verify:

* Backend tests
* Frontend tests
* Linting
* Build success
* Docker image build

Deployment should not proceed when required CI checks fail.

---

## 15. Deployment Smoke Tests

After deployment, verify:

```text
[ ] Frontend loads
[ ] Backend health endpoint works
[ ] Swagger documentation loads
[ ] User registration works
[ ] Email verification works
[ ] Login works
[ ] Protected endpoints work
[ ] Logout works
[ ] Password reset works
[ ] Profile update works
[ ] Admin endpoints work
[ ] Student cannot access admin endpoints
[ ] Teacher cannot access admin endpoints
[ ] Admin can manage users
[ ] Deactivated users cannot log in
```

---

## 16. Rollback

If a deployment fails:

```text
Failed Deployment
       ↓
Identify Version
       ↓
Rollback Application
       ↓
Check Database Compatibility
       ↓
Run Health Checks
       ↓
Run Smoke Tests
       ↓
Investigate Failure
```

Database migrations must be handled carefully because rolling back application code does not automatically make database changes reversible.

---

## 17. Deployment Definition of Done

Epic 1 deployment is complete when:

* [ ] Docker Compose works locally
* [ ] Frontend container works
* [ ] Backend container works
* [ ] PostgreSQL container works
* [ ] Database migrations work
* [ ] Environment configuration works
* [ ] Health endpoint works
* [ ] CI checks pass
* [ ] Application is deployed
* [ ] HTTPS works
* [ ] Authentication works after deployment
* [ ] Email verification works
* [ ] Password reset works
* [ ] RBAC works
* [ ] Account deactivation works
* [ ] Production secrets are protected
* [ ] Smoke tests pass
