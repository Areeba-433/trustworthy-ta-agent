from pydantic import BaseModel
from typing import Optional

class UpdateStatusRequest(BaseModel):
    is_active: bool

class UserAdminOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool