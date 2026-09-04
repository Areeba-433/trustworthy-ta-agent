from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import decodeToken
from app.models.user import User
from app.models.session import Session as SessionModel

async def getCurrentUser(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "MISSING_TOKEN", "message": "Not authenticated"
            }}
        )

    payload = decodeToken(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "INVALID_TOKEN", "message": "Invalid or expired token"
            }}
        )

    userId = payload.get("sub")
    jti    = payload.get("jti")

    # deleted_at.is_(None) — sahi SQLAlchemy way
    user = db.query(User).filter(
        User.id == userId,
        User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "USER_NOT_FOUND", "message": "User not found"
            }}
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "ACCOUNT_INACTIVE", "message": "Account is inactive"
            }}
        )
    # is_verified check — pehle missing tha
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "error": {
                "code": "EMAIL_NOT_VERIFIED", "message": "Email not verified"
            }}
        )

    # JTI se session dhoondhna
    session = db.query(SessionModel).filter(
        SessionModel.jti        == jti,
        SessionModel.is_active  == True,
        SessionModel.revoked_at.is_(None)
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "SESSION_EXPIRED", "message": "Session expired or revoked"
            }}
        )

    return user