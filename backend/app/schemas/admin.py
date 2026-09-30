from pydantic import BaseModel, validator
from typing import Optional

class UpdateStatusRequest(BaseModel):
    is_active: bool

class UpdateRoleRequest(BaseModel):
    role: str

    @validator('role')
    def validate_role(cls, v):
        if v != "TEACHER":
            raise ValueError('Admins can only grant the TEACHER role. Other role changes are not permitted.')
        return v


class UserAdminOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool