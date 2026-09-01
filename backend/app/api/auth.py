from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.database import getDb
from app.models.user import User
from app.core.security import verifyPassword
from app.core.middleware.auth import getCurrentUser, security
from app.services.tokenService import TokenService
from app.services.auditService import AuditService
from app.schemas.auth import LoginRequest, RefreshRequest, LoginResponse
from datetime import datetime

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, data: LoginRequest, db: Session = Depends(getDb)):
    user = db.query(User).filter(
        (User.email == data.email_or_username) | (User.username == data.email_or_username)
    ).first()

    if not user or not verifyPassword(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    tokens = TokenService.createSession(
        db        = db,
        userId    = user.id,
        rememberMe= data.remember_me,
        ip        = request.client.host,
        userAgent = request.headers.get("user-agent", "")
    )

    user.last_login = datetime.utcnow()
    db.commit()

    AuditService.log(db, action="user_login", userId=user.id,
                     entityType="user", entityId=user.id,
                     ipAddress=request.client.host,
                     userAgent=request.headers.get("user-agent", ""))

    return {**tokens, "token_type": "bearer", "user": user, "role": user.role.name}


@router.post("/logout")
async def logout(request: Request, credentials=Depends(security), db: Session = Depends(getDb)):
    user = await getCurrentUser(request, credentials, db)
    TokenService.invalidateSession(db, credentials.credentials)
    AuditService.log(db, action="user_logout", userId=user.id,
                     ipAddress=request.client.host)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refreshToken(data: RefreshRequest, db: Session = Depends(getDb)):
    newToken = TokenService.refreshAccessToken(db, data.refresh_token)
    if not newToken:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    return {"access_token": newToken}


@router.get("/me")
async def getMe(request: Request, credentials=Depends(security), db: Session = Depends(getDb)):
    user    = await getCurrentUser(request, credentials, db)
    profile = user.profile

    return {
        "id":         user.id,
        "email":      user.email,
        "username":   user.username,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "role":       user.role.name,
        "profile": {
            "phone_number":    profile.phone_number    if profile else None,
            "department":      profile.department      if profile else None,
            "expertise":       profile.expertise       if profile else [],
            "enrollment_year": profile.enrollment_year if profile else None,
            "semester":        profile.semester        if profile else None,
            "cgpa":            float(profile.cgpa)     if profile and profile.cgpa else None,
        }
    }