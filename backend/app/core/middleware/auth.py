from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.models.user import User
from app.models.session import Session as SessionModel


async def get_current_user(request: Request, db: Session):
    """
    Get current user from JWT token.
    
    Validates:
    1. Token exists in cookie
    2. Token is valid and not expired
    3. User exists and is active (is_active=True)
    4. User is verified (is_verified=True)
    5. Session exists and is not revoked
    
    Matches:
    - Database Specification: Table 1 - users (no deleted_at column)
    - Database Specification: Table 3 - sessions (uses token_jti, revoked_at)
    - Security Specification: Section 9 - Session Validation
    """
    # 1. Get token from cookie
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "MISSING_TOKEN", "message": "Not authenticated"
            }}
        )

    # 2. Decode and validate token
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "INVALID_TOKEN", "message": "Invalid or expired token"
            }}
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")

    # 3. Get user from database
    # ✅ FIXED: Removed User.deleted_at.is_(None) - this column doesn't exist
    # Matches Database Specification: Table 1 - users
    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "USER_NOT_FOUND", "message": "User not found"
            }}
        )

    # 4. Check if user is active (matches Security Spec Section 24)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "ACCOUNT_INACTIVE", "message": "Account inactive"
            }}
        )

    # 5. Check if user is verified (matches Security Spec Section 15)
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "error": {
                "code": "EMAIL_NOT_VERIFIED", "message": "Email not verified"
            }}
        )

    # 6. Check if session exists and is valid
    # ✅ FIXED: Changed SessionModel.jti to SessionModel.token_jti
    # ✅ FIXED: Removed SessionModel.is_active (not in schema)
    # Matches Database Specification: Table 3 - sessions
    session = db.query(SessionModel).filter(
        SessionModel.token_jti == jti,  # ← Fixed: jti → token_jti
        SessionModel.revoked_at.is_(None)  # ← Session revocation via revoked_at
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {
                "code": "SESSION_EXPIRED", "message": "Session expired"
            }}
        )

    return user