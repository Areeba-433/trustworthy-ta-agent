# Epic 1: User Management Module

## 1. Overview

The User Management Module provides user registration, authentication,
authorization, profile management, and account management for the
Trustworthy TA Agent platform.

The system supports three primary user roles:

- Student
- Teacher
- Admin

## 2. Objectives

The User Management Module aims to:

- Allow users to securely register accounts.
- Authenticate registered users.
- Provide role-based access to the system.
- Support password recovery.
- Manage user sessions securely.
- Allow users to manage their profiles.
- Allow administrators to activate and deactivate user accounts.

## 3. User Stories

### User Story 1.1: User Registration

**As a new user, I want to create an account by providing my
required information so that I can securely access the
Trustworthy TA Agent according to my assigned role.**

#### Acceptance Criteria

1. User can enter the required registration information.
2. System validates the provided information.
3. System prevents registration using an already registered email address.
4. System securely stores the user account information.
5. System assigns the appropriate user role.
6. System sends a verification email after successful registration.
7. User can activate the account through the verification link.

---

### User Story 1.2: User Login & Authentication

**As a user, I want to securely log in so that I can access
the system according to my role.**

#### Acceptance Criteria

1. Login supports email/username and password.
2. Users are redirected based on Student, Teacher, or Admin role.
3. Sessions are secured using JWT tokens.
4. Invalid login attempts show error messages.
5. The "Remember Me" option is available.

---

### User Story 1.3: Password Reset

**As a user, I want to reset my password so that I can regain
access to my account if I forget my password.**

#### Acceptance Criteria

1. Password reset is available from the login page.
2. The reset link is sent to the registered email.
3. The reset link expires in 24 hours.
4. New passwords must meet security requirements.
5. Successful reset shows confirmation.

---

### User Story 1.4: Logout & Session Management

**As a user, I want to securely log out so that my account
cannot be accessed by unauthorized users.**

#### Acceptance Criteria

1. Logout options are clearly available.
2. Session ends completely after logging out.
3. JWT tokens are invalidated.
4. User is redirected to the login page.
5. Session expires after 30 minutes of inactivity.

---

### User Story 1.5: Role-Based Access Control

**As a system administrator, I want users to have appropriate
roles and permissions so that system resources are protected.**

#### Acceptance Criteria

1. Student, Teacher, and Admin roles are supported.
2. Students access student features only.
3. Teachers access teaching and course features.
4. Admins have full user management access.
5. Roles are validated on API requests.

---

### User Story 1.6: User Profile Management

**As a user, I want to manage my profile information so that
my personal and academic information remains up to date.**

#### Acceptance Criteria

1. Profile displays name, email, and picture.
2. Users can update personal information.
3. Users can change profile pictures.
4. Teachers can add departments and expertise.
5. Students can view courses and progress.

---

### User Story 1.7: User Account Deactivation

**As an administrator, I want to manage inactive or restricted
user accounts so that access to the system can be controlled.**

#### Acceptance Criteria

1. Admin can activate or deactivate accounts.
2. Deactivated users cannot log in.
3. User data remains stored as inactive.
4. Deactivation actions are logged.
5. Users are notified of deactivation.

## 4. Supported Roles

| Role | Main Responsibility |
|---|---|
| Student | Access student features and course-related learning support |
| Teacher | Manage teaching, courses, and AI teaching assistants |
| Admin | Manage users, roles, permissions, and system access |

## 5. Epic Acceptance Summary

Epic 1 will be considered complete when:

- Users can register and verify their accounts.
- Registered users can securely log in.
- Users can reset forgotten passwords.
- Users can securely log out.
- Sessions are managed securely.
- Role-based access control is enforced.
- Users can manage their profiles.
- Admins can activate and deactivate accounts.
- Deactivated users cannot access the system.
- User management actions are appropriately logged.

## 6. Related Documentation

- Architecture: `docs/architecture/epic-1-architecture.md`
- Database: `docs/database/epic-1-database.md`
- API Contract: `docs/api/epic-1-api-contract.md`
- Authentication: `docs/security/authentication.md`