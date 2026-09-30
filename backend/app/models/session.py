"""
Session model - represents the 'sessions' table.
Tracks user sessions and JWT tokens.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Session(Base):
    __tablename__ = "sessions"

    # Section 7: Table 3 - sessions
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_jti = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token_hash = Column(String(500), nullable=True)  # ← No leading space!
    remember_me = Column(Boolean, nullable=False, default=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")