from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.middleware.auth import get_current_user
from app.models.user import User
from app.services.user_service import UserService
from app.schemas.user import UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current user profile."""
    user = await get_current_user(request, db)
    user_service = UserService(db)
    
    try:
        profile_data = user_service.get_user_profile(str(user.id))
        return {
            "success": True,
            "message": "User fetched",
            "data": profile_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": str(e)
                }
            }
        )


@router.put("/me")
async def update_me(
    request: Request,
    update_data: UpdateProfileRequest,
    db: Session = Depends(get_db)
):
    """Update current user profile."""
    user = await get_current_user(request, db)
    user_service = UserService(db)
    
    try:
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        profile_data = user_service.update_profile(str(user.id), update_dict)
        return {
            "success": True,
            "message": "Profile updated successfully",
            "data": profile_data
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": str(e)
                }
            }
        )