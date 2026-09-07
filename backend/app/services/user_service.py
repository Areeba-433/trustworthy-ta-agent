from sqlalchemy.orm import Session
from app.models.user import User
from app.models.profile import Profile
from typing import Optional


class UserService:
    """Service for user operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_profile(self, user_id: str) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
        
        return {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "first_name": profile.first_name if profile else None,
            "last_name": profile.last_name if profile else None,
            "role": user.role.name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "department": profile.department if profile else None,
            "expertise": profile.expertise if profile else None,
            "bio": profile.bio if profile else None,
            "profile_picture_url": profile.profile_picture_url if profile else None
        }
    
    def update_profile(self, user_id: str, update_data: dict) -> dict:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            raise ValueError("Profile not found")
        
        if "first_name" in update_data and update_data["first_name"]:
            profile.first_name = update_data["first_name"]
        if "last_name" in update_data and update_data["last_name"]:
            profile.last_name = update_data["last_name"]
        if "department" in update_data:
            profile.department = update_data["department"]
        if "expertise" in update_data:
            profile.expertise = update_data["expertise"]
        if "bio" in update_data:
            profile.bio = update_data["bio"]
        
        self.db.commit()
        self.db.refresh(profile)
        
        return self.get_user_profile(user_id)