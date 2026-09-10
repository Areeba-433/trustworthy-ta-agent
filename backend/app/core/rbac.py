from fastapi import Depends, HTTPException, status
from app.core.middleware.auth import get_current_user
from app.models.user import User


def require_role(required_role: str):
    async def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role.name != required_role:
            role_label = required_role.capitalize()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"{role_label} access is required."
                }}
            )
        return current_user
    return dependency