from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.session import Session as SessionModel
from app.core.security import createAccessToken, createRefreshToken, decodeToken

class TokenService:

    @staticmethod
    def createSession(db: Session, userId: str, role: str, rememberMe: bool, ip: str, userAgent: str) -> dict:
        accessExp  = timedelta(days=7)  if rememberMe else timedelta(hours=1)
        refreshExp = timedelta(days=30) if rememberMe else timedelta(days=7)

        accessToken  = createAccessToken({"sub": str(userId), "role": role}, accessExp)
        refreshToken = createRefreshToken({"sub": str(userId), "role": role}, refreshExp)

        accessPayload = decodeToken(accessToken)

        session = SessionModel(
            user_id       = userId,
            jti           = accessPayload["jti"],
            token         = accessToken,
            refresh_token = refreshToken,
            ip_address    = ip,
            user_agent    = userAgent,
            expires_at    = datetime.utcnow() + accessExp,
        )
        db.add(session)
        db.commit()
        return {"access_token": accessToken, "refresh_token": refreshToken}

    @staticmethod
    def invalidateSession(db: Session, token: str):
        session = db.query(SessionModel).filter(SessionModel.token == token).first()
        if session:
            session.is_active  = False
            session.revoked_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def revokeAllSessions(db: Session, userId: str):
        db.query(SessionModel).filter(
            SessionModel.user_id   == userId,
            SessionModel.is_active == True
        ).update({"is_active": False, "revoked_at": datetime.utcnow()})
        db.commit()

    @staticmethod
    def refreshAccessToken(db: Session, refreshToken: str):
        payload = decodeToken(refreshToken)
        if not payload or payload.get("type") != "refresh":
            return None
        session = db.query(SessionModel).filter(
            SessionModel.refresh_token == refreshToken,
            SessionModel.is_active     == True
        ).first()
        if not session:
            return None
        newToken   = createAccessToken({"sub": payload["sub"], "role": payload.get("role")})
        newPayload = decodeToken(newToken)
        session.token         = newToken
        session.jti           = newPayload["jti"]
        session.last_activity = datetime.utcnow()
        db.commit()
        return newToken