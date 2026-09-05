"""
Security utilities for password hashing and token generation.
This module provides secure password hashing (Argon2id) and
token generation for email verification.
"""

from argon2 import PasswordHasher
import secrets
import hashlib
from datetime import datetime, timedelta, timezone  # ← ADD timezone
from typing import Optional

# ============================================================
# Password Hashing with Argon2id (Direct)
# ============================================================
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
# Token Generation & Hashing
# ============================================================

def generate_verification_token() -> str:
    """
    Generate a secure random verification token.
    
    Uses secrets.token_urlsafe() for cryptographically secure random.
    
    Returns:
        32-byte random token as URL-safe string (43 characters)
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256.
    
    We hash tokens before storing in database.
    This means even if the database is hacked, raw tokens are safe.
    
    Args:
        token: Raw token to hash
        
    Returns:
        Hashed token as hex string (64 characters)
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ============================================================
# Token Expiry
# ============================================================

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