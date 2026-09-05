"""
Tests for security utilities.
"""

import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    generate_verification_token,
    hash_token,
    get_token_expiry,
    is_token_expired,
)


def test_password_hashing():
    """Test that password hashing works."""
    password = "MySecurePassword123!"
    
    # Hash the password
    hashed = get_password_hash(password)
    
    # Verify it's not the same as the original
    assert hashed != password
    assert hashed.startswith("$argon2id$")
    
    # Verify correct password works
    assert verify_password(password, hashed) is True
    
    # Verify wrong password fails
    assert verify_password("WrongPassword", hashed) is False


def test_token_generation():
    """Test that token generation creates unique tokens."""
    token1 = generate_verification_token()
    token2 = generate_verification_token()
    
    # Tokens should be different
    assert token1 != token2
    
    # Tokens should be non-empty strings
    assert len(token1) > 0
    assert len(token2) > 0


def test_token_hashing():
    """Test that token hashing works."""
    token = "test_token_123"
    
    # Hash the token
    hashed = hash_token(token)
    
    # Hash should be different from raw token
    assert hashed != token
    assert len(hashed) == 64  # SHA-256 produces 64 hex characters


def test_token_expiry():
    """Test that token expiry works."""
    expires_at = get_token_expiry()
    
    # Should be 24 hours from now
    assert expires_at is not None
    
    # Token should not be expired immediately
    assert is_token_expired(expires_at) is False


def test_same_password_produces_different_hash():
    """Test that same password produces different hashes (due to salt)."""
    password = "MySecurePassword123!"
    
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)
    
    # Hashes should be different (due to unique salt)
    assert hash1 != hash2
    
    # Both should verify correctly
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True