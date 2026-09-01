# Trustworthy TA Agent

# Git & Development Workflow

**Epic:** Epic 1 — User Management Module
**Version:** 1.0
**Status:** Final
**Repository:** GitHub

---

# 1. Purpose

This document defines the Git and development workflow for the Trustworthy TA Agent project.

The workflow ensures:

* Organized team development.
* Clear ownership of work.
* Controlled integration of changes.
* Code review before merging.
* Reduced merge conflicts.
* Consistent commit history.
* Protection of stable code.
* Traceability between Jira tasks and GitHub changes.

The GitHub repository is the single source of truth for application source code.

---

# 2. Development Workflow

All development should follow this workflow:

```text
Jira Story / Task
       ↓
Create Feature Branch
       ↓
Implement Changes
       ↓
Run Tests
       ↓
Commit Changes
       ↓
Push Feature Branch
       ↓
Create Pull Request
       ↓
Code Review
       ↓
CI / Tests Pass
       ↓
Merge into develop
       ↓
Epic / Release Testing
       ↓
Merge develop into main
```

---

# 3. Branch Strategy

The project will use the following branch structure:

```text
main
 │
 └── develop
      │
      ├── feature/TA-101-user-registration
      ├── feature/TA-102-user-login
      ├── feature/TA-103-password-reset
      ├── feature/TA-104-session-management
      ├── feature/TA-105-rbac
      ├── feature/TA-106-profile-management
      └── feature/TA-107-account-deactivation
```

The Jira issue ID should be included in the branch name whenever possible.

Example:

```text
feature/TA-101-user-registration
```

---

# 4. Main Branch

The `main` branch contains stable and release-ready code.

## Rules

* Developers must not push directly to `main`.
* Changes must be introduced through a Pull Request.
* Pull Requests must be reviewed before merging.
* Required tests and CI checks must pass.
* `main` should always contain a stable version of the project.
* Force pushes are not allowed.

---

# 5. Develop Branch

The `develop` branch is the main integration branch for ongoing development.

## Rules

* Feature branches are merged into `develop`.
* Developers should not directly push to `develop`.
* Changes must be reviewed through Pull Requests.
* `develop` should remain buildable and testable.
* Integration testing is performed on `develop`.

After an epic or release is fully tested:

```text
develop
   ↓
main
```

---

# 6. Feature Branches

Every Jira story or development task should have its own feature branch when practical.

### Branch Format

```text
feature/<jira-id>-<short-description>
```

### Examples

```text
feature/TA-101-user-registration
feature/TA-102-user-login
feature/TA-103-password-reset
feature/TA-105-rbac
```

For bug fixes:

```text
fix/TA-120-login-validation
```

For documentation:

```text
docs/TA-125-update-api-contract
```

For maintenance:

```text
chore/TA-130-update-dependencies
```

---

# 7. One Feature = One Branch

A feature branch should contain one logical piece of work.

### Avoid

```text
feature/auth
```

containing:

```text
login
profile
RBAC
password reset
unrelated UI changes
```

### Prefer

```text
feature/TA-101-user-registration
feature/TA-102-user-login
feature/TA-103-password-reset
feature/TA-105-rbac
```

Closely related tasks may be combined into one branch when agreed upon by the team.

---

# 8. Creating a Feature Branch

Before starting a new task, update your local `develop` branch.

```bash
git checkout develop
git pull origin develop
```

Create the feature branch:

```bash
git checkout -b feature/TA-101-user-registration
```

Verify the current branch:

```bash
git branch
```

The active branch will be marked with `*`.

---

# 9. Working on a Feature

After creating the feature branch:

1. Implement the assigned Jira task.
2. Follow the project architecture.
3. Follow the API contract.
4. Follow the database specification.
5. Write or update tests.
6. Run tests locally.
7. Review your own changes.
8. Commit the changes.

The feature branch may be pushed multiple times while development is in progress.

---

# 10. Commit Workflow

Commits should be small, meaningful, and related to one logical change.

### Commit Format

```text
type(scope): description
```

### Allowed Types

| Type       | Purpose                  |
| ---------- | ------------------------ |
| `feat`     | New functionality        |
| `fix`      | Bug fix                  |
| `test`     | Tests                    |
| `refactor` | Code restructuring       |
| `docs`     | Documentation            |
| `style`    | Formatting/style changes |
| `chore`    | Maintenance              |
| `build`    | Build/dependency changes |
| `ci`       | CI/CD changes            |

### Good Examples

```text
feat(auth): implement user registration
feat(auth): add email verification
feat(auth): implement login endpoint
fix(auth): handle duplicate email
test(auth): add registration API tests
docs(api): update registration contract
chore(deps): update backend dependencies
```

### Bad Examples

```text
update
changes
final
final2
working
new
done
```

---

# 11. Referencing Jira in Commits

Where practical, include the Jira issue ID in the commit message.

Example:

```text
feat(auth): TA-101 implement user registration
```

This makes it easier to trace:

```text
Jira Task
    ↓
Git Branch
    ↓
Git Commit
    ↓
Pull Request
    ↓
Code
```

---

# 12. Push Workflow

After implementing and testing the feature:

Check the changes:

```bash
git status
```

Review changed files:

```bash
git diff
```

Stage the intended files:

```bash
git add <file-path>
```

Example:

```bash
git add backend/app/api/routes/auth.py
```

Commit:

```bash
git commit -m "feat(auth): TA-101 implement user registration"
```

Push the feature branch:

```bash
git push -u origin feature/TA-101-user-registration
```

For subsequent pushes to the same branch:

```bash
git push
```

---

# 13. Pull Request Workflow

Once the feature is ready:

```text
feature/TA-101-user-registration
             ↓
          develop
```

Create a Pull Request on GitHub.

The Pull Request should contain:

* Jira issue reference.
* Description of the implemented feature.
* Files/components changed.
* Tests performed.
* Known limitations.
* Screenshots for UI changes when useful.

---

# 14. Pull Request Title

Use a clear Pull Request title.

Example:

```text
feat(auth): implement user registration [TA-101]
```

Another example:

```text
feat(auth): implement login and JWT authentication [TA-102]
```

---

# 15. Pull Request Description

A Pull Request should explain:

```text
## What was implemented?

- Added registration endpoint.
- Added password hashing.
- Added duplicate email validation.

## Tests

- Registration success test
- Duplicate email test
- Invalid input test

## Jira

TA-101
```

---

# 16. Code Review

At least one other team member should review the Pull Request before merging.

The reviewer should check:

* Does the implementation satisfy the Jira requirements?
* Does it follow the project architecture?
* Does it follow the API contract?
* Does it follow the database specification?
* Are security requirements satisfied?
* Is the code readable and maintainable?
* Are appropriate tests included?
* Does the change introduce unnecessary modifications?
* Does it break existing functionality?
* Are error cases handled correctly?

---

# 17. Merge Rules

A Pull Request should not be merged when:

* Tests are failing.
* CI checks are failing.
* Requirements are not satisfied.
* API contract is violated.
* Database changes are incorrect.
* Security requirements are violated.
* Important review comments remain unresolved.
* The implementation breaks existing functionality.

After approval:

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
```

---

# 18. Keeping a Feature Branch Updated

If `develop` has changed while you are working, update your feature branch before creating or merging the Pull Request.

First update `develop`:

```bash
git checkout develop
git pull origin develop
```

Return to your feature branch:

```bash
git checkout feature/TA-101-user-registration
```

Merge the latest `develop`:

```bash
git merge develop
```

If there are conflicts, resolve them locally.

Then:

```bash
git add .
git commit -m "chore: resolve merge conflicts"
git push
```

---

# 19. Merge Conflicts

A merge conflict may occur when multiple developers modify the same part of a file.

Git may show:

```text
<<<<<<< HEAD
your changes
=======
changes from develop
>>>>>>> develop
```

The responsible developer must:

1. Understand both changes.
2. Discuss the intended behavior with the other developer if necessary.
3. Resolve the conflict manually.
4. Remove the conflict markers.
5. Run the relevant tests.
6. Stage the resolved files.
7. Commit the resolution.
8. Push the branch.

Commands:

```bash
git status
git add <resolved-file>
git commit -m "chore: resolve merge conflicts"
git push
```

Do not blindly select "ours" or "theirs".

---

# 20. Database Migration Workflow

Database schema changes must be managed through migrations.

The team will use Alembic for PostgreSQL schema migrations.

Example:

```bash
alembic revision --autogenerate -m "add session table"
```

Review the generated migration before applying it.

Apply the migration:

```bash
alembic upgrade head
```

Database migrations must:

* Be committed to Git.
* Be reviewed before merging.
* Be tested locally.
* Not be deleted or modified without team agreement.
* Maintain compatibility with the application.

---

# 21. Shared Database Rules

Database changes must be coordinated with the team.

For example, if one developer modifies:

```text
users
```

and another modifies:

```text
sessions
```

both changes must be represented through proper migrations.

Developers must not:

* Delete another developer's migration.
* Rewrite shared migration history without agreement.
* Commit database dumps containing sensitive data.
* Make undocumented schema changes.

---

# 22. API Contract Workflow

If implementation requires an API change:

1. Discuss the change with the team.
2. Update the API contract.
3. Update backend schemas.
4. Update backend implementation.
5. Update frontend integration.
6. Update tests.
7. Review the Pull Request.

For Epic 1, the API contract is:

```text
docs/api/epic-1-api-contract.md
```

No developer should make a major API change unilaterally.

---

# 23. Documentation Workflow

Documentation is version controlled together with the project.

Documentation changes should use appropriate commit types.

Examples:

```bash
git add docs/api/epic-1-api-contract.md
git commit -m "docs(api): update registration contract"
git push
```

```bash
git add docs/security/authentication.md
git commit -m "docs(security): document authentication policy"
git push
```

Documentation should be updated whenever implementation changes make existing documentation inaccurate.

---

# 24. Protected Branches

The following branches should be protected on GitHub:

```text
main
develop
```

Recommended protection rules:

* Require Pull Requests.
* Require at least one approval.
* Require CI checks to pass.
* Prevent force pushes.
* Prevent direct pushes.
* Prevent accidental branch deletion where appropriate.

---

# 25. Daily Development Workflow

## Start of Work

Update the integration branch:

```bash
git checkout develop
git pull origin develop
```

Create or switch to your feature branch:

```bash
git checkout -b feature/TA-101-user-registration
```

---

## During Work

Check your changes:

```bash
git status
```

Stage changes:

```bash
git add <file-path>
```

Commit:

```bash
git commit -m "feat(auth): TA-101 implement registration"
```

Push:

```bash
git push
```

---

## Before Creating a Pull Request

Update your branch:

```bash
git checkout develop
git pull origin develop
git checkout feature/TA-101-user-registration
git merge develop
```

Run tests:

```bash
# Use the project's configured test command
```

Check the final changes:

```bash
git status
git diff
```

Push:

```bash
git push
```

Create the Pull Request:

```text
feature/TA-101-user-registration
                ↓
             develop
```

---

# 26. After Pull Request Is Merged

After the feature is merged into `develop`, remove the local feature branch:

```bash
git checkout develop
git pull origin develop
git branch -d feature/TA-101-user-registration
```

If the remote branch has not been automatically deleted:

```bash
git push origin --delete feature/TA-101-user-registration
```

Only delete the branch after confirming that the Pull Request has been successfully merged.

---

# 27. Main Release Workflow

When an Epic or release is fully implemented and tested:

```text
develop
   │
   ├── Integration Testing
   ├── Regression Testing
   └── Final Review
            ↓
          main
```

The merge into `main` should be performed through a Pull Request.

After merging into `main`:

```bash
git checkout main
git pull origin main
```

The `main` branch represents the stable project version.

---

# 28. Do Not Commit

The following must not be committed:

```text
.env
.venv/
__pycache__/
*.pyc
node_modules/
build/
dist/
database dumps containing sensitive data
passwords
API keys
JWT secrets
private credentials
```

Sensitive configuration should be stored in environment variables.

Use:

```text
.env.example
```

to document required environment variables without exposing actual secrets.

---

# 29. Definition of Ready

Before starting a Jira task, verify:

* [ ] Requirement is understood.
* [ ] Acceptance criteria are clear.
* [ ] Related API contract is available.
* [ ] Database requirements are understood.
* [ ] Dependencies are identified.
* [ ] UI behavior is agreed upon where applicable.
* [ ] Jira task is assigned.
* [ ] Feature branch is created.

---

# 30. Definition of Done

A feature is considered complete when:

* [ ] Code is implemented.
* [ ] Unit tests are added where applicable.
* [ ] Integration/API tests are added where applicable.
* [ ] Local tests pass.
* [ ] API contract is followed.
* [ ] Database changes use migrations.
* [ ] Security requirements are satisfied.
* [ ] Documentation is updated if required.
* [ ] Changes are committed.
* [ ] Feature branch is pushed.
* [ ] Pull Request is created.
* [ ] Code review is completed.
* [ ] CI checks pass.
* [ ] Pull Request is merged into `develop`.
* [ ] Jira task is updated.

---

# 31. Emergency / Regression Workflow

If a change introduces a serious regression:

```text
Identify Problem
      ↓
Stop Further Merges
      ↓
Identify Offending Change
      ↓
Discuss With Team
      ↓
Fix or Revert
      ↓
Run Tests
      ↓
Code Review
      ↓
Resume Development
```

Never use force pushes on shared branches to hide or bypass problems.

---

# 32. Quick Command Reference

### Get latest develop

```bash
git checkout develop
git pull origin develop
```

### Create feature branch

```bash
git checkout -b feature/TA-101-user-registration
```

### Check status

```bash
git status
```

### Review changes

```bash
git diff
```

### Stage a file

```bash
git add <file-path>
```

### Commit

```bash
git commit -m "feat(auth): TA-101 implement registration"
```

### Push new branch

```bash
git push -u origin feature/TA-101-user-registration
```

### Push existing branch

```bash
git push
```

### Update feature branch

```bash
git checkout develop
git pull origin develop
git checkout feature/TA-101-user-registration
git merge develop
```

### Delete local feature branch after merge

```bash
git checkout develop
git branch -d feature/TA-101-user-registration
```

---

# 33. Team Workflow Summary

The complete team workflow is:

```text
                    JIRA
                     │
                     ▼
              Assign Story/Task
                     │
                     ▼
             Create Feature Branch
                     │
                     ▼
               Develop Locally
                     │
                     ▼
                 Run Tests
                     │
                     ▼
              Commit Changes
                     │
                     ▼
              Push Feature Branch
                     │
                     ▼
             Create Pull Request
                     │
                     ▼
                Code Review
                     │
                     ▼
                 CI Checks
                     │
                     ▼
              Merge into develop
                     │
                     ▼
             Integration Testing
                     │
                     ▼
             Epic/Release Complete
                     │
                     ▼
             Pull Request to main
                     │
                     ▼
              Stable Version
```

This workflow ensures that Jira tasks, Git branches, commits, Pull Requests, reviews, testing, and releases remain connected throughout development.
