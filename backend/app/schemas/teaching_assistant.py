from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.teaching_assistant import TAStatus


def _clean_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("Name cannot be empty")
    return value


class TACreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return _clean_name(value)


class TAUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[TAStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return _clean_name(value)