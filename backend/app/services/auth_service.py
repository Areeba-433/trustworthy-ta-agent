"""
Authentication service - handles auth business logic.
"""

from sqlalchemy.orm import Session
from app.models.user import User
from app.models.profile import Profile
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.core.security import get_password_hash, verify_password, generate_verification_token, hash_token, get_token_expiry
from datetime import datetime, timezone


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: Session):
        self.db = db

    # ============================================================
    # Registration & Verification
    # ============================================================

    def register_user(self, register_data):
        """Register a new user."""
        # Check if email exists
        if self.db.query(User).filter(User.email == register_data.email).first():
            raise ValueError("Email already registered")
        
        # Check if username exists
        if self.db.query(User).filter(User.username == register_data.username).first():
            raise ValueError("Username already taken")
        
        # Hash password
        hashed_password = get_password_hash(register_data.password)
        
        # Create user
        user = User(
            username=register_data.username,
            email=register_data.email,
            password_hash=hashed_password,
            role=register_data.role
        )
        self.db.add(user)
        self.db.flush()
        
        # Create profile
        profile = Profile(
            user_id=user.id,
            first_name=register_data.first_name,
            last_name=register_data.last_name
        )
        self.db.add(profile)
        self.db.flush()
        
        # Create verification token
        raw_token = generate_verification_token()
        token_hash = hash_token(raw_token)
        expires_at = get_token_expiry()
        
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(verification_token)
        self.db.commit()
        
        return user, raw_token

    def verify_email(self, token: str) -> bool:
        """Verify user's email using token."""
        token_hash = hash_token(token)
        
        verification = self.db.query(EmailVerificationToken).filter(
            EmailVerificationToken.token_hash == token_hash
        ).first()
        
        if not verification:
            raise ValueError("Invalid verification token")
        
        if verification.expires_at < datetime.now(timezone.utc):
            raise ValueError("Verification token expired")
        
        if verification.used_at is not None:
            raise ValueError("Token already used")
        
        user = self.db.query(User).filter(User.id == verification.user_id).first()
        if not user:
            raise ValueError("User not found")
        
        verification.used_at = datetime.now(timezone.utc)
        user.is_verified = True
        
        self.db.commit()
        return True

    # ============================================================
    # Password Reset
    # ============================================================

    def create_password_reset_token(self, user_id: str) -> str:
        """Create a password reset token for a user."""
        # Delete any existing unused tokens
        existing_tokens = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None)
        ).all()
        for token in existing_tokens:
            self.db.delete(token)
        
        # Generate new token
        raw_token = generate_verification_token()
        token_hash = hash_token(raw_token)
        expires_at = get_token_expiry()  # 24 hours
        
        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        self.db.add(reset_token)
        self.db.commit()
        
        return raw_token

    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset user password using token."""
        from app.models.session import Session as SessionModel
        
        token_hash = hash_token(token)
        
        reset_token = self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash
        ).first()
        
        if not reset_token:
            raise ValueError("Invalid reset token")
        
        if reset_token.expires_at < datetime.now(timezone.utc):
            raise ValueError("Reset token expired")
        
        if reset_token.used_at is not None:
            raise ValueError("Token already used")
        
        user = self.db.query(User).filter(User.id == reset_token.user_id).first()
        if not user:
            raise ValueError("User not found")
        
        user.password_hash = get_password_hash(new_password)
        reset_token.used_at = datetime.now(timezone.utc)
        
        # Revoke all sessions
        self.db.query(SessionModel).filter(
            SessionModel.user_id == user.id,
            SessionModel.revoked_at.is_(None)
        ).update({"revoked_at": datetime.now(timezone.utc)})
        
        self.db.commit()
        return True