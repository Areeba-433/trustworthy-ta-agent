"""
Core package - central utilities for the application.
This package contains shared functionality used across the app.
"""

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal, get_db

__all__ = [
    "settings",
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
]
