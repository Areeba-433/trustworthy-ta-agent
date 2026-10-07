"""
Course model - represents the 'courses' table.

A course belongs to exactly one teacher (the owner).
ta_id is the future link to the teaching_assistants table.
join_code is the short code a student enters to enroll in the course.
"""

import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)

    # Short code students enter to join. Generated server-side on create.
    join_code = Column(String(12), nullable=False, unique=True, index=True)

    # Intentionally NO ForeignKey yet (TA feature adds it later).
    ta_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)