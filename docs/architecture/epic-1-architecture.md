# Epic 1: User Management Module — Architecture

**Project:** Trustworthy TA Agent
**Epic:** Epic 1 — User Management Module
**Document Version:** 1.0
**Status:** Baseline

---

## 1. Overview

The User Management Module is responsible for managing user registration, authentication, authorization, session management, profile management, and account activation/deactivation.

The module provides secure access to the Trustworthy TA Agent platform for three primary roles:

* Student
* Teacher
* Admin

The architecture separates frontend presentation, backend business logic, authentication/security, and database access to improve maintainability, security, and scalability.

---

## 2. Architecture Goals

The architecture of Epic 1 aims to:

* Provide secure user authentication and authorization.
* Separate frontend and backend responsibilities.
* Enforce role-based access control.
* Protect user credentials and sensitive information.
* Provide reusable authentication middleware.
* Support future expansion of the platform.
* Maintain clear separation between API, business logic, and database operations.
* Allow the User Management Module to integrate with other project modules.

---

## 3. Technology Stack

| Layer                   | Technology         |
| ----------------------- | ------------------ |
| Frontend                | React.js           |
| Backend                 | FastAPI (Python)   |
| Authentication          | JWT                |
| Password Security       | Password hashing   |
| Database                | PostgreSQL         |
| API Communication       | REST API           |
| Development Environment | Visual Studio Code |
| Version Control         | Git + GitHub       |
| API Testing             | Postman            |
| Containerization        | Docker             |

The project proposal identifies React.js for the frontend, FastAPI/Python for the backend, PostgreSQL as a database option, and Docker among the development tools.

---

## 4. High-Level Architecture

The User Management Module follows a layered architecture:

```text
┌─────────────────────────────────────────────┐
│                  Frontend                   │
│                 React.js                    │
│                                             │
│  Registration │ Login │ Profile │ Dashboard │
└──────────────────────┬──────────────────────┘
                       │
                       │ REST API / HTTP
                       ▼
┌─────────────────────────────────────────────┐
│                 Backend                     │
│                 FastAPI                     │
│                                             │
│  API Routes / Controllers                   │
│            ↓                                │
│  Authentication & Authorization             │
│            ↓                                │
│  Services / Business Logic                 │
│            ↓                                │
│  Data Access Layer                          │
└──────────────────────┬──────────────────────┘
                       │
                       │ Database Queries
                       ▼
┌─────────────────────────────────────────────┐
│                PostgreSQL                   │
│                                             │
│ Users │ Roles │ Profiles │ Sessions │ Logs  │
└─────────────────────────────────────────────┘
```

---

## 5. Frontend Architecture

The frontend is responsible for user interaction and presentation.

### 5.1 Main Components

The following React components/pages will be required for Epic 1:

```text
frontend/
└── src/
    ├── components/
    │   ├── auth/
    │   │   ├── LoginForm
    │   │   ├── RegistrationForm
    │   │   ├── ForgotPasswordForm
    │   │   └── ResetPasswordForm
    │   │
    │   └── profile/
    │       ├── ProfileView
    │       └── ProfileForm
    │
    ├── pages/
    │   ├── Login
    │   ├── Register
    │   ├── ForgotPassword
    │   ├── ResetPassword
    │   └── Profile
    │
    ├── services/
    │   └── authService
    │
    ├── context/
    │   └── AuthContext
    │
    └── routes/
        └── ProtectedRoutes
```

### 5.2 Frontend Responsibilities

The frontend will:

* Display registration and login forms.
* Validate basic user input.
* Send authentication requests to the backend.
* Store authentication state securely.
* Redirect users according to their role.
* Protect frontend routes.
* Display user profile information.
* Allow users to update their profile.
* Provide logout functionality.
* Display appropriate success and error messages.

Frontend validation will improve user experience, but all security-sensitive validation must also be performed by the backend.

---

## 6. Backend Architecture

The backend will be implemented using FastAPI.

The backend will handle:

* User registration.
* Input validation.
* Password hashing.
* Login and authentication.
* JWT generation and validation.
* Role-based authorization.
* Password reset.
* Session management.
* Profile management.
* Account activation/deactivation.
* Authentication-related audit logging.

### 6.1 Proposed Backend Structure

```text
backend/
└── app/
    ├── main.py
    │
    ├── api/
    │   └── routes/
    │       ├── auth.py
    │       ├── users.py
    │       └── admin.py
    │
    ├── models/
    │   ├── user.py
    │   ├── role.py
    │   └── session.py
    │
    ├── schemas/
    │   ├── auth.py
    │   ├── user.py
    │   └── profile.py
    │
    ├── services/
    │   ├── auth_service.py
    │   ├── user_service.py
    │   ├── token_service.py
    │   └── email_service.py
    │
    ├── middleware/
    │   ├── auth.py
    │   └── rate_limit.py
    │
    ├── security/
    │   ├── password.py
    │   └── jwt.py
    │
    ├── database/
    │   ├── connection.py
    │   └── repositories/
    │
    └── tests/
        ├── test_auth.py
        ├── test_users.py
        └── test_admin.py
```

This structure keeps API routes, business logic, security, database access, and testing separate.

---

## 7. Authentication Flow

The authentication process will use JWT-based authentication.

### 7.1 Registration Flow

```text
User
 │
 │ Registration Data
 ▼
React Registration Form
 │
 │ POST /auth/register
 ▼
FastAPI
 │
 ├── Validate Input
 │
 ├── Check Existing Email
 │
 ├── Hash Password
 │
 ├── Create User
 │
 └── Generate Verification Token
 │
 ▼
Database
 │
 └── Store User
 │
 ▼
Email Verification
 │
 ▼
User Activates Account
```

### 7.2 Login Flow

```text
User
 │
 │ Email + Password
 ▼
React Login Form
 │
 │ POST /auth/login
 ▼
FastAPI
 │
 ├── Find User
 │
 ├── Verify Password
 │
 ├── Check Account Status
 │
 ├── Determine User Role
 │
 └── Generate JWT
 │
 ▼
React Application
 │
 └── Authenticated Session
```

---

## 8. JWT Authentication

JWT will be used to authenticate requests to protected API endpoints.

The token will contain information required to identify the authenticated user, such as:

* User ID
* User role
* Token expiration time

Protected requests will include the JWT in the authorization header.

Example:

```text
Authorization: Bearer <JWT_TOKEN>
```

The backend authentication middleware will:

1. Extract the token.
2. Validate the token.
3. Check token expiration.
4. Identify the user.
5. Attach the authenticated user to the request.
6. Allow or reject the request.

---

## 9. Role-Based Access Control

The system will support:

```text
                 User
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
       Student   Teacher   Admin
```

### Student

Students will be allowed to access student-specific functionality.

### Teacher

Teachers will be allowed to access teaching and course-related functionality.

### Admin

Admins will have access to user management and administrative functionality.

Authorization will be enforced on the **backend**, not only through frontend route restrictions.

Example:

```text
Request
   │
   ▼
JWT Authentication
   │
   ▼
Identify User
   │
   ▼
Check Role
   │
   ├── Authorized ──► Continue
   │
   └── Unauthorized ► 403 Forbidden
```

---

## 10. Protected Routes

Protected API endpoints will require authentication.

Examples:

```text
Public Routes
├── POST /auth/register
├── POST /auth/login
├── POST /auth/forgot-password
└── POST /auth/reset-password

Authenticated Routes
├── POST /auth/logout
├── GET  /users/me
├── PUT  /users/me
└── PUT  /users/me/profile

Admin Routes
├── GET  /admin/users
├── PATCH /admin/users/{user_id}/activate
└── PATCH /admin/users/{user_id}/deactivate
```

The exact API contract will be documented separately in:

```text
docs/api/epic-1-api-contract.md
```

---

## 11. Password Security

Passwords must never be stored as plain text.

The registration process will:

```text
Plain Password
      │
      ▼
Password Hashing
      │
      ▼
Password Hash
      │
      ▼
Database
```

During login:

```text
Entered Password
      │
      ▼
Password Verification
      │
      ▼
Stored Password Hash
```

The system will also enforce password security requirements during registration and password reset.

---

## 12. Password Reset Architecture

The password reset process will use a time-limited reset token.

```text
User
 │
 │ Forgot Password
 ▼
POST /auth/forgot-password
 │
 ▼
Generate Reset Token
 │
 ▼
Send Email
 │
 ▼
User Opens Link
 │
 ▼
Reset Password
 │
 ▼
Validate Token
 │
 ├── Valid ──────► Update Password
 │
 └── Expired ────► Reject Request
```

The reset link will expire after 24 hours according to the Epic 1 requirements.

---

## 13. Session Management

The system will manage authenticated sessions using JWT-based authentication.

The session management design will support:

* Secure authentication.
* Token expiration.
* Logout.
* Inactivity timeout.
* Protection of authenticated routes.

The Epic 1 requirements specify a 30-minute inactivity timeout.

---

## 14. User Profile Architecture

User profile information will be managed separately from authentication logic where appropriate.

The profile may contain:

### Common Information

* Name
* Email
* Profile picture

### Teacher Information

* Department
* Expertise

### Student Information

* Courses
* Learning progress

The backend will ensure users can only modify their own permitted profile information, while administrative actions will require appropriate privileges.

---

## 15. Account Activation & Deactivation

Administrators will be able to activate or deactivate user accounts.

```text
Admin
 │
 │ Activate / Deactivate
 ▼
Admin API
 │
 ▼
Authorization Check
 │
 ▼
Update Account Status
 │
 ▼
Database
```

When an account is deactivated:

* The account remains stored.
* The account status changes to inactive.
* The user cannot log in.
* The action is recorded in the audit log.
* The user is notified.

---

## 16. Audit Logging

Security-sensitive actions should be recorded for accountability.

The system will log events such as:

* User registration.
* Successful login.
* Failed login attempts.
* Password reset.
* Logout.
* Account activation.
* Account deactivation.
* Important profile/security changes.

Example:

```text
Audit Log
├── User ID
├── Action
├── Timestamp
├── Result
└── Additional Metadata
```

---

## 17. Database Architecture

PostgreSQL will be used for structured user management data.

The detailed database design will be documented separately in:

```text
docs/database/epic-1-database.md
```

The initial logical entities are:

```text
User
 │
 ├── Role
 │
 ├── Profile
 │
 ├── Sessions
 │
 ├── Password Reset Tokens
 │
 └── Audit Logs
```

A user's role determines which protected resources and operations they can access.

---

## 18. Security Architecture

Security will be implemented at multiple layers:

```text
Frontend
   │
   ▼
API Validation
   │
   ▼
Authentication
   │
   ▼
Authorization / RBAC
   │
   ▼
Business Logic
   │
   ▼
Database
```

Security measures include:

* Password hashing.
* JWT authentication.
* Role-based authorization.
* Backend request validation.
* Protected API routes.
* Rate limiting for authentication endpoints.
* Secure session handling.
* Account status verification.
* Audit logging.
* Protection of environment variables and secrets.

---

## 19. Error Handling

The backend will return appropriate HTTP status codes for different conditions.

| Situation                                   | HTTP Status |
| ------------------------------------------- | ----------: |
| Successful request                          |         200 |
| Account successfully created                |         201 |
| Invalid input                               |         400 |
| Authentication required/invalid credentials |         401 |
| Insufficient permissions                    |         403 |
| Resource not found                          |         404 |
| Duplicate email                             |         409 |
| Server error                                |         500 |

Error responses should provide useful information without exposing sensitive security details.

---

## 20. Integration With Other Modules

Epic 1 provides authentication and authorization services that will be reused by future modules.

```text
                 User Management
                       │
             Authentication / RBAC
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   TA Management   Course/KB       AI TA
     Module          Module         Module
```

Future modules will use the authenticated user's identity and role to determine access to courses, AI teaching assistants, resources, assessments, and other functionality.

The overall project includes separate User Management, TA Management, Course & Knowledge Base Management, AI Teaching Assistant, and other modules.

---

## 21. Testing Architecture

Epic 1 will include testing at multiple levels.

### Unit Testing

Test individual services and functions:

* Password hashing.
* Password verification.
* JWT generation.
* JWT validation.
* Role checking.
* User validation.

### API Testing

Test endpoints such as:

* Registration.
* Login.
* Logout.
* Password reset.
* Profile management.
* Account activation/deactivation.

### Integration Testing

Test interactions between:

```text
Frontend
   ↓
FastAPI
   ↓
Authentication Services
   ↓
Database
```

### Security Testing

Test:

* Unauthorized access.
* Invalid tokens.
* Expired tokens.
* Incorrect roles.
* Brute-force protection.
* Access to deactivated accounts.

---

## 22. Architecture Summary

The Epic 1 architecture provides a secure and modular foundation for the Trustworthy TA Agent.

The main architectural principles are:

* React.js handles presentation and user interaction.
* FastAPI provides REST APIs and backend business logic.
* JWT provides authentication.
* Role-based access control protects role-specific functionality.
* PostgreSQL stores structured user data.
* Security-sensitive operations are handled by the backend.
* Authentication functionality is designed for reuse by future modules.
* Testing is performed at unit, integration, API, and security levels.

This architecture allows Epic 1 to serve as the authentication and authorization foundation for the remaining Trustworthy TA Agent modules.

