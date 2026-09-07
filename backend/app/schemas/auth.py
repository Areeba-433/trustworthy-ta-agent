from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict
from typing import Any
import re


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
    role: str


# ⬇️ ADD THESE NEW SCHEMAS ⬇️

class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for reset password."""
    token: str
    new_password: str = Field(..., min_length=8)

    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


# Helper functions (keep these as they are)
def success_response(message: str, data: Any = None):
    return {"success": True, "message": message, "data": data}


def error_response(code: str, message: str):
    return {"success": False, "error": {"code": code, "message": message}}