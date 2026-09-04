"""
Profile model - represents the 'profiles' table.
Stores user personal information separately from authentication data.
"""

from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base


class Profile(Base):
    """
    Profile model - one per user.
    
    Attributes:
        id: Unique identifier
        user_id: Foreign key to User (one-to-one)
        first_name: User's first name
        last_name: User's last name
        profile_picture_url: Avatar/photo URL
        department: Academic department (for teachers)
        expertise: Areas of expertise (for teachers)
        bio: User biography
    """
    __tablename__ = "profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    profile_picture_url = Column(Text, nullable=True)
    department = Column(String(150), nullable=True)
    expertise = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Profile {self.first_name} {self.last_name} for User {self.user_id}>"
