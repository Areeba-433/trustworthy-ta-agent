"""
Models package - exports all models for easier imports.
"""

from app.models.user import User, UserRole
from app.models.profile import Profile
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.session import Session
from app.models.audit_log import AuditLog, AuditAction
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.teaching_assistant import TeachingAssistant, TAStatus

__all__ = [
    "User",
    "UserRole",
    "Profile",
    "EmailVerificationToken",
    "PasswordResetToken",
    "Session",
    "AuditLog",
    "AuditAction",
    "Course",
    "Enrollment",
    "TeachingAssistant",
    "TAStatus",
]