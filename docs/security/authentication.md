# Trustworthy TA Agent

# Security & Authentication Specification

## Epic 1 — User Management Module

**Version:** 1.0
**Status:** Final
**Applies To:** Backend and Frontend
**Security Boundary:** FastAPI Backend

---

# 1. Purpose

This document defines the security and authentication standards for Epic 1 — User Management Module.

It establishes the required approach for:

* Authentication
* Password security
* JWT access tokens
* Server-side sessions
* Email verification
* Password recovery
* Role-Based Access Control (RBAC)
* Account activation/deactivation
* Audit logging
* CORS
* Secrets management
* Secure file uploads
* Security-related logging

All developers must follow this specification when implementing Epic 1.

A developer must not introduce a different authentication or authorization mechanism without team approval and corresponding documentation updates.

---

# 2. Security Objectives

Epic 1 security aims to provide:

1. Secure user authentication
2. Secure password storage
3. Email verification
4. Secure password recovery
5. JWT-based authentication
6. Server-side session tracking and revocation
7. Role-Based Access Control
8. Protection against unauthorized account access
9. Protection against common authentication attacks
10. Secure account deactivation
11. Auditability of security-sensitive actions
12. Protection of application secrets

---

# 3. Security Architecture

The authentication flow is:

```text
React Frontend
      │
      │ HTTPS
      ▼
FastAPI API
      │
      ▼
Authentication Dependency
      │
      ├── Validate JWT signature
      ├── Validate expiration
      ├── Extract user ID
      ├── Extract JTI
      └── Validate server-side session
      │
      ▼
Current User
      │
      ▼
Authorization / RBAC
      │
      ▼
Protected Endpoint
```

The **backend is the security boundary**.

Frontend authentication controls improve user experience but must never be treated as a replacement for backend authentication or authorization.

---

# 4. Authentication Method

The system shall use:

```text
JWT Access Token
        +
Server-Side Session
```

The JWT provides authenticated identity information.

The server-side session provides revocation and session-control capabilities.

This allows the application to invalidate authentication before the JWT naturally expires.

Server-side session tracking is required for:

* Logout
* Account deactivation
* Password reset
* Security incidents
* Forced session termination

A valid JWT alone is not sufficient to access protected resources.

---

# 5. Token Transport

The access token shall be transported using a cookie with:

```text
HttpOnly
Secure
SameSite
```

The JWT must not be stored in:

```text
localStorage
sessionStorage
```

This prevents normal client-side JavaScript from directly reading the authentication token.

Production authentication traffic must use HTTPS.

The exact cookie configuration must be centralized in the backend security configuration.

---

# 6. JWT Claims

The access token should contain only the minimum information required by the application.

Required claims:

```text
sub
role
jti
iat
exp
```

### `sub`

Contains the authenticated user's ID.

### `role`

Contains the user's current application role.

Supported Epic 1 roles:

```text
STUDENT
TEACHER
ADMIN
```

### `jti`

A unique JWT identifier.

The JTI is associated with the server-side session and is used during session validation and revocation.

### `iat`

The time at which the JWT was issued.

### `exp`

The expiration time of the JWT.

Sensitive information must not be placed inside JWT claims.

---

# 7. JWT Expiration

The default access-token lifetime is:

```text
30 minutes
```

The value must be configurable through environment variables.

Example:

```env
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

The backend must always validate the `exp` claim when processing a protected request.

---

# 8. Server-Side Sessions

Every successful login shall create a server-side session.

A session should contain:

```text
session_id
user_id
jti
created_at
last_activity_at
expires_at
revoked_at
```

The JWT's `jti` must correspond to the associated session.

The session record allows the backend to determine whether the JWT is still authorized.

---

# 9. Session Validation

Every protected request must follow this general flow:

```text
Incoming Request
      ↓
Read Authentication Cookie
      ↓
Validate JWT Signature
      ↓
Validate JWT Expiration
      ↓
Extract User ID
      ↓
Extract JTI
      ↓
Find Server-Side Session
      ↓
Check Session Revocation
      ↓
Check Session Expiration
      ↓
Check Inactivity
      ↓
Check User Account Status
      ↓
Authenticate User
      ↓
Apply Authorization / RBAC
      ↓
Protected Endpoint
```

A valid JWT without a valid server-side session must be rejected.

---

# 10. Session Inactivity

A session shall become invalid after:

```text
30 minutes of inactivity
```

The backend shall use:

```text
last_activity_at
```

to determine inactivity.

Session behavior must be consistent across all protected endpoints.

The inactivity policy must not be implemented differently by individual developers.

---

# 11. Logout

Endpoint:

```text
POST /api/v1/auth/logout
```

Logout shall:

1. Authenticate the current request.
2. Identify the current session/JTI.
3. Mark the session as revoked.
4. Clear the authentication cookie.
5. Return a successful response.

After logout, the previously issued JWT must not authorize protected API requests.

---

# 12. Password Storage

Passwords must never be stored as plaintext.

The system shall use:

```text
Argon2id
```

for password hashing.

The database stores:

```text
password_hash
```

Only the password hash is stored.

The original password must never be:

* Stored
* Logged
* Returned in an API response
* Included in audit metadata

---

# 13. Password Policy

The application shall enforce a centralized password policy.

Minimum requirement:

```text
At least 8 characters
```

The application should encourage the use of:

* Uppercase characters
* Lowercase characters
* Numbers
* Special characters

Registration, password change, and password reset must use the same password validation rules.

Password policy logic should be centralized rather than duplicated across endpoints.

Recommended location:

```text
backend/app/core/security.py
```

or another agreed security module.

---

# 14. Password Verification

During login:

```text
Entered Password
       ↓
Argon2id Verification
       ↓
Stored Password Hash
       ↓
Authentication Result
```

Password verification must use the approved password-hashing library.

Developers must not manually compare password strings or hashes.

---

# 15. Email Verification

Newly registered accounts must complete email verification according to the Epic 1 registration requirements.

General flow:

```text
User Registration
       ↓
Create User
       ↓
Generate Secure Verification Token
       ↓
Hash Token
       ↓
Store Token Hash
       ↓
Send Verification Email
       ↓
User Opens Verification Link
       ↓
Validate Token
       ↓
Mark Email as Verified
```

The verification process must not expose sensitive account information.

---

# 16. Verification Token Security

Email verification tokens must:

* Be cryptographically random
* Be sufficiently long
* Be stored as hashes
* Have an expiration time
* Be single-use

The raw verification token should only exist where required for delivery to the user.

Raw verification tokens must not be stored in the database or application logs.

---

# 17. Password Reset

Password reset shall use a secure, time-limited, single-use token.

General flow:

```text
Forgot Password
       ↓
Generate Secure Random Token
       ↓
Hash Token
       ↓
Store Token Hash
       ↓
Send Reset Email
       ↓
User Opens Reset Link
       ↓
Validate Token
       ↓
Set New Password
       ↓
Invalidate Token
       ↓
Revoke Existing Sessions
```

Password reset tokens expire after:

```text
24 hours
```

---

# 18. Password Reset Token Rules

A reset token must be:

* Cryptographically random
* Single-use
* Time-limited
* Stored as a hash
* Invalid after successful use

After a successful password reset, existing active sessions should be revoked.

This prevents previously authenticated sessions from continuing after a password compromise.

---

# 19. Forgot Password Account Enumeration Protection

The forgot-password endpoint must not reveal whether an email address is registered.

The API should return a generic response such as:

```json
{
  "success": true,
  "message": "If an account exists for this email, password reset instructions have been sent."
}
```

The response should remain the same whether the account exists or not.

This reduces the risk of user-account enumeration.

---

# 20. Login Security

The login system shall:

* Use generic invalid-credential messages
* Avoid revealing whether an email/username exists
* Reject invalid credentials
* Reject deactivated accounts
* Enforce email-verification requirements
* Never return password hashes
* Never log passwords
* Never return authentication secrets in normal responses

Authentication failures should not disclose unnecessary information to attackers.

---

# 21. Role-Based Access Control

Epic 1 supports:

```text
STUDENT
TEACHER
ADMIN
```

Authorization must be enforced by the backend.

Example:

```text
GET /api/v1/admin/users

STUDENT  → 403 Forbidden
TEACHER  → 403 Forbidden
ADMIN    → Allowed
```

Frontend role checks are not sufficient for security.

---

# 22. RBAC Implementation

FastAPI dependencies should be used for authorization.

Conceptual flow:

```text
get_current_user()
        ↓
require_role(ADMIN)
        ↓
Admin Endpoint
```

Role and permission checks should be implemented through reusable dependencies rather than manually duplicated across every endpoint.

---

# 23. Registration Role Restrictions

Public registration may create:

```text
STUDENT
TEACHER
```

Public users must not be allowed to create:

```text
ADMIN
```

Administrator accounts must be created through a controlled administrative mechanism.

The client must never be trusted to assign itself an administrator role.

---

# 24. Account Deactivation

When an administrator deactivates an account:

```text
is_active = false
```

The backend must also:

1. Revoke active sessions.
2. Prevent future login.
3. Record the action in the audit log.
4. Trigger the appropriate notification if implemented.

Account deactivation must not delete the user's historical data.

---

# 25. Account Activation

When an administrator activates an account:

```text
is_active = true
```

The user may authenticate again, subject to all other authentication requirements.

The activation action must be recorded in the audit log.

---

# 26. Audit Logging

Security-sensitive actions shall be recorded.

Examples:

```text
USER_REGISTERED
EMAIL_VERIFIED
LOGIN_SUCCESS
LOGIN_FAILED
LOGOUT
PASSWORD_RESET_REQUESTED
PASSWORD_RESET_COMPLETED
PASSWORD_CHANGED
PROFILE_UPDATED
ACCOUNT_ACTIVATED
ACCOUNT_DEACTIVATED
```

An audit record should contain information such as:

```text
id
actor_user_id
target_user_id
action
timestamp
ip_address
metadata
```

Only appropriate non-sensitive metadata should be stored.

Audit logs must never contain:

* Passwords
* Password hashes
* JWTs
* Raw reset tokens
* Raw verification tokens
* Database passwords
* API keys
* Other secrets

---

# 27. CORS

CORS must be explicitly configured.

Production must not use:

```python
allow_origins=["*"]
```

for authenticated APIs.

Allowed origins should be configured through environment variables.

Example:

```env
CORS_ORIGINS=https://your-frontend-domain.com
```

For local development, the frontend origin may be:

```text
http://localhost:5173
```

---

# 28. Secrets Management

The following must never be committed to Git:

```text
JWT secrets
Database passwords
SMTP passwords
API keys
OAuth secrets
Production credentials
Private keys
```

Secrets must be supplied through:

* Environment variables
* Docker secrets where appropriate
* Deployment-platform secret managers

Secrets must not be hard-coded in source code.

---

# 29. Environment Files

The repository shall contain:

```text
.env.example
```

Developers create their own local:

```text
.env
```

The `.env` file must be included in `.gitignore`.

The `.env.example` file must contain placeholder/example values only.

Example:

```env
DATABASE_URL=
JWT_SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=
CORS_ORIGINS=
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
```

No real credentials should be placed in `.env.example`.

---

# 30. HTTPS

Production communication must use HTTPS.

Authentication cookies must use:

```text
Secure=true
```

in production.

The application must not transmit authentication credentials over unencrypted HTTP in production.

---

# 31. File Upload Security

Profile-picture uploads must be validated by the backend.

The backend should validate:

* File size
* MIME/content type
* File contents
* Allowed extensions

User-provided filenames must not be trusted.

Uploaded files should use server-generated filenames.

Executable or unexpected file types must not be accepted as profile pictures.

---

# 32. Security Logging

Application logs may contain:

* Request ID
* Endpoint
* HTTP status code
* Execution time
* Non-sensitive error information

Application logs must never contain:

```text
Passwords
JWTs
Reset tokens
Verification tokens
Password hashes
Database passwords
API keys
SMTP passwords
```

When debugging authentication problems, developers must use safe identifiers and non-sensitive information.

---

# 33. Authentication Error Handling

Authentication errors must return controlled API responses.

Raw internal exceptions must not be exposed to clients.

The API should provide safe, human-readable error messages while keeping sensitive implementation details in server-side logs where appropriate.

Examples of controlled authentication errors include:

```text
INVALID_CREDENTIALS
EMAIL_NOT_VERIFIED
ACCOUNT_DEACTIVATED
INVALID_TOKEN
TOKEN_EXPIRED
SESSION_REVOKED
INSUFFICIENT_PERMISSIONS
```

The exact error response format must follow:

```text
docs/api/epic-1-api-contract.md
```

---

# 34. Frontend Security Responsibilities

The frontend must:

* Use the approved API endpoints
* Send authentication requests using the configured cookie mechanism
* Avoid storing JWTs in localStorage/sessionStorage
* Protect private routes for user experience
* Hide UI actions that the current role cannot use
* Never assume frontend authorization is sufficient
* Never expose backend secrets

Backend authorization remains mandatory even when a frontend route or button is hidden.

---

# 35. Security Responsibilities by Layer

Security responsibilities should be separated as follows:

```text
Frontend
   ↓
User experience and route protection

FastAPI API
   ↓
Authentication and authorization

Security/Core
   ↓
Password hashing, JWT, token validation

Session Layer
   ↓
Session tracking and revocation

Database
   ↓
Secure persistence of users, sessions and security records
```

No layer should assume another layer has completely replaced its own required security responsibility.

---

# 36. Epic 1 Security Testing

The following security scenarios must be tested before Epic 1 is considered complete:

### Authentication

* [ ] Valid credentials allow login
* [ ] Invalid credentials are rejected
* [ ] Deactivated accounts cannot log in
* [ ] Unverified accounts are handled according to requirements
* [ ] Expired JWTs are rejected
* [ ] Invalid JWT signatures are rejected
* [ ] Unknown JTIs are rejected
* [ ] Revoked sessions are rejected

### Session Management

* [ ] Login creates a session
* [ ] Logout revokes the session
* [ ] Logged-out JWT cannot access protected endpoints
* [ ] Inactive sessions expire
* [ ] Account deactivation revokes active sessions

### Password Security

* [ ] Passwords are stored only as Argon2id hashes
* [ ] Password verification works
* [ ] Weak passwords are rejected according to the password policy
* [ ] Password reset tokens expire
* [ ] Password reset tokens are single-use
* [ ] Password reset invalidates existing sessions

### Email Verification

* [ ] Verification token is generated securely
* [ ] Verification token is stored as a hash
* [ ] Expired verification tokens are rejected
* [ ] Used verification tokens cannot be reused

### RBAC

* [ ] Admin endpoints require ADMIN role
* [ ] Students cannot access admin endpoints
* [ ] Teachers cannot access admin endpoints
* [ ] Users cannot assign themselves ADMIN role

### Security

* [ ] Secrets are not committed
* [ ] Passwords are not logged
* [ ] Tokens are not logged
* [ ] CORS is correctly configured
* [ ] Production cookies use Secure
* [ ] Profile uploads are validated

---

# 37. Security Review Checklist

Before merging an Epic 1 security-related feature, verify:

```text
☐ Authentication mechanism follows this specification
☐ JWT claims follow the approved structure
☐ JWT expiration is validated
☐ JTI is validated against the server-side session
☐ Session revocation works
☐ Passwords use Argon2id
☐ Passwords are never logged
☐ Verification tokens are hashed
☐ Reset tokens are hashed
☐ Reset tokens expire after 24 hours
☐ Reset tokens are single-use
☐ Password reset revokes existing sessions
☐ RBAC is enforced on the backend
☐ Public users cannot create ADMIN accounts
☐ Deactivated accounts cannot authenticate
☐ Deactivation revokes sessions
☐ Security-sensitive actions are audited
☐ Secrets are excluded from Git
☐ CORS is explicitly configured
☐ Production uses HTTPS
☐ Authentication cookies use Secure in production
☐ File uploads are validated
☐ Sensitive information is excluded from logs
☐ Security tests pass
```

---

# 38. Source-of-Truth Rule

Security implementation must remain consistent with:

```text
Requirements
      +
Architecture
      +
Database Specification
      +
API Contract
      +
Security Specification
```

If implementation requires a security change:

```text
Identify required change
        ↓
Discuss with team
        ↓
Update relevant documentation
        ↓
Implement
        ↓
Test
        ↓
Review
        ↓
Merge
```

Developers must not silently introduce a different authentication, authorization, token, or session mechanism.

---

# 39. Final Security Principle

The following principle applies throughout Epic 1:

```text
Never trust the client.
Never store plaintext passwords.
Never expose secrets.
Never rely on frontend authorization.
Never accept a JWT without validating its session.
Never log sensitive authentication information.
```

The FastAPI backend remains the final security boundary for authentication and authorization.
