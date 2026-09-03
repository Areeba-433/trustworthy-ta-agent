"""
Database connection configuration using SQLAlchemy.
This file sets up the connection to PostgreSQL and creates
database sessions for our application.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create SQLAlchemy engine
# This establishes the connection to PostgreSQL
engine = create_engine(settings.DATABASE_URL)

# SessionLocal creates a new database session for each request
# This is like a "workspace" where we interact with the database
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
# Every table will inherit from this
Base = declarative_base()

# Dependency for FastAPI routes
# This function gives each API request its own database session
def get_db():
    """
    Creates a database session for each request and closes it after.
    This ensures proper cleanup and prevents connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
