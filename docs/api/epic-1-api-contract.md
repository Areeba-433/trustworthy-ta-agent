# Epic 1: User Management Module — API Contract

**Project:** Trustworthy TA Agent
**Epic:** Epic 1 — User Management Module
**API Type:** REST API
**Backend:** FastAPI
**Frontend:** React.js
**Database:** PostgreSQL
**Authentication:** JWT
**API Version:** v1
**Document Version:** 1.0
**Status:** Baseline

---

# 1. Overview

This document defines the REST API contract for the User Management Module of the Trustworthy TA Agent platform.

The API provides endpoints for:

* User registration
* Email verification
* User login
* Logout
* Password reset
* Session management
* User profile management
* Role-based access control
* Account activation and deactivation
* User management by administrators

The API will be implemented using FastAPI and consumed by the React.js frontend.

---

# 2. Base URL

All API endpoints will use the following base path:

```text
/api/v1
```

Authentication endpoints will be grouped under:

```text
/api/v1/auth
```

User endpoints:

```text
/api/v1/users
```

Admin endpoints:

```text
/api/v1/admin
```

---

# 3. Authentication

Protected endpoints require a valid JWT access token.

The token must be sent using the HTTP Authorization header:

```http
Authorization: Bearer <access_token>
```

Requests without a valid authentication token will receive:

```http
401 Unauthorized
```

Requests from authenticated users without sufficient permissions will receive:

```http
403 Forbidden
```

---

# 4. API Response Format

Successful responses should return JSON.

Example:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {}
}
```

Error responses should follow a consistent structure:

```json
{
  "success": false,
  "message": "Error message",
  "detail": "Additional information"
}
```

Sensitive information such as passwords, password hashes, JWT secrets, and raw reset tokens must never be returned in API responses.

---

# 5. Authentication Endpoints

## 5.1 User Registration

### Endpoint

```http
POST /api/v1/auth/register
```

### Authentication

Public

### Description

Creates a new user account.

### Request Body

```json
{
  "first_name": "Ali",
  "last_name": "Khan",
  "username": "alikhan",
  "email": "ali@example.com",
  "password": "SecurePassword123",
  "role": "student"
}
```

### Validation

* `first_name` is required.
* `last_name` is required.
* `username` is required and must be unique.
* `email` is required and must be unique.
* `password` must meet security requirements.
* `role` must be a valid system role.
* Password must not be stored in plain text.

### Success Response

**HTTP 201 Created**

```json
{
  "success": true,
  "message": "Registration successful. Please verify your email.",
  "data": {
    "user_id": "uuid",
    "email": "ali@example.com",
    "role": "student",
    "is_verified": false
  }
}
```

### Error Responses

**400 Bad Request**

```json
{
  "success": false,
  "message": "Invalid registration data"
}
```

**409 Conflict**

```json
{
  "success": false,
  "message": "Email address is already registered"
}
```

---

# 6. Email Verification

## 6.1 Verify Email

### Endpoint

```http
POST /api/v1/auth/verify-email
```

### Authentication

Public

### Description

Verifies a user's email address using the verification token sent after registration.

### Request Body

```json
{
  "token": "verification-token"
}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Email verified successfully"
}
```

### Error Responses

**400 Bad Request**

```json
{
  "success": false,
  "message": "Invalid or expired verification token"
}
```

---

# 7. User Login

## 7.1 Login

### Endpoint

```http
POST /api/v1/auth/login
```

### Authentication

Public

### Description

Authenticates a registered user and returns an access token.

### Request Body

```json
{
  "email": "ali@example.com",
  "password": "SecurePassword123",
  "remember_me": true
}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "jwt-access-token",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
      "id": "uuid",
      "email": "ali@example.com",
      "role": "student"
    }
  }
}
```

### Error Responses

**401 Unauthorized**

```json
{
  "success": false,
  "message": "Invalid email or password"
}
```

**403 Forbidden**

```json
{
  "success": false,
  "message": "Account is inactive"
}
```

---

# 8. User Logout

## 8.1 Logout

### Endpoint

```http
POST /api/v1/auth/logout
```

### Authentication

Required

### Description

Logs the authenticated user out and revokes the associated session/token.

### Request Body

```json
{}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Logout successful"
}
```

### Error Response

**401 Unauthorized**

```json
{
  "success": false,
  "message": "Authentication required"
}
```

---

# 9. Password Reset

## 9.1 Request Password Reset

### Endpoint

```http
POST /api/v1/auth/forgot-password
```

### Authentication

Public

### Description

Requests a password reset link for a registered email address.

### Request Body

```json
{
  "email": "ali@example.com"
}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "If the account exists, a password reset link has been sent"
}
```

The response should not reveal whether an email address is registered.

---

## 9.2 Reset Password

### Endpoint

```http
POST /api/v1/auth/reset-password
```

### Authentication

Public

### Description

Resets the user's password using a valid password reset token.

### Request Body

```json
{
  "token": "password-reset-token",
  "new_password": "NewSecurePassword123"
}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Password reset successful"
}
```

### Error Responses

**400 Bad Request**

```json
{
  "success": false,
  "message": "Invalid or expired reset token"
}
```

**422 Unprocessable Entity**

```json
{
  "success": false,
  "message": "Password does not meet security requirements"
}
```

---

# 10. User Profile Endpoints

## 10.1 Get Current User

### Endpoint

```http
GET /api/v1/users/me
```

### Authentication

Required

### Description

Returns the profile and basic account information of the authenticated user.

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "ali@example.com",
    "username": "alikhan",
    "role": "student",
    "is_active": true,
    "is_verified": true,
    "profile": {
      "first_name": "Ali",
      "last_name": "Khan",
      "profile_picture_url": null
    }
  }
}
```

---

## 10.2 Update Current User Profile

### Endpoint

```http
PUT /api/v1/users/me
```

### Authentication

Required

### Description

Updates the authenticated user's permitted profile information.

### Request Body

```json
{
  "first_name": "Ali",
  "last_name": "Khan",
  "profile_picture_url": "https://example.com/profile.jpg"
}
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Profile updated successfully",
  "data": {
    "first_name": "Ali",
    "last_name": "Khan",
    "profile_picture_url": "https://example.com/profile.jpg"
  }
}
```

---

# 11. Role-Based Access Control

The API supports three roles:

```text
student
teacher
admin
```

Access must be enforced by the backend.

| Endpoint Group   | Student | Teacher |  Admin  |
| ---------------- | :-----: | :-----: | :-----: |
| Register         |  Public |  Public |  Public |
| Login            |  Public |  Public |  Public |
| Logout           |    ✓    |    ✓    |    ✓    |
| Own Profile      |    ✓    |    ✓    |    ✓    |
| Student Features |    ✓    |    ✗    | Depends |
| Teacher Features |    ✗    |    ✓    | Depends |
| User Management  |    ✗    |    ✗    |    ✓    |

Frontend route protection must not be treated as the security mechanism. Authorization must always be verified by the backend.

---

# 12. Admin User Management

## 12.1 Get Users

### Endpoint

```http
GET /api/v1/admin/users
```

### Authentication

Required — Admin only

### Description

Returns a list of registered users.

### Query Parameters

```text
?page=1
&limit=20
&role=student
&is_active=true
```

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "data": {
    "users": [
      {
        "id": "uuid",
        "email": "ali@example.com",
        "username": "alikhan",
        "role": "student",
        "is_active": true,
        "is_verified": true
      }
    ],
    "page": 1,
    "limit": 20,
    "total": 1
  }
}
```

---

## 12.2 Activate User Account

### Endpoint

```http
PATCH /api/v1/admin/users/{user_id}/activate
```

### Authentication

Required — Admin only

### Description

Activates a previously deactivated user account.

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "User account activated successfully"
}
```

---

## 12.3 Deactivate User Account

### Endpoint

```http
PATCH /api/v1/admin/users/{user_id}/deactivate
```

### Authentication

Required — Admin only

### Description

Deactivates a user account without deleting the user's data.

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "User account deactivated successfully"
}
```

### Behavior

After deactivation:

* The user cannot log in.
* The account remains stored in the database.
* The account status is set to inactive.
* The action is recorded in the audit log.
* The user is notified.

---

# 13. Session Management

## 13.1 Get Active Sessions

### Endpoint

```http
GET /api/v1/users/me/sessions
```

### Authentication

Required

### Description

Returns the authenticated user's active sessions.

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "data": [
    {
      "session_id": "uuid",
      "created_at": "2026-09-01T10:00:00Z",
      "last_activity_at": "2026-09-01T10:20:00Z",
      "expires_at": "2026-09-01T10:50:00Z"
    }
  ]
}
```

---

## 13.2 Revoke Session

### Endpoint

```http
DELETE /api/v1/users/me/sessions/{session_id}
```

### Authentication

Required

### Description

Revokes a specific session belonging to the authenticated user.

### Success Response

**HTTP 200 OK**

```json
{
  "success": true,
  "message": "Session revoked successfully"
}
```

---

# 14. HTTP Status Codes

The API will use standard HTTP status codes.

| Status | Meaning                            |
| -----: | ---------------------------------- |
|    200 | Request successful                 |
|    201 | Resource successfully created      |
|    400 | Bad request                        |
|    401 | Authentication required or invalid |
|    403 | Insufficient permissions           |
|    404 | Resource not found                 |
|    409 | Resource conflict                  |
|    422 | Validation error                   |
|    429 | Too many requests                  |
|    500 | Internal server error              |

---

# 15. Validation Rules

The backend must validate all incoming requests.

### Email

* Must be in a valid email format.
* Must be unique during registration.

### Username

* Must be unique.
* Must meet the defined username format.

### Password

* Must satisfy the defined password security policy.
* Must never be returned in an API response.
* Must never be stored in plain text.

### User Role

Only the following roles are valid:

```text
student
teacher
admin
```

Role assignment must be controlled by the backend. A normal user must not be able to grant themselves administrative privileges.

---

# 16. Rate Limiting

Rate limiting should be applied to security-sensitive endpoints.

The following endpoints should be rate limited:

```text
POST /auth/login
POST /auth/register
POST /auth/forgot-password
POST /auth/reset-password
POST /auth/verify-email
```

If the rate limit is exceeded:

**HTTP 429 Too Many Requests**

```json
{
  "success": false,
  "message": "Too many requests. Please try again later."
}
```

---

# 17. API Security Requirements

The API must:

* Use HTTPS in production.
* Require authentication for protected endpoints.
* Validate JWT tokens.
* Enforce role-based authorization on the backend.
* Validate all request data.
* Never return passwords or password hashes.
* Never expose secret keys.
* Avoid revealing whether an email exists during password-reset requests.
* Rate-limit authentication endpoints.
* Validate account status before allowing authentication.
* Record security-sensitive actions in audit logs.

---

# 18. Endpoint Summary

| Method | Endpoint                            | Access        | Purpose                |
| ------ | ----------------------------------- | ------------- | ---------------------- |
| POST   | `/auth/register`                    | Public        | Register user          |
| POST   | `/auth/verify-email`                | Public        | Verify email           |
| POST   | `/auth/login`                       | Public        | Authenticate user      |
| POST   | `/auth/logout`                      | Authenticated | Logout                 |
| POST   | `/auth/forgot-password`             | Public        | Request password reset |
| POST   | `/auth/reset-password`              | Public        | Reset password         |
| GET    | `/users/me`                         | Authenticated | Get own profile        |
| PUT    | `/users/me`                         | Authenticated | Update own profile     |
| GET    | `/users/me/sessions`                | Authenticated | View active sessions   |
| DELETE | `/users/me/sessions/{session_id}`   | Authenticated | Revoke session         |
| GET    | `/admin/users`                      | Admin         | List users             |
| PATCH  | `/admin/users/{user_id}/activate`   | Admin         | Activate account       |
| PATCH  | `/admin/users/{user_id}/deactivate` | Admin         | Deactivate account     |

---

# 19. Requirements Traceability

| User Story                  | API Endpoints                                                                           |
| --------------------------- | --------------------------------------------------------------------------------------- |
| User Registration           | `POST /auth/register`                                                                   |
| User Login & Authentication | `POST /auth/login`                                                                      |
| Password Reset              | `POST /auth/forgot-password`, `POST /auth/reset-password`                               |
| Logout & Session Management | `POST /auth/logout`, `GET /users/me/sessions`, `DELETE /users/me/sessions/{session_id}` |
| Role-Based Access Control   | Backend authorization across protected endpoints                                        |
| User Profile Management     | `GET /users/me`, `PUT /users/me`                                                        |
| User Account Deactivation   | Admin activate/deactivate endpoints                                                     |

---

# 20. API Documentation

FastAPI will provide automatically generated interactive API documentation.

The development API documentation will be available through the FastAPI application's Swagger UI.

The API implementation must remain consistent with this contract.

Any changes to endpoint names, request/response structures, authentication requirements, or status codes should be reflected in this document.

---

# 21. Related Documentation

* **Requirements:** `docs/requirements/epic-1-requirements.md`
* **Architecture:** `docs/architecture/epic-1-architecture.md`
* **Database:** `docs/database/epic-1-database.md`
* **Authentication & Security:** `docs/security/authentication.md`
* **Project Setup:** `docs/development/project-setup.md`
* **Git Workflow:** `docs/development/git-workflow.md`

---

# 22. API Contract Summary

The Epic 1 API provides the authentication and user-management foundation for the Trustworthy TA Agent.

The API follows these principles:

* RESTful endpoint design.
* JWT-based authentication.
* Backend-enforced RBAC.
* Consistent JSON responses.
* Standard HTTP status codes.
* Request validation.
* Secure password handling.
* Rate limiting for authentication endpoints.
* Audit logging for security-sensitive operations.
* Versioned API endpoints using `/api/v1`.
