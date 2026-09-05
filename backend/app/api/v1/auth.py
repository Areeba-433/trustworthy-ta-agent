"""
Authentication API routes for user registration and verification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re

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
from app.services.email_service import send_verification_email

# ============================================================
# Pydantic Schemas
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
        """Validate role is valid."""
        if v not in ["STUDENT", "TEACHER"]:
            raise ValueError('Role must be STUDENT or TEACHER')
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
    verification.used_at = get_token_expiry()  # Using get_token_expiry as current time
    user.is_verified = True
    
    db.commit()
    
    return VerifyEmailResponse(
        success=True,
        message="Email verified successfully! You can now log in."
    )