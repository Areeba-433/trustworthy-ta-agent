from pydantic import BaseModel, Field
from typing import Optional


class UpdateProfileRequest(BaseModel):
    """Request body for updating profile."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=150)
    expertise: Optional[str] = None
    bio: Optional[str] = None