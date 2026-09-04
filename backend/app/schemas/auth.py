from pydantic import BaseModel
from pydantic.config import ConfigDict
from typing import Optional, Any

class LoginRequest(BaseModel):
    identifier: str
    password: str
    remember_me: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    first_name: str
    last_name: str
    role: str

def successResponse(message: str, data: Any = None):
    return {"success": True, "message": message, "data": data}

def errorResponse(code: str, message: str):
    return {"success": False, "error": {"code": code, "message": message}}