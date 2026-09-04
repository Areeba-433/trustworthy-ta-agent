"""
EmailVerificationToken model - represents the 'email_verification_tokens' table.
Stores hashed verification tokens for email verification.
"""

from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class EmailVerificationToken(Base):
    """
    Email verification token - one per verification request.
    
    Security Note:
        - Raw token is NEVER stored in database
        - Only the hashed version is stored
        - Tokens are single-use (used_at prevents reuse)
        - Tokens expire after 24 hours
    """
    __tablename__ = "email_verification_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        from datetime import datetime
        return self.expires_at < datetime.now(self.expires_at.tzinfo)
    
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        return not self.is_expired() and not self.is_used()
