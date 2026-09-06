"""
Security utilities for password hashing, token generation, and JWT handling.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
from passlib.context import CryptContext
from jose import JWTError, jwt
import secrets
import hashlib

from app.core.config import settings

# ============================================================
# Password Hashing (Minahil's Version - Argon2id)
# ============================================================

# Using argon2 directly
from argon2 import PasswordHasher
_ph = PasswordHasher()


def get_password_hash(password: str) -> str:
    """
    Hash a password using Argon2id.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string (starts with $argon2id$)
    """
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Password to check
        hashed_password: Stored hash from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return _ph.verify(hashed_password, plain_password)
    except:
        return False


# ============================================================
# Password Hashing (Areeba's Version - Passlib)
# ============================================================

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using passlib."""
    return pwd_context.hash(password)


def verify_password_passlib(plain: str, hashed: str) -> bool:
    """Verify a password using passlib."""
    return pwd_context.verify(plain, hashed)


# ============================================================
# Token Generation & Hashing (Minahil's Version)
# ============================================================

def generate_verification_token() -> str:
    """
    Generate a secure random verification token.
    
    Returns:
        32-byte random token as URL-safe string (43 characters)
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256.
    
    Returns:
        Hashed token as hex string (64 characters)
    """
    return hashlib.sha256(token.encode()).hexdigest()


def get_token_expiry() -> datetime:
    """
    Get token expiry time (24 hours from now).
    
    Returns:
        Datetime 24 hours in the future (timezone-aware)
    """
    return datetime.now(timezone.utc) + timedelta(hours=24)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Check if a token has expired.
    
    Args:
        expires_at: Token expiry datetime (timezone-aware)
        
    Returns:
        True if token has expired, False otherwise
    """
    return datetime.now(timezone.utc) > expires_at


# ============================================================
# JWT Token Functions (Areeba's Version)
# ============================================================

def create_access_token(data: dict, expires: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary with user data (sub, role)
        expires: Optional custom expiry time
        
    Returns:
        JWT token string
    """
    expiry = expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expiry,
        "type": "access"
    }
    # ⬇️ CHANGED: settings.SECRET_KEY → settings.JWT_SECRET_KEY
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary with user data (sub, role)
        expires: Optional custom expiry time
        
    Returns:
        JWT token string
    """
    expiry = expires or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + expiry,
        "type": "refresh"
    }
    # ⬇️ CHANGED: settings.SECRET_KEY → settings.JWT_SECRET_KEY
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        # ⬇️ CHANGED: settings.SECRET_KEY → settings.JWT_SECRET_KEY
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None