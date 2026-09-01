from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    email_or_username: str
    password: str
    remember_me: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    first_name: str
    last_name: str

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserOut
    role: str