from pydantic import BaseModel
from pydantic import ConfigDict
from typing import Any

class LoginRequest(BaseModel):
    identifier:  str
    password:    str
    remember_me: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:         str
    email:      str
    username:   str
    role:       str

def success_response(message: str, data: Any = None):
    return {"success": True, "message": message, "data": data}

def error_response(code: str, message: str):
    return {"success": False, "error": {"code": code, "message": message}}