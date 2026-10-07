from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.teaching_assistant import TAStatus


def _clean_name(value: Optional[str]) -> str:
    if value is None:
        raise ValueError("name cannot be null")
    value = value.strip()
    if not value:
        raise ValueError("name cannot be empty")
    return value


class TAUpdate(BaseModel):
    """Update a course's TA. course_id and teacher_id cannot be changed."""
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    status: Optional[TAStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return _clean_name(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is None:
            raise ValueError("status cannot be null")
        return value


class TAOut(BaseModel):
    """What the frontend sees about a TA. Embedded in course responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    course_id: UUID
    name: str
    status: TAStatus
    created_at: datetime
    updated_at: datetime