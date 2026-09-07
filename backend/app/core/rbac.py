from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.middleware.auth import get_current_user
from app.models.user import User


def require_role(required_role: str):
    async def dependency(request: Request, db: Session = Depends(get_db)):
        current_user = await get_current_user(request, db)
        if current_user.role.name != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": "Administrator access is required."
                }}
            )
        return current_user
    return dependency