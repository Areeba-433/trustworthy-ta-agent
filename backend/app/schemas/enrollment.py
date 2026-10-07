from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.teaching_assistant import TAOut


class JoinByCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=12)


class EnrolledCourseOut(BaseModel):
    """What a student sees about a course they joined.

    Intentionally does NOT include:
      - join_code   (would let the student re-share the code)
      - teacher_id  (not needed by the student UI)

    Includes a read-only `ta` block for display.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: Optional[str]
    description: Optional[str]
    ta: Optional[TAOut] = None
    created_at: Optional[datetime] = None