from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action      = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50))
    entity_id   = Column(Integer)
    old_values  = Column(JSONB)
    new_values  = Column(JSONB)
    ip_address  = Column(String(45))
    user_agent  = Column(Text)
    created_at  = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")