from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JoinByCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=12)


class EnrolledCourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: Optional[str]
    description: Optional[str]
    ta_id: Optional[UUID]
