"""
TeachingAssistant model.

Design: one-to-one with Course.
  - Every course has exactly one TA.
  - Every TA belongs to exactly one course.
The FK lives on the TA side (teaching_assistants.course_id -> courses.id),
which enforces one-to-one via a UNIQUE constraint on course_id.

When a course is hard-deleted, its TA is deleted by the DB (ON DELETE CASCADE).
The teacher_id column is kept for convenience: it lets us run ownership
checks without joining to courses every time.
"""

import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class TAStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TeachingAssistant(Base):
    __tablename__ = "teaching_assistants"
    __table_args__ = (
        UniqueConstraint("course_id", name="uq_teaching_assistants_course_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    teacher_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    name = Column(String(150), nullable=False)

    status = Column(
        Enum(TAStatus, name="ta_status"),
        nullable=False,
        default=TAStatus.DRAFT,
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )