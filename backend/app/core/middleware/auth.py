from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.models.user import User
from app.models.session import Session as SessionModel

async def get_current_user(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "MISSING_TOKEN", "message": "Not authenticated"
            }}
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "INVALID_TOKEN", "message": "Invalid or expired token"
            }}
        )

    user_id = payload.get("sub")
    jti     = payload.get("jti")

    user = db.query(User).filter(
        User.id == user_id,
        User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"success": False, "error": {"code": "USER_NOT_FOUND", "message": "User not found"}})
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"success": False, "error": {"code": "ACCOUNT_INACTIVE", "message": "Account inactive"}})
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"success": False, "error": {"code": "EMAIL_NOT_VERIFIED", "message": "Email not verified"}})

    session = db.query(SessionModel).filter(
        SessionModel.jti        == jti,
        SessionModel.is_active  == True,
        SessionModel.revoked_at.is_(None)
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail={"success": False, "error": {"code": "SESSION_EXPIRED", "message": "Session expired"}})

    return user