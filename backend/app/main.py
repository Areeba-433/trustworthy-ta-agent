"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from app.api.v1 import router as api_v1_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware.rate_limit import rate_limit_middleware
from app.core.middleware.logging import logging_middleware
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
# Create FastAPI application
app = FastAPI(
    title="Trustworthy TA Agent",
    version="1.0.0",
    description="AI-powered educational support system with trustworthiness mechanisms",
)

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(logging_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Include Routers
# ============================================================

# Option 1: Use the combined router (Recommended)
# This includes all routes from auth, users, admin, etc.
app.include_router(api_v1_router, prefix="/api/v1")

# Option 2: Individual routers (Alternative)
# app.include_router(auth_router, prefix="/api/v1")

# ============================================================
# Health Check Endpoints
# ============================================================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "Welcome to Trustworthy TA Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

app.include_router(admin_router, prefix="/api/v1")