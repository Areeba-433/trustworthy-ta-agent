"""
Authentication API routes for user registration, verification, login, and logout.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re
from datetime import datetime, timezone
from app.core.config import settings

# ============================================================
# Imports
# ============================================================
# Core & Security Imports
# ============================================================

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    generate_verification_token,
    hash_token,
    get_token_expiry,
    is_token_expired,
)
from app.models import User, UserRole, Profile, EmailVerificationToken
from app.services.email_service import send_verification_email, send_password_reset_email

from app.core.middleware.auth import get_current_user
from app.services.token_service import TokenService
from app.services.audit_service import AuditService
from app.models.audit_log import AuditAction
from app.schemas.auth import LoginRequest, success_response, error_response, ForgotPasswordRequest, ResetPasswordRequest

# ============================================================
# Pydantic Schemas (Registration)
# ============================================================

class RegisterRequest(BaseModel):
    """Request body for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
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
        """Public registration is STUDENT-only. Teacher accounts are
        granted by an administrator via PATCH /admin/users/{id}/role."""
        if v != "STUDENT":
            raise ValueError('Public registration only supports the STUDENT role. Teacher accounts are granted by an administrator.')
        return v


class RegisterResponse(BaseModel):
    """Response for user registration."""
    success: bool
    message: str
    data: Optional[dict] = None


class VerifyEmailResponse(BaseModel):
    """Response for email verification."""
    success: bool
    message: str


# ============================================================
# API Routes
# ============================================================

router = APIRouter(prefix="/auth", tags=["authentication"])


# ============================================================
# REGISTRATION & VERIFICATION ENDPOINTS
# ============================================================

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user.
    
    Creates a new user account and sends a verification email.
    """
    
    # 1. Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "EMAIL_ALREADY_EXISTS",
                    "message": "An account with this email already exists."
                }
            }
        )
    
    # 2. Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {
                    "code": "USERNAME_ALREADY_EXISTS",
                    "message": "This username is already taken."
                }
            }
        )
    
    # 3. Hash the password
    hashed_password = get_password_hash(request.password)
    
    # 4. Create user
    user = User(
        username=request.username,
        email=request.email,
        password_hash=hashed_password,
        role=UserRole(request.role),
        is_active=True,
        is_verified=False
    )
    db.add(user)
    db.flush()  # Get the user ID
    
    # 5. Create profile
    profile = Profile(
        user_id=user.id,
        first_name=request.first_name,
        last_name=request.last_name
    )
    db.add(profile)
    db.flush()
    
    # 6. Generate verification token
    raw_token = generate_verification_token()
    token_hash = hash_token(raw_token)
    expires_at = get_token_expiry()
    
    # 7. Store token hash in database
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(verification_token)
    
    # 8. Commit everything
    db.commit()
    
    # 9. Send verification email
    email_sent = send_verification_email(user.email, raw_token)
    
    return RegisterResponse(
        success=True,
        message="Registration successful. Please verify your email address.",
        data={
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "email_sent": email_sent
        }
    )


@router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Verify a user's email address using a verification token.
    """
    
    # 1. Hash the received token
    token_hash = hash_token(token)
    
    # 2. Find the verification record
    verification = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token_hash == token_hash
    ).first()
    
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_VERIFICATION_TOKEN",
                    "message": "The verification link is invalid."
                }
            }
        )
    
    # 3. Check if token is expired
    if is_token_expired(verification.expires_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "VERIFICATION_TOKEN_EXPIRED",
                    "message": "The verification link has expired. Please request a new one."
                }
            }
        )
    
    # 4. Check if token was already used
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
    
    # 5. Verify the user
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
async def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Request password reset email."""
    from app.services.auth_service import AuthService
    
    user = db.query(User).filter(User.email == request.email).first()
    
    if user:
        auth_service = AuthService(db)
        token = auth_service.create_password_reset_token(str(user.id))
        send_password_reset_email(user.email, token)
    
    return {
        "success": True,
        "message": "If an account exists for this email, password reset instructions have been sent."
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using token."""
    from app.services.auth_service import AuthService
    
    try:
        auth_service = AuthService(db)
        auth_service.reset_password(request.token, request.new_password)
        return {
            "success": True,
            "message": "Password reset successful"
        }
    except ValueError as e:
        error_msg = str(e)
        code = "RESET_ERROR"
        
        if "Invalid reset token" in error_msg:
            code = "INVALID_RESET_TOKEN"
        elif "Reset token expired" in error_msg:
            code = "RESET_TOKEN_EXPIRED"
        elif "Token already used" in error_msg:
            code = "TOKEN_ALREADY_USED"
        
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": code,
                    "message": error_msg
                }
            }
        )


# ============================================================
# LOGIN, LOGOUT, REFRESH, ME
# ============================================================

@router.post("/login")
async def login(
    request: Request, 
    response: Response,
    data: LoginRequest, 
    db: Session = Depends(get_db)
):
    """Login user."""
    
    user = db.query(User).filter(
        (User.email == data.identifier) | (User.username == data.identifier)
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        AuditService.log(
            db, 
            action=AuditAction.LOGIN_FAILED,
            description=f"Failed attempt: {data.identifier}",
            ip_address=request.client.host
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
        db          = db,
        user_id     = str(user.id),
        role        = user.role.name,
        remember_me = data.remember_me,
        ip          = request.client.host,
        user_agent  = request.headers.get("user-agent", "")
    )

    access_max_age  = 604800  if data.remember_me else 3600
    refresh_max_age = 2592000 if data.remember_me else 604800

    response.set_cookie(
        key="access_token", value=tokens["access_token"],
        httponly=True, secure=not settings.DEBUG, samesite="lax", max_age=access_max_age
    )
    response.set_cookie(
        key="refresh_token", value=tokens["refresh_token"],
        httponly=True, secure=not settings.DEBUG, samesite="lax", max_age=refresh_max_age
    )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    AuditService.log(
        db, 
        action=AuditAction.USER_LOGIN,
        actor_user_id=str(user.id),
        ip_address=request.client.host
    )

    return success_response("Login successful", {
        "user": {
            "id":         str(user.id),
            "email":      user.email,
            "username":   user.username,
            "first_name": profile.first_name if profile else None,
            "last_name":  profile.last_name  if profile else None,
            "role":       user.role.name,
        }
    })


@router.post("/logout")
async def logout(
    request: Request, 
    response: Response,
    db: Session = Depends(get_db)
):
    """Logout user."""
    
    user  = await get_current_user(request, db)
    token = request.cookies.get("access_token")

    TokenService.invalidate_session(db, token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    AuditService.log(
        db, 
        action=AuditAction.USER_LOGOUT,
        actor_user_id=str(user.id),
        ip_address=request.client.host
    )

    return success_response("Logged out successfully")


@router.post("/refresh")
async def refresh_token(
    request: Request, 
    response: Response,
    db: Session = Depends(get_db)
):
    """Refresh access token."""
    
    old_token = request.cookies.get("refresh_token")

    if not old_token:
        raise HTTPException(
            status_code=401,
            detail=error_response("MISSING_TOKEN", "Refresh token not found")
        )

    tokens = TokenService.refresh_access_token(db, old_token)

    if not tokens:
        raise HTTPException(
            status_code=401,
            detail=error_response("INVALID_TOKEN", "Invalid or expired refresh token")
        )

    remember_me = tokens.get("remember_me", False)
    access_max_age = 604800 if remember_me else 3600
    refresh_max_age = 2592000 if remember_me else 604800

    response.set_cookie(
        key="access_token", 
        value=tokens["access_token"],
        httponly=True, 
        secure=not settings.DEBUG, 
        samesite="lax", 
        max_age=access_max_age
    )
    response.set_cookie(
        key="refresh_token", 
        value=tokens["refresh_token"],
        httponly=True, 
        secure=not settings.DEBUG, 
        samesite="lax", 
        max_age=refresh_max_age
    )

    return success_response("Token refreshed", {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"]
    })


@router.get("/me")
async def get_me(
    request: Request, 
    db: Session = Depends(get_db)
):
    """
    Get current user info.
    
    Returns user data with profile information.
    Matches Database Specification: Table 1 (users) and Table 2 (profiles).
    """
    
    user    = await get_current_user(request, db)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    # Formatted to match Profile schema specification
    return success_response("User fetched", {
        "id":         str(user.id),
        "email":      user.email,
        "username":   user.username,
        "first_name": profile.first_name if profile else None,
        "last_name":  profile.last_name  if profile else None,
        "role":       user.role.name,
        "is_active":  user.is_active,
        "is_verified": user.is_verified,
        "profile": {
            "department": profile.department if profile else None,
            "expertise":  profile.expertise if profile else None,
            "bio":        profile.bio if profile else None,
            "profile_picture_url": profile.profile_picture_url if profile else None,
        }
    })