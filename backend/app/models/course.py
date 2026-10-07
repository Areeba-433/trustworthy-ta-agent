"""
Course model - represents the 'courses' table.

A course belongs to exactly one teacher (the owner).
A course has exactly one TeachingAssistant (created together).
"""

import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    join_code = Column(String(12), nullable=False, unique=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # One-to-one: the TA holds the FK (teaching_assistants.course_id).
    # uselist=False makes it a scalar, not a list.
    ta = relationship(
        "TeachingAssistant",
        uselist=False,
        lazy="joined",
        cascade="all, delete-orphan",
    )