"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""

import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = ConfigDict(extra="ignore")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trustworthy_ta")
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 43200))
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    
    # Remember Me Settings
    REMEMBER_ME_ACCESS_EXPIRE_MINUTES: int = int(os.getenv("REMEMBER_ME_ACCESS_EXPIRE_MINUTES", 10080))
    REMEMBER_ME_REFRESH_EXPIRE_MINUTES: int = int(os.getenv("REMEMBER_ME_REFRESH_EXPIRE_MINUTES", 43200))
    
    # ⬇️ ADD THIS LINE ⬇️
    SESSION_INACTIVITY_MINUTES: int = int(os.getenv("SESSION_INACTIVITY_MINUTES", 30))
    
    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Email (SMTP)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 1025))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

# Create a single instance of settings
settings = Settings()