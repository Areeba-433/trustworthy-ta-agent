import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email               = Column(String(255), unique=True, nullable=False, index=True)
    username            = Column(String(100), unique=True, nullable=False, index=True)
    password_hash       = Column(String(255), nullable=False)
    is_active           = Column(Boolean, default=True)
    is_verified         = Column(Boolean, default=False)
    profile_picture_url = Column(String, nullable=True)
    last_login          = Column(DateTime(timezone=True), nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at          = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    profile    = relationship("Profile",  back_populates="user", uselist=False)
    sessions   = relationship("Session",  back_populates="user")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.actor_user_id", back_populates="actor")