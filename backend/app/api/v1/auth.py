from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import verify_password
from app.core.middleware.auth import get_current_user
from app.services.token_service import TokenService
from app.services.audit_service import AuditService
from app.models.user import User
from app.models.profile import Profile
from app.models.audit_log import AuditAction
from app.schemas.auth import LoginRequest, success_response, error_response

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login")
async def login(request: Request, response: Response,
                data: LoginRequest, db: Session = Depends(get_db)):

    user = db.query(User).filter(
        (User.email == data.identifier) | (User.username == data.identifier)
    ).first()

    if not user or not verify_password(data.password, user.password_hash):
        AuditService.log(db, action=AuditAction.LOGIN_FAILED,
                         description=f"Failed attempt: {data.identifier}",
                         ip_address=request.client.host)
        raise HTTPException(
            status_code=401,
            detail=error_response("INVALID_CREDENTIALS", "Invalid identifier or password")
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail=error_response("ACCOUNT_DEACTIVATED", "Account is deactivated")
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail=error_response("EMAIL_NOT_VERIFIED", "Email not verified")
        )

    tokens = TokenService.create_session(
        db          = db,
        user_id     = str(user.id),
        role        = user.role.name,
        remember_me = data.remember_me,
        ip          = request.client.host,
        user_agent  = request.headers.get("user-agent", "")
    )

    access_max_age  = 604800  if data.remember_me else 3600
    refresh_max_age = 2592000 if data.remember_me else 604800

    response.set_cookie(
        key="access_token", value=tokens["access_token"],
        httponly=True, secure=True, samesite="lax", max_age=access_max_age
    )
    response.set_cookie(
        key="refresh_token", value=tokens["refresh_token"],
        httponly=True, secure=True, samesite="lax", max_age=refresh_max_age
    )

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    # Profile se first_name, last_name lo — User table mein nahi hai
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    AuditService.log(
        db, action=AuditAction.USER_LOGIN,
        actor_user_id=str(user.id),
        ip_address=request.client.host
    )

    return success_response("Login successful", {
        "user": {
            "id":         str(user.id),
            "email":      user.email,
            "username":   user.username,
            "first_name": profile.first_name if profile else None,
            "last_name":  profile.last_name  if profile else None,
            "role":       user.role.name,
        }
    })


@router.post("/logout")
async def logout(request: Request, response: Response,
                 db: Session = Depends(get_db)):

    user  = await get_current_user(request, db)
    token = request.cookies.get("access_token")

    TokenService.invalidate_session(db, token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    AuditService.log(
        db, action=AuditAction.USER_LOGOUT,
        actor_user_id=str(user.id),
        ip_address=request.client.host
    )

    return success_response("Logged out successfully")


@router.post("/refresh")
async def refresh_token(request: Request, response: Response,
                        db: Session = Depends(get_db)):

    old_token = request.cookies.get("refresh_token")

    if not old_token:
        raise HTTPException(
            status_code=401,
            detail=error_response("MISSING_TOKEN", "Refresh token not found")
        )

    tokens = TokenService.refresh_access_token(db, old_token)

    if not tokens:
        raise HTTPException(
            status_code=401,
            detail=error_response("INVALID_TOKEN", "Invalid or expired refresh token")
        )

    response.set_cookie(
        key="access_token", value=tokens["access_token"],
        httponly=True, secure=True, samesite="lax", max_age=3600
    )
    response.set_cookie(
        key="refresh_token", value=tokens["refresh_token"],
        httponly=True, secure=True, samesite="lax", max_age=604800
    )

    return success_response("Token refreshed")


@router.get("/me")
async def get_me(request: Request, db: Session = Depends(get_db)):

    user    = await get_current_user(request, db)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    return success_response("User fetched", {
        "id":         str(user.id),
        "email":      user.email,
        "username":   user.username,
        "first_name": profile.first_name if profile else None,
        "last_name":  profile.last_name  if profile else None,
        "role":       user.role.name,
        "profile": {
            "phone_number":    profile.phone_number    if profile else None,
            "department":      profile.department      if profile else None,
            "expertise":       profile.expertise       if profile else [],
            "enrollment_year": profile.enrollment_year if profile else None,
            "semester":        profile.semester        if profile else None,
            "cgpa":  float(profile.cgpa) if profile and profile.cgpa else None,
        }
    })