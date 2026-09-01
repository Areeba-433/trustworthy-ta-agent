# Epic 1: User Management Module — Database Specification

**Project:** Trustworthy TA Agent
**Epic:** Epic 1 — User Management Module
**Database:** PostgreSQL
**Document Version:** 1.0
**Status:** Baseline

---

## 1. Overview

This document defines the database requirements for the User Management Module of the Trustworthy TA Agent platform.

The database will store and manage:

* User accounts
* User roles
* User profiles
* Authentication sessions
* Email verification tokens
* Password reset tokens
* Audit logs

The database design supports user registration, authentication, authorization, password recovery, session management, profile management, and account activation/deactivation.

---

## 2. Database Design Goals

The database design aims to:

* Store user information securely.
* Prevent duplicate user accounts.
* Support Student, Teacher, and Admin roles.
* Maintain relationships between users and their roles.
* Support secure authentication and session management.
* Support email verification and password reset.
* Store user profile information.
* Maintain account activation/deactivation status.
* Maintain audit records for security-sensitive actions.
* Provide appropriate constraints and indexes for data integrity and performance.

---

## 3. Database Technology

PostgreSQL will be used as the relational database for Epic 1.

The database will use:

* Primary keys for unique record identification.
* Foreign keys for relationships.
* Unique constraints for fields such as email.
* NOT NULL constraints for required fields.
* Timestamps for tracking record creation and updates.
* Indexes for frequently queried fields.

---

# 4. Entity Overview

The main entities required for Epic 1 are:

```text
User
 │
 ├── Role
 │
 ├── User Profile
 │
 ├── Sessions
 │
 ├── Email Verification Tokens
 │
 ├── Password Reset Tokens
 │
 └── Audit Logs
```

---

# 5. Entity Specifications

## 5.1 Users Table

The `users` table stores the core account information of every platform user.

| Field         | Data Type    | Constraints             | Description                |
| ------------- | ------------ | ----------------------- | -------------------------- |
| id            | UUID         | PK, NOT NULL            | Unique user identifier     |
| email         | VARCHAR(255) | UNIQUE, NOT NULL        | User email address         |
| username      | VARCHAR(100) | UNIQUE, NOT NULL        | User login name            |
| password_hash | TEXT         | NOT NULL                | Hashed user password       |
| role_id       | UUID         | FK, NOT NULL            | User's assigned role       |
| is_active     | BOOLEAN      | NOT NULL, DEFAULT TRUE  | Account activation status  |
| is_verified   | BOOLEAN      | NOT NULL, DEFAULT FALSE | Email verification status  |
| created_at    | TIMESTAMP    | NOT NULL                | Account creation time      |
| updated_at    | TIMESTAMP    | NOT NULL                | Last account update time   |
| last_login_at | TIMESTAMP    | NULL                    | Last successful login time |

### Constraints

* `id` is the primary key.
* `email` must be unique.
* `username` must be unique.
* `password_hash` must never contain a plain-text password.
* `role_id` must reference a valid role.
* Deactivated users must not be allowed to authenticate.

---

## 5.2 Roles Table

The `roles` table defines the roles available in the system.

| Field       | Data Type   | Constraints      | Description             |
| ----------- | ----------- | ---------------- | ----------------------- |
| id          | UUID        | PK, NOT NULL     | Unique role identifier  |
| name        | VARCHAR(50) | UNIQUE, NOT NULL | Role name               |
| description | TEXT        | NULL             | Description of the role |
| created_at  | TIMESTAMP   | NOT NULL         | Role creation time      |

### Initial Roles

The system will initially support:

| Role    | Description                                            |
| ------- | ------------------------------------------------------ |
| Student | Accesses student-specific learning functionality       |
| Teacher | Accesses teaching and course-related functionality     |
| Admin   | Manages users, roles, and administrative functionality |

---

## 5.3 User Profiles Table

The `user_profiles` table stores additional information associated with a user's account.

| Field               | Data Type    | Constraints          | Description                 |
| ------------------- | ------------ | -------------------- | --------------------------- |
| id                  | UUID         | PK, NOT NULL         | Unique profile identifier   |
| user_id             | UUID         | FK, UNIQUE, NOT NULL | Associated user             |
| first_name          | VARCHAR(100) | NOT NULL             | User's first name           |
| last_name           | VARCHAR(100) | NOT NULL             | User's last name            |
| profile_picture_url | TEXT         | NULL                 | Profile picture location    |
| department          | VARCHAR(150) | NULL                 | Teacher's department        |
| expertise           | TEXT         | NULL                 | Teacher's area of expertise |
| created_at          | TIMESTAMP    | NOT NULL             | Profile creation time       |
| updated_at          | TIMESTAMP    | NOT NULL             | Last profile update         |

### Notes

* Each user has one profile.
* `user_id` must reference an existing user.
* Teacher-specific fields may remain NULL for students and admins.
* Student course/progress information will be managed by the appropriate course/learning modules rather than duplicating it in the user profile.

---

## 5.4 Sessions Table

The `sessions` table stores information required for session management.

| Field            | Data Type    | Constraints      | Description                       |
| ---------------- | ------------ | ---------------- | --------------------------------- |
| id               | UUID         | PK, NOT NULL     | Unique session identifier         |
| user_id          | UUID         | FK, NOT NULL     | Associated user                   |
| token_identifier | VARCHAR(255) | UNIQUE, NOT NULL | JWT/session identifier            |
| created_at       | TIMESTAMP    | NOT NULL         | Session creation time             |
| expires_at       | TIMESTAMP    | NOT NULL         | Session expiration time           |
| last_activity_at | TIMESTAMP    | NOT NULL         | Last recorded activity            |
| revoked_at       | TIMESTAMP    | NULL             | Time the session was revoked      |
| ip_address       | INET         | NULL             | Client IP address                 |
| user_agent       | TEXT         | NULL             | Client device/browser information |

### Constraints

* Every session must belong to a valid user.
* Expired sessions must not be considered active.
* Revoked sessions must not be accepted.
* Session information must be handled securely.

---

## 5.5 Email Verification Tokens Table

The `email_verification_tokens` table manages email verification during registration.

| Field      | Data Type | Constraints      | Description               |
| ---------- | --------- | ---------------- | ------------------------- |
| id         | UUID      | PK, NOT NULL     | Unique token identifier   |
| user_id    | UUID      | FK, NOT NULL     | Associated user           |
| token_hash | TEXT      | UNIQUE, NOT NULL | Hashed verification token |
| expires_at | TIMESTAMP | NOT NULL         | Token expiration time     |
| used_at    | TIMESTAMP | NULL             | Time token was used       |
| created_at | TIMESTAMP | NOT NULL         | Token creation time       |

### Rules

* A verification token must belong to a valid user.
* Expired tokens must not be accepted.
* A used token must not be reused.
* Tokens should be stored securely rather than storing sensitive raw token values.

---

## 5.6 Password Reset Tokens Table

The `password_reset_tokens` table supports password recovery.

| Field      | Data Type | Constraints      | Description             |
| ---------- | --------- | ---------------- | ----------------------- |
| id         | UUID      | PK, NOT NULL     | Unique token identifier |
| user_id    | UUID      | FK, NOT NULL     | Associated user         |
| token_hash | TEXT      | UNIQUE, NOT NULL | Hashed reset token      |
| expires_at | TIMESTAMP | NOT NULL         | Token expiration time   |
| used_at    | TIMESTAMP | NULL             | Time token was used     |
| created_at | TIMESTAMP | NOT NULL         | Token creation time     |

### Rules

* Reset tokens must belong to a valid user.
* Reset tokens expire after 24 hours according to the Epic 1 requirements.
* A used token cannot be reused.
* A new password must satisfy the defined password security requirements.

---

## 5.7 Audit Logs Table

The `audit_logs` table records important security and account-management activities.

| Field      | Data Type    | Constraints  | Description                       |
| ---------- | ------------ | ------------ | --------------------------------- |
| id         | UUID         | PK, NOT NULL | Unique log identifier             |
| user_id    | UUID         | FK, NULL     | User associated with the action   |
| action     | VARCHAR(100) | NOT NULL     | Action performed                  |
| status     | VARCHAR(50)  | NOT NULL     | Result of the action              |
| ip_address | INET         | NULL         | Client IP address                 |
| user_agent | TEXT         | NULL         | Client device/browser information |
| metadata   | JSONB        | NULL         | Additional event information      |
| created_at | TIMESTAMP    | NOT NULL     | Time of the event                 |

### Actions to Log

Examples include:

* Registration
* Email verification
* Successful login
* Failed login
* Logout
* Password reset
* Profile update
* Account activation
* Account deactivation

Audit logs should not store passwords, authentication tokens, or other sensitive credentials.

---

# 6. Entity Relationships

The primary relationships are:

```text
ROLES
  │
  │ 1
  │
  │ *
USERS
  │
  ├────────────── 1 : 1 ────────────── USER_PROFILES
  │
  ├────────────── 1 : * ────────────── SESSIONS
  │
  ├────────────── 1 : * ────────────── EMAIL_VERIFICATION_TOKENS
  │
  ├────────────── 1 : * ────────────── PASSWORD_RESET_TOKENS
  │
  └────────────── 1 : * ────────────── AUDIT_LOGS
```

### Relationship Summary

| Relationship                     | Cardinality |
| -------------------------------- | ----------- |
| Role → Users                     | One-to-Many |
| User → User Profile              | One-to-One  |
| User → Sessions                  | One-to-Many |
| User → Email Verification Tokens | One-to-Many |
| User → Password Reset Tokens     | One-to-Many |
| User → Audit Logs                | One-to-Many |

---

# 7. Data Integrity Rules

The following rules must be enforced:

### User Accounts

* Email addresses must be unique.
* Usernames must be unique.
* Required user information cannot be NULL.
* Every user must have a valid role.
* Deactivated users must not authenticate.

### Passwords

* Plain-text passwords must never be stored.
* Passwords must be stored as secure hashes.
* Password reset must replace the existing password hash.

### Roles

* Only valid system roles can be assigned to users.
* Role names must be unique.

### Profiles

* Each user can have only one profile.
* Profile records must reference an existing user.

### Tokens

* Verification and reset tokens must expire.
* Used tokens must not be reused.
* Token values must not be stored in plain text.

---

# 8. Indexing Strategy

Indexes should be created for fields frequently used for authentication and account management.

Recommended indexes include:

| Table                     | Field            | Purpose                       |
| ------------------------- | ---------------- | ----------------------------- |
| users                     | email            | Fast user lookup during login |
| users                     | username         | Fast username lookup          |
| users                     | role_id          | Role-based queries            |
| users                     | is_active        | Account status checks         |
| sessions                  | user_id          | User session lookup           |
| sessions                  | token_identifier | Session/token lookup          |
| sessions                  | expires_at       | Expiration checks             |
| password_reset_tokens     | token_hash       | Reset token lookup            |
| email_verification_tokens | token_hash       | Verification token lookup     |
| audit_logs                | user_id          | User activity lookup          |
| audit_logs                | created_at       | Time-based audit queries      |

---

# 9. Account Status

The `users.is_active` field will be used to control account access.

```text
Active Account
     │
     ├── Can authenticate
     └── Can access authorized resources

Inactive Account
     │
     ├── Cannot authenticate
     └── Existing data remains stored
```

Account deactivation should not delete the user's data.

---

# 10. Security Considerations

The database design must follow these security principles:

* Passwords must be stored only as secure hashes.
* Authentication and reset tokens should be stored securely.
* Database credentials must be stored in environment variables.
* Database access should use authenticated connections.
* Sensitive information should not be exposed through API responses.
* Audit logs must not contain passwords or raw authentication tokens.
* Database users should follow the principle of least privilege.
* Foreign key constraints should be used to maintain data integrity.

---

# 11. Data Retention

User account data should remain stored when an account is deactivated.

Deactivation changes the account status rather than deleting the user record.

Audit logs should be retained according to the project's security and data-retention policies.

Expired verification and password reset tokens may be removed periodically after they are no longer required.

---

# 12. Future Extensibility

The database design should allow future modules to extend user-related functionality without redesigning the core user table.

Potential future relationships include:

```text
USER
 │
 ├── Courses
 ├── Teaching Assistants
 ├── Assignments
 ├── Quizzes
 ├── Learning Progress
 └── Notifications
```

These relationships will be defined in the database specifications of their respective modules.

---

# 13. Database Migration

Database schema changes should be managed through a database migration system.

Each schema change should be:

* Version controlled.
* Reviewed before merging.
* Applied consistently across development environments.
* Reversible where practical.

Database migrations should be included as part of the backend development workflow.

---

# 14. Related Documentation

* **Requirements:** `docs/requirements/epic-1-requirements.md`
* **Architecture:** `docs/architecture/epic-1-architecture.md`
* **API Contract:** `docs/api/epic-1-api-contract.md`
* **Authentication & Security:** `docs/security/authentication.md`
* **Project Setup:** `docs/development/project-setup.md`

---

## 15. Database Design Summary

The Epic 1 database provides the persistent data layer for the User Management Module.

The core entities are:

* `users`
* `roles`
* `user_profiles`
* `sessions`
* `email_verification_tokens`
* `password_reset_tokens`
* `audit_logs`

The design provides the foundation for secure registration, authentication, authorization, password recovery, session management, profile management, and account administration.
