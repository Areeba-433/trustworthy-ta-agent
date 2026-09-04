from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.db.database import Base

class AuditAction(str, enum.Enum):
    USER_LOGIN          = "USER_LOGIN"
    USER_LOGOUT         = "USER_LOGOUT"
    USER_REGISTERED     = "USER_REGISTERED"
    PASSWORD_RESET      = "PASSWORD_RESET"
    PASSWORD_CHANGED    = "PASSWORD_CHANGED"
    ACCOUNT_ACTIVATED   = "ACCOUNT_ACTIVATED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    ROLE_CHANGED        = "ROLE_CHANGED"
    PROFILE_UPDATED     = "PROFILE_UPDATED"

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action         = Column(Enum(AuditAction), nullable=False, index=True)
    description    = Column(Text)
    ip_address     = Column(String(45))
    created_at     = Column(DateTime, server_default=func.now())

    actor  = relationship("User", foreign_keys=[actor_user_id])
    target = relationship("User", foreign_keys=[target_user_id])