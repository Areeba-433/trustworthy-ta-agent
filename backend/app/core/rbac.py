from fastapi import Depends, HTTPException, status
from app.core.middleware.auth import get_current_user
from app.models.user import User


def require_role(*required_roles: str):
    """Gate a route to one or more roles: require_role("ADMIN") or
    require_role("ADMIN", "TEACHER") both work."""
    allowed = set(required_roles)

    async def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role.name not in allowed:
            label = " or ".join(r.capitalize() for r in required_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"success": False, "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"{label} access is required."
                }}
            )
        return current_user
    return dependency