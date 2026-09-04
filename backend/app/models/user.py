"""
User model - represents the 'users' table in PostgreSQL.
This stores account information for all users.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    """User roles in the system."""
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class User(Base):
    """
    User model - one row per user account.
    
    Attributes:
        id: Unique identifier (UUID)
        username: Unique username for login
        email: Unique email address
        password_hash: Hashed password (Argon2id)
        role: User role (STUDENT, TEACHER, ADMIN)
        is_active: Account status (deactivated = False)
        is_verified: Email verification status
        timestamps: created_at, updated_at, last_login_at
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<User {self.username} ({self.email})>"
