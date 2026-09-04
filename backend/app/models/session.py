from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.db.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    jti           = Column(String(255), unique=True, nullable=False, index=True)
    token         = Column(Text, unique=True, nullable=False)
    refresh_token = Column(Text, unique=True)
    ip_address    = Column(String(45))
    user_agent    = Column(Text)
    expires_at    = Column(DateTime, nullable=False)
    revoked_at    = Column(DateTime, nullable=True)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, server_default=func.now())
    last_activity = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="sessions")