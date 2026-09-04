from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.db.database import getDb
from app.core.middleware.auth import getCurrentUser
from app.core.security import verifyPassword
from app.services.tokenService import TokenService
from app.services.auditService import AuditService
from app.models.auditLog import AuditAction
from app.models.user import User
from app.schemas.auth import LoginRequest, successResponse, errorResponse
from datetime import datetime

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login")
async def login(request: Request, response: Response,
                data: LoginRequest, db: Session = Depends(getDb)):

    user = db.query(User).filter(
        (User.email == data.identifier) | (User.username == data.identifier)
    ).first()

    if not user or not verifyPassword(data.password, user.password_hash):
        # Failed login bhi log karo
        AuditService.log(db, action=AuditAction.LOGIN_FAILED,
                         description=f"Failed login attempt for: {data.identifier}",
                         ipAddress=request.client.host)
        raise HTTPException(status_code=401,
                            detail=errorResponse("INVALID_CREDENTIALS", "Invalid identifier or password"))
    if not user.is_active:
        raise HTTPException(status_code=403,
                            detail=errorResponse("ACCOUNT_DEACTIVATED", "Account is deactivated"))
    if not user.is_verified:
        raise HTTPException(status_code=403,
                            detail=errorResponse("EMAIL_NOT_VERIFIED", "Email not verified"))

    tokens = TokenService.createSession(
        db         = db,
        userId     = str(user.id),
        role       = user.role.name,
        rememberMe = data.remember_me,
        ip         = request.client.host,
        userAgent  = request.headers.get("user-agent", "")
    )

    # HttpOnly cookies set karo
    accessMaxAge  = 604800  if data.remember_me else 3600
    refreshMaxAge = 2592000 if data.remember_me else 604800

    response.set_cookie(key="access_token",  value=tokens["access_token"],
                        httponly=True, secure=True, samesite="lax", max_age=accessMaxAge)
    response.set_cookie(key="refresh_token", value=tokens["refresh_token"],
                        httponly=True, secure=True, samesite="lax", max_age=refreshMaxAge)

    user.last_login = datetime.utcnow()
    db.commit()

    AuditService.log(db, action=AuditAction.USER_LOGIN,
                     actorUserId=str(user.id), ipAddress=request.client.host)

    return successResponse("Login successful", {
        "user": {
            "id":         str(user.id),
            "email":      user.email,
            "username":   user.username,
            "first_name": user.first_name,
            "last_name":  user.last_name,
            "role":       user.role.name,
        }
    })


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(getDb)):
    user = await getCurrentUser(request, db)
    token = request.cookies.get("access_token")
    TokenService.invalidateSession(db, token)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    AuditService.log(db, action=AuditAction.USER_LOGOUT,
                     actorUserId=str(user.id), ipAddress=request.client.host)
    return successResponse("Logged out successfully")


@router.post("/refresh")
async def refreshToken(request: Request, response: Response, db: Session = Depends(getDb)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401,
                            detail=errorResponse("MISSING_TOKEN", "Refresh token not found"))

    newToken = TokenService.refreshAccessToken(db, token)
    if not newToken:
        raise HTTPException(status_code=401,
                            detail=errorResponse("INVALID_TOKEN", "Invalid or expired refresh token"))

    # Cookie mein set karo — JS ko expose mat karo
    response.set_cookie(key="access_token", value=newToken,
                        httponly=True, secure=True, samesite="lax", max_age=3600)

    return successResponse("Token refreshed")


@router.get("/me")
async def getMe(request: Request, db: Session = Depends(getDb)):
    user    = await getCurrentUser(request, db)
    profile = user.profile
    return successResponse("User fetched", {
        "id":         str(user.id),
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
    })