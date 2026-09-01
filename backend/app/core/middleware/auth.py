from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.security import decodeToken
from app.models.user import User
from app.models.session import Session as SessionModel

security = HTTPBearer()

async def getCurrentUser(request: Request, credentials: HTTPAuthorizationCredentials, db: Session):
    token = credentials.credentials

    payload = decodeToken(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    userId = int(payload.get("sub"))
    user   = db.query(User).filter(User.id == userId, User.deleted_at == None).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive")

    session = db.query(SessionModel).filter(
        SessionModel.token     == token,
        SessionModel.is_active == True
    ).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return user