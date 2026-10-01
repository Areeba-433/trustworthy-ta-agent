"""
Authentication API routes for user registration, verification, login, and logout.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_token,
    hash_token,
    get_token_expiry,
    is_token_expired
)
from app.core.config import settings
from app.core.middleware.auth import get_current_user
from app.models.user import User, UserRole
from app.models.profile import Profile
from app.models.email_verification_token import EmailVerificationToken
from app.services.token_service import TokenService
from app.services.email_service import send_verification_email, send_password_reset_email
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction
from app.schemas.auth import LoginRequest, success_response, error_response, ForgotPasswordRequest, ResetPasswordRequest

# Precomputed once at import time so a nonexistent-identifier login attempt
# costs the same Argon2 verify as a real one - response time cannot be used
# to enumerate valid identifiers.
_DUMMY_PASSWORD_HASH = get_password_hash("dummy-password-for-timing-safety-only")

# ============================================================
# Pydantic Schemas (Registration)
# ============================================================

class RegisterRequest(BaseModel):
    """Request body for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: str = "STUDENT"

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v

    @validator('role')
    def validate_role(cls, v):
        """Only STUDENT can self-register. TEACHER is granted by an admin."""
        if v != "STUDENT":
            raise ValueError('Public registration only allows the STUDENT role')
        return v


class RegisterResponse(BaseModel):
    """Response body for successful registration."""
    success: bool
    message: str
    data: dict


class VerifyEmailResponse(BaseModel):
    """Response body for email verification."""
    success: bool
    message: str


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user (STUDENT only).

    Creates user, profile, and sends verification email.
    Matches Database Specification: Table 1 (users), Table 2 (profiles).
    """

    # 1. Check for duplicate email
    existing_email = db.query(User).filter(User.email == register_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "EMAIL_ALREADY_EXISTS",
                    "message": "Email already registered."
                }
            }
        )

    # 2. Check for duplicate username
    existing_username = db.query(User).filter(User.username == register_data.username)
    existing_username = existing_username.filter(User.username == register_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "USERNAME_ALREADY_EXISTS",
                    "message": "Username already taken."
                }
            }
        )

    # 3. Hash password
    password_hash = get_password_hash(register_data.password)

    # 4. Create user
    user = User(
        username=register_data.username,
        email=register_data.email,
        password_hash=password_hash,
        role=UserRole.STUDENT,  # Public registration is always STUDENT
        is_active=True,
        is_verified=False
    )
    db.add(user)
    db.flush()  # Get user.id without committing

    # 5. Create profile
    profile = Profile(
        user_id=user.id,
        first_name=register_data.first_name,
        last_name=register_data.last_name,
        updated_at=datetime.now(timezone.utc)
    )
    db.add(profile)

    # 6. Commit transaction
    db.commit()
    db.refresh(user)

    # 7. Generate verification token
    raw_token = generate_verification_token()
    token_hash = hash_token(raw_token)
    expires_at = get_token_expiry()

    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(verification)
    db.commit()

    # 8. Send verification email (don't fail registration if email fails)
    send_verification_email(user.email, raw_token)

    return RegisterResponse(
        success=True,
        message="Registration successful! Please check your email to verify your account.",
        data={
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username
        }
    )


@router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Verify user email address.

    Matches Security Specification: Section 15 - Email Verification.
    """

    # 1. Hash the provided token
    token_hash = hash_token(token)

    # 2. Find matching verification record
    verification = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token_hash == token_hash
    ).first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": "Invalid verification token."
                }
            }
        )

    # 3. Check if already used
    if verification.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "TOKEN_ALREADY_USED",
                    "message": "This verification link has already been used."
                }
            }
        )

    # 4. Check if expired
    if is_token_expired(verification.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "TOKEN_EXPIRED",
                    "message": "Verification link has expired. Please request a new one."
                }
            }
        )

    # 5. Get user
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found."
                }
            }
        )

    # 6. Mark token as used and user as verified
    verification.used_at = datetime.now(timezone.utc)
    user.is_verified = True

    db.commit()

    return VerifyEmailResponse(
        success=True,
        message="Email verified successfully! You can now log in."
    )


# ============================================================
# PASSWORD RESET ENDPOINTS (NEW)
# ============================================================

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Request a password reset email."""
    user = db.query(User).filter(User.email == data.email).first()

    # Always return success (don't leak whether email exists)
    if user:
        auth_service = AuthService(db)
        raw_token = auth_service.create_password_reset_token(str(user.id))
        send_password_reset_email(user.email, raw_token)

    return success_response(
        "If an account with that email exists, a password reset link has been sent."
    )


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a valid reset token."""
    auth_service = AuthService(db)

    try:
        auth_service.reset_password(data.token, data.new_password)
        return success_response("Password has been reset successfully. You can now log in.")
    except ValueError as e:
        error_code = "INVALID_TOKEN"
        if "expired" in str(e).lower():
            error_code = "TOKEN_EXPIRED"
        elif "already used" in str(e).lower():
            error_code = "TOKEN_ALREADY_USED"
        elif "not found" in str(e).lower():
            error_code = "USER_NOT_FOUND"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(error_code, str(e))
        )


@router.post("/login")
async def login(
    data: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login with email/username and password.

    Sets httpOnly cookies for access and refresh tokens.
    """

    user = db.query(User).filter(
        (User.email == data.identifier) | (User.username == data.identifier)
    ).first()

    # Always run the (slow) hash verification, even when the user does not
    # exist, so response time cannot be used to enumerate valid identifiers.
    password_ok = verify_password(
        data.password, user.password_hash if user else _DUMMY_PASSWORD_HASH
    )

    if not user or not password_ok:
        AuditService.log(
            db, 
            action=AuditAction.LOGIN_FAILED,
            description=f"Failed attempt: {data.identifier}",
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=401,
            detail=error_response("INVALID_CREDENTIALS", "Invalid identifier or password")
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=error_response("ACCOUNT_DEACTIVATED", "Account is deactivated")
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail=error_response("EMAIL_NOT_VERIFIED", "Email not verified")
        )

    tokens = TokenService.create_session(
        db, str(user.id), user.role.name, data.remember_me,
        request.client.host if request.client else None,
        request.headers.get("user-agent")
    )

    response.set_cookie(
        key="access_token", 
        value=tokens["access_token"],
        httponly=True, 
        secure=(settings.DEBUG == False), 
        samesite="lax", 
        max_age=(604800 if data.remember_me else 3600)
    )
    response.set_cookie(
        key="refresh_token", 
        value=tokens["refresh_token"],
        httponly=True, 
        secure=(settings.DEBUG == False), 
        samesite="lax", 
        max_age=(2592000 if data.remember_me else 604800)
    )

    AuditService.log(
        db, 
        action=AuditAction.USER_LOGIN,
        actor_user_id=str(user.id),
        ip_address=request.client.host if request.client else None
    )

    return success_response("Login successful", {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role.name
        }
    })


@router.post("/logout")
async def logout(
    request: Request, 
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Logout user."""
    
    token = request.cookies.get("access_token")

    TokenService.invalidate_session(db, token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    AuditService.log(
        db, 
        action=AuditAction.USER_LOGOUT,
        actor_user_id=str(user.id)
    )

    return success_response("Logged out successfully")


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token cookie."""

    old_token = request.cookies.get("refresh_token")

    if not old_token:
        raise HTTPException(
            status_code=401,
            detail=error_response("MISSING_TOKEN", "No refresh token provided")
        )

    tokens = TokenService.refresh_access_token(db, old_token)

    if not tokens:
        raise HTTPException(
            status_code=401,
            detail=error_response("INVALID_TOKEN", "Invalid or expired refresh token")
        )

    access_max_age = 604800 if tokens["remember_me"] else 3600
    refresh_max_age = 2592000 if tokens["remember_me"] else 604800

    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=(settings.DEBUG == False),
        samesite="lax",
        max_age=access_max_age
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=(settings.DEBUG == False),
        samesite="lax",
        max_age=refresh_max_age
    )

    # Tokens are only ever sent via httpOnly cookies, never in the body -
    # returning them here would let anything that can read the fetch
    # response (e.g. an XSS payload) grab them despite httpOnly.
    return success_response("Token refreshed")


@router.get("/me")
async def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get current user info.
    
    Returns user data with profile information.
    Matches Database Specification: Table 1 (users) and Table 2 (profiles).
    """
    
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    # Formatted to match Profile schema specification
    return success_response("User fetched", {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "role": user.role.name,
        "is_verified": user.is_verified,
        "profile": {
            "first_name": profile.first_name if profile else None,
            "last_name": profile.last_name if profile else None,
            "department": profile.department if profile else None,
            "expertise": profile.expertise if profile else None,
            "bio": profile.bio if profile else None,
        } if profile else None
    })