"""
TeachingAssistant model - represents the 'teaching_assistants' table.

One teacher can own many TAs. One TA can be used by many courses:
the link is courses.ta_id -> teaching_assistants.id (added once the
Course module is merged), so there is deliberately no course_id here.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class TAStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TeachingAssistant(Base):
    __tablename__ = "teaching_assistants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TAStatus), nullable=False, default=TAStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)