"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.auth import router as auth_router

# Create FastAPI application
app = FastAPI(
    title="Trustworthy TA Agent",
    version="1.0.0",
    description="AI-powered educational support system with trustworthiness mechanisms",
)

# ============================================================
# CORS Configuration (ADD THIS!)
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Include Routers
# ============================================================

app.include_router(auth_router, prefix="/api/v1")

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