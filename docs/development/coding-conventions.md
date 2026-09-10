# Trustworthy TA Agent

# Coding Conventions & Development Standards

**Epic:** Epic 1 — User Management Module
**Version:** 1.0
**Status:** Final
**Repository:** GitHub

---

# 1. Purpose

This document defines the coding conventions and development standards that all team members must follow while developing the Trustworthy TA Agent.

The objective is to ensure that code written by different developers remains:

* Consistent
* Readable
* Maintainable
* Secure
* Testable
* Reusable
* Easy to review

All developers must follow these conventions when contributing to the project.

---

# 2. General Principles

The team follows these principles:

```text
Readable > Clever
Simple > Over-engineered
Reusable > Duplicated
Tested > Assumed
Explicit > Implicit
Secure > Convenient
Consistent > Personal Preference
```

Code should be written for the team, not only for the developer who created it.

---

# 3. Technology Standards

## Backend

```text
Language: Python 3.x
Framework: FastAPI
ORM: SQLAlchemy
Database: PostgreSQL
Migration Tool: Alembic
Validation: Pydantic
```

## Frontend

```text
Language: JavaScript
Framework: React
Build Tool: Vite
Styling: Tailwind CSS
```

The team should use the versions defined in the project's dependency files.

---

# 4. Python Naming Conventions

Python code should follow PEP 8.

## Variables and Functions

Use `snake_case`.

```python
user_id = 10

def get_user_by_email():
    pass
```

## Classes

Use `PascalCase`.

```python
class UserService:
    pass
```

## Constants

Use `UPPER_SNAKE_CASE`.

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30
MAX_LOGIN_ATTEMPTS = 5
```

## Modules and Files

Use lowercase with underscores where necessary.

```text
auth_service.py
user_repository.py
password_validator.py
```

---

# 5. Type Hints

Type hints should be used throughout backend code.

Example:

```python
def get_user(user_id: UUID) -> User | None:
    pass
```

For function parameters and return values, use meaningful types whenever practical.

Avoid unnecessary untyped functions.

---

# 6. Pydantic Schemas

All API request and response data should use Pydantic schemas.

Recommended structure:

```text
schemas/
├── auth.py
├── user.py
└── admin.py
```

Example:

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

Do not pass arbitrary dictionaries between API, service, and repository layers when a defined schema or model is appropriate.

---

# 7. SQLAlchemy Models

Database models belong in the `models/` directory.

Example:

```text
models/
├── user.py
├── profile.py
├── session.py
└── audit_log.py
```

Models should primarily represent database structure and relationships.

Business logic should not be unnecessarily placed inside database models.

---

# 8. Layered Backend Architecture

The backend should follow a layered structure:

```text
API / Route
     ↓
Schema Validation
     ↓
Service
     ↓
Repository
     ↓
Database Model
     ↓
PostgreSQL
```

Each layer should have a clear responsibility.

---

# 9. API Routes

Routes should remain thin.

Routes should primarily handle:

* HTTP requests.
* Request validation through schemas.
* Authentication dependencies.
* Calling appropriate services.
* Returning API responses.

Avoid placing complex business logic inside routes.

### Avoid

```text
Route
 ├── Validate password
 ├── Query database
 ├── Generate token
 ├── Send email
 └── Create session
```

### Prefer

```text
Route
   ↓
Schema
   ↓
AuthService
   ↓
Repository
   ↓
Database
```

---

# 10. Services

Services contain application and business logic.

Examples:

```text
AuthService
UserService
SessionService
AdminService
```

Services should coordinate operations between repositories and other required components.

Example responsibilities of `AuthService`:

* Validate login credentials.
* Create authentication sessions.
* Generate authentication tokens.
* Handle registration logic.
* Coordinate email verification.

---

# 11. Repositories

Repositories contain database-access logic.

Examples:

```text
UserRepository
SessionRepository
AuditLogRepository
```

Repositories should handle operations such as:

* Creating records.
* Finding records.
* Updating records.
* Deleting records where permitted.
* Querying related data.

Avoid placing database queries throughout routes.

---

# 12. Dependency Injection

FastAPI dependency injection should be used for common application dependencies.

Examples:

```python
Depends(get_db)
Depends(get_current_user)
Depends(require_admin)
```

Dependencies may be used for:

* Database sessions.
* Current authenticated user.
* Authentication.
* Role authorization.
* Common request dependencies.

---

# 13. API Naming Conventions

Use REST-style resource naming.

Resource collections should use plural nouns.

Good:

```text
/api/v1/users
/api/v1/admin/users
```

Authentication operations may use action-based endpoints:

```text
/api/v1/auth/login
/api/v1/auth/logout
/api/v1/auth/register
/api/v1/auth/verify-email
```

Use lowercase paths with hyphens where appropriate.

Avoid inconsistent naming such as:

```text
/api/GetUsers
/api/userData
/api/get_user
```

---

# 14. HTTP Methods

Use HTTP methods according to the operation.

| Method | Purpose                        |
| ------ | ------------------------------ |
| GET    | Retrieve data                  |
| POST   | Create or trigger an operation |
| PUT    | Replace/update a resource      |
| PATCH  | Partially update a resource    |
| DELETE | Remove/revoke a resource       |

Examples:

```text
POST   /api/v1/auth/login
POST   /api/v1/auth/register
GET    /api/v1/users/me
PUT    /api/v1/users/me
PATCH  /api/v1/admin/users/{user_id}/deactivate
DELETE /api/v1/users/me/sessions/{session_id}
```

---

# 15. API Response Format

API responses should follow the agreed project response structure.

## Success

```json
{
  "success": true,
  "message": "Operation successful.",
  "data": {}
}
```

## Error

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message."
  }
}
```

Responses should remain consistent across the application.

---

# 16. API Error Codes

Use uppercase descriptive error codes.

Examples:

```text
INVALID_CREDENTIALS
EMAIL_ALREADY_EXISTS
USERNAME_ALREADY_EXISTS
ACCOUNT_DEACTIVATED
EMAIL_NOT_VERIFIED
INVALID_RESET_TOKEN
RESET_TOKEN_EXPIRED
USER_NOT_FOUND
INSUFFICIENT_PERMISSIONS
VALIDATION_ERROR
```

Error messages should be understandable without exposing internal implementation details.

---

# 17. Exception Handling

Do not expose raw Python, SQLAlchemy, or database exceptions to API clients.

### Avoid

```text
sqlalchemy.exc.IntegrityError
```

being returned directly to the client.

Instead:

1. Catch expected exceptions.
2. Log appropriate technical details internally.
3. Return a controlled API error.
4. Avoid exposing sensitive implementation details.

---

# 18. React Naming Conventions

React components should use `PascalCase`.

Examples:

```text
LoginForm.jsx
RegisterForm.jsx
ProfilePage.jsx
AdminUsersPage.jsx
DeactivateUserModal.jsx
```

Functions and variables should use `camelCase`.

Examples:

```javascript
handleLogin()
getUserProfile()
isLoading
currentUser
```

Boolean variables should use meaningful prefixes when appropriate:

```javascript
isLoading
isAuthenticated
isActive
hasPermission
```

---

# 19. React Component Structure

Each component should have one clear responsibility.

Avoid extremely large components.

### Avoid

```text
AdminDashboard.jsx
    2000+ lines
```

### Prefer

```text
AdminDashboard.jsx
UserTable.jsx
UserFilters.jsx
DeactivateUserModal.jsx
```

Reusable UI logic should be extracted into components or hooks when appropriate.

---

# 20. Frontend API Communication

API communication should be separated from UI components.

Recommended structure:

```text
services/
├── api/
│   ├── authApi.js
│   ├── userApi.js
│   └── adminApi.js
```

Components should call service functions rather than repeatedly writing raw HTTP requests.

Example:

```text
LoginPage
    ↓
authApi.login()
    ↓
POST /api/v1/auth/login
```

This keeps API communication centralized and easier to maintain.

---

# 21. Authentication State

Authentication state should have one consistent source of truth.

Recommended structure:

```text
context/
└── AuthContext.jsx
```

Authentication state may manage:

* Current user.
* Authentication status.
* User role.
* Login state.
* Logout.
* Token/session state.

Avoid maintaining separate conflicting authentication states across multiple components.

---

# 22. Protected Routes

Frontend protected routes should be used to control the user interface.

Examples:

```text
/student/*
/teacher/*
/admin/*
```

However, frontend route protection is **not a security mechanism**.

Backend authorization must always verify:

* Authentication.
* User identity.
* User role.
* Resource permissions.

The backend remains the security boundary.

---

# 23. Form Validation

Validation should be performed on both frontend and backend.

```text
Frontend Validation
        +
Backend Validation
```

Frontend validation provides immediate feedback to users.

Backend validation is mandatory because frontend validation can be bypassed.

---

# 24. Environment Variables

Environment-specific configuration should use environment variables.

Example:

```text
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
VITE_API_BASE_URL
```

Never commit actual secrets.

Do not place private backend secrets in frontend environment variables.

Anything exposed through the frontend build should be considered public.

Use:

```text
.env.example
```

to document required variables without exposing their actual values.

---

# 25. Comments

Comments should explain **why**, not simply repeat **what** the code does.

### Avoid

```python
# Increment i
i += 1
```

### Prefer

```python
# Revoke active sessions so a deactivated account
# cannot continue using an existing session.
```

Do not add unnecessary comments to obvious code.

---

# 26. Functions and Methods

Functions should generally perform one logical task.

Avoid very large functions containing multiple unrelated responsibilities.

### Avoid

```text
register_user()
 ├── validate everything
 ├── create database records
 ├── generate tokens
 ├── send email
 ├── create session
 └── write audit log
```

### Prefer

```text
validate_registration()
create_user()
create_verification_token()
send_verification_email()
create_session()
create_audit_log()
```

The service layer can coordinate these operations.

---

# 27. DRY Principle

Follow the **Don't Repeat Yourself (DRY)** principle.

Common logic should be centralized where appropriate.

Examples:

* Password validation.
* Authentication dependencies.
* Role checking.
* Error formatting.
* API client configuration.
* Common validation.
* Reusable React components.

Do not create unnecessary abstractions for code that is only used once.

---

# 28. Security Coding Rules

Never:

```text
print(password)
print(jwt)
print(reset_token)
log(secret)
return password_hash
```

Never hard-code:

```text
Database passwords
JWT secrets
SMTP passwords
API keys
Private credentials
```

Passwords must be securely hashed before storage.

Sensitive tokens should be handled carefully and should not be unnecessarily logged or exposed.

Security-sensitive operations should be recorded through the project's audit logging mechanism where required.

---

# 29. Database Coding Rules

The backend should use:

```text
SQLAlchemy
    +
Alembic
```

Database schema changes must be performed through migrations.

Example:

```bash
alembic revision --autogenerate -m "add session table"
```

Review the generated migration before applying it.

Apply migrations using:

```bash
alembic upgrade head
```

Do not manually modify the database schema in a way that is not represented by a migration.

---

# 30. Testing Conventions

Backend test files should use descriptive names.

Examples:

```text
tests/
├── test_auth.py
├── test_users.py
├── test_sessions.py
└── test_admin.py
```

Test function names should describe the expected behavior.

Example:

```python
def test_login_rejects_deactivated_user():
    pass
```

Another example:

```python
def test_registration_rejects_duplicate_email():
    pass
```

---

# 31. Epic 1 Testing Requirements

Important User Management tests should cover:

### Registration

* Registration succeeds with valid data.
* Duplicate email is rejected.
* Duplicate username is rejected.
* Invalid password is rejected.
* Invalid input is rejected.

### Email Verification

* Valid verification token works.
* Invalid verification token is rejected.
* Expired verification token is rejected.
* Verification token cannot be reused where applicable.

### Login

* Valid credentials succeed.
* Invalid credentials are rejected.
* Unverified account is handled according to the requirements.
* Deactivated account cannot log in.

### Session Management

* Session is created after successful authentication.
* Logout revokes the session.
* Revoked session cannot be used.
* Expired session is rejected.

### Password Reset

* Password reset request succeeds.
* Password reset does not reveal whether an account exists.
* Invalid reset token is rejected.
* Expired reset token is rejected.
* Reset token cannot be reused.

### Role-Based Access Control

* Admin can perform admin operations.
* Non-admin cannot perform admin operations.
* Unauthorized users cannot access protected endpoints.

---

# 32. Import Organization

Python imports should generally be organized as:

```text
1. Standard library
2. Third-party libraries
3. Local application imports
```

Example:

```python
from datetime import datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
```

Remove unused imports.

Avoid unnecessary wildcard imports.

---

# 33. Formatting and Linting

The project should use automated tools to maintain consistent code quality.

## Backend

Recommended:

```text
Ruff
```

## Frontend

Recommended:

```text
ESLint
Prettier
```

Tool configuration should be committed to the repository so all team members use consistent settings.

---

# 34. Code Quality Before Pull Request

Before creating a Pull Request, each developer should:

```text
Format
   ↓
Lint
   ↓
Run Tests
   ↓
Review Changes
   ↓
Push
   ↓
Create Pull Request
```

The developer should verify:

* No unnecessary files are included.
* No debugging statements remain.
* No secrets are included.
* Tests pass.
* Code follows project conventions.
* Documentation is updated if required.

---

# 35. File Organization

Developers must follow the agreed project structure.

## Backend

```text
backend/
└── app/
    ├── api/
    ├── core/
    ├── models/
    ├── schemas/
    ├── repositories/
    ├── services/
    ├── utils/
    └── tests/
```

## Frontend

```text
frontend/
└── src/
    ├── components/
    ├── pages/
    ├── layouts/
    ├── services/
    ├── hooks/
    ├── context/
    ├── routes/
    └── utils/
```

Do not create random files or directories without a clear purpose.

---

# 36. Jira and Git Traceability

Development work should remain traceable to Jira tasks.

Where practical, include the Jira issue ID in:

* Feature branch name.
* Commit message.
* Pull Request title.
* Pull Request description.

Example:

```text
Jira:
TA-101 — User Registration
```

Branch:

```text
feature/TA-101-user-registration
```

Commit:

```text
feat(auth): TA-101 implement user registration
```

Pull Request:

```text
feat(auth): implement user registration [TA-101]
```

This provides a clear relationship between project requirements and implementation.

---

# 37. Code Ownership

Each developer is responsible for the quality of the code they modify.

However, ownership does not prevent other team members from reviewing or improving the code.

Developers should:

* Keep changes within their assigned task.
* Inform the relevant team member before modifying another person's active work.
* Avoid overwriting another developer's changes.
* Communicate when shared files or interfaces need modification.

---

# 38. Avoid Unnecessary Changes

A feature branch should contain only changes related to its assigned task.

Avoid including:

* Unrelated formatting changes.
* Unrelated refactoring.
* Temporary files.
* Debugging code.
* Personal configuration.
* Changes to another developer's feature without agreement.

Smaller Pull Requests are easier to review and merge.

---

# 39. Development Consistency

Team members should not introduce different approaches to the same problem without discussion.

For example, if the project already has:

```text
AuthService
```

do not create another unrelated authentication mechanism.

Before introducing a new pattern, library, dependency, or architectural approach, discuss it with the team.

---

# 40. Final Responsibility Rule

When deciding where code belongs, use this rule:

```text
HTTP handling
      ↓
API / Route

Request validation
      ↓
Pydantic Schema

Business logic
      ↓
Service

Database access
      ↓
Repository

Database structure
      ↓
SQLAlchemy Model

Authentication / Security
      ↓
Core / Security

Reusable UI
      ↓
Component

Page-level UI
      ↓
Page

API communication
      ↓
API Service

Shared React state
      ↓
Context / Hook
```

This separation should be maintained throughout Epic 1 and subsequent development.

---

# 41. Final Coding Standard

Before submitting code, every developer should ask:

```text
Is it readable?
Is it secure?
Is it tested?
Is it reusable?
Is it consistent with the architecture?
Is it consistent with the API contract?
Is it consistent with the database design?
Is it linked to the correct Jira task?
Does it contain unnecessary changes?
```

If the answer is yes to all applicable questions, the code is ready for review.

The goal is not to write the most complicated code.

The goal is to build a **secure, maintainable, consistent, and trustworthy system as a team**.
