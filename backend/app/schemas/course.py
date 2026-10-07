from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_name(v: Optional[str]) -> str:
    if v is None:
        raise ValueError("name cannot be null")
    v = v.strip()
    if not v:
        raise ValueError("name cannot be empty")
    return v


def _clean_optional(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return _clean_name(v)

    @field_validator("code", "description")
    @classmethod
    def validate_optional(cls, v):
        return _clean_optional(v)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return _clean_name(v)

    @field_validator("code", "description")
    @classmethod
    def validate_optional(cls, v):
        return _clean_optional(v)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_id: UUID
    name: str
    code: Optional[str]
    description: Optional[str]
    ta_id: Optional[UUID]
    join_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
