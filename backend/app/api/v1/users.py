import os
import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from PIL import Image
from app.core.database import get_db
from app.core.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Profile
from app.services.user_service import UserService
from app.schemas.user import UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
# backend/app/api/v1/users.py -> backend/uploads/avatars
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "uploads", "avatars"
)


@router.get("/me")
async def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get current user profile."""
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
    update_data: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update current user profile."""
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


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Upload/replace the current user's profile picture."""

    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "Only JPEG, PNG, or WEBP images are allowed."
                }
            }
        )

    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "Image must be under 5MB."
                }
            }
        )

    # Validate it is actually a decodable image (not just a renamed file
    # with a spoofed content-type), then re-encode it - this also strips
    # any non-image data that might be hiding inside the upload.
    try:
        Image.open(io.BytesIO(contents)).verify()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "INVALID_IMAGE",
                    "message": "The uploaded file is not a valid image."
                }
            }
        )

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": "Profile not found"
                }
            }
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Clean up the previous avatar file so uploads do not accumulate forever.
    if profile.profile_picture_url:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(profile.profile_picture_url))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    filename = f"{user.id}_{uuid.uuid4().hex[:8]}.jpg"
    img.save(os.path.join(UPLOAD_DIR, filename), "JPEG", quality=85)

    profile.profile_picture_url = f"/uploads/avatars/{filename}"
    db.commit()

    return {
        "success": True,
        "message": "Avatar updated",
        "data": {"profile_picture_url": profile.profile_picture_url}
    }
