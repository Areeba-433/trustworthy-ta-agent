"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router


# Create FastAPI application
app = FastAPI(
    title="Trustworthy TA Agent",
    version="1.0.0",
    description="AI-powered educational support system with trustworthiness mechanisms",
)

# ============================================================
# Include Routers
# ============================================================

# Authentication routes (Registration + Login + Logout + Refresh + Me)
app.include_router(auth_router, prefix="/api/v1")

# Add any other routers here as they are created
# Example:
# app.include_router(profile_router, prefix="/api/v1")
# app.include_router(admin_router, prefix="/api/v1")

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