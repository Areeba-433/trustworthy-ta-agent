from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.session import Session as SessionModel
from app.core.security import createAccessToken, createRefreshToken, decodeToken
from app.core.config import settings

class TokenService:

    @staticmethod
    def createSession(db: Session, userId: str, role: str,
                      rememberMe: bool, ip: str, userAgent: str) -> dict:

        if rememberMe:
            accessExp  = timedelta(minutes=settings.REMEMBER_ME_ACCESS_EXPIRE_MINUTES)
            refreshExp = timedelta(minutes=settings.REMEMBER_ME_REFRESH_EXPIRE_MINUTES)
        else:
            accessExp  = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            refreshExp = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

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
            expires_at    = datetime.now(timezone.utc) + accessExp,
        )
        db.add(session)
        db.commit()
        return {"access_token": accessToken, "refresh_token": refreshToken}

    @staticmethod
    def invalidateSession(db: Session, token: str):
        session = db.query(SessionModel).filter(
            SessionModel.token == token
        ).first()
        if session:
            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def revokeAllSessions(db: Session, userId: str):
        db.query(SessionModel).filter(
            SessionModel.user_id   == userId,
            SessionModel.is_active == True
        ).update({
            "is_active":  False,
            "revoked_at": datetime.now(timezone.utc)
        })
        db.commit()

    @staticmethod
    def isSessionExpiredByInactivity(session: SessionModel) -> bool:
        if not session.last_activity:
            return False
        inactiveFor = datetime.now(timezone.utc) - session.last_activity.replace(tzinfo=timezone.utc)
        return inactiveFor > timedelta(minutes=settings.SESSION_INACTIVITY_MINUTES)

    @staticmethod
    def refreshAccessToken(db: Session, oldRefreshToken: str) -> dict | None:
        payload = decodeToken(oldRefreshToken)
        if not payload or payload.get("type") != "refresh":
            return None

        session = db.query(SessionModel).filter(
            SessionModel.refresh_token == oldRefreshToken,
            SessionModel.is_active     == True,
            SessionModel.revoked_at.is_(None)
        ).first()

        if not session:
            # Already used refresh token — possible token theft
            # Puri family revoke karo
            compromisedSession = db.query(SessionModel).filter(
                SessionModel.refresh_token == oldRefreshToken
            ).first()
            if compromisedSession:
                TokenService.revokeAllSessions(db, str(compromisedSession.user_id))
            return None

        # Inactivity check
        if TokenService.isSessionExpiredByInactivity(session):
            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
            return None

        # Refresh Token Rotation — dono naye banao
        newAccessToken  = createAccessToken({
            "sub":  payload["sub"],
            "role": payload.get("role")
        })
        newRefreshToken = createRefreshToken({
            "sub":  payload["sub"],
            "role": payload.get("role")
        })

        newAccessPayload = decodeToken(newAccessToken)

        # Purana revoke karo — naya set karo
        session.token         = newAccessToken
        session.refresh_token = newRefreshToken
        session.jti           = newAccessPayload["jti"]
        session.last_activity = datetime.now(timezone.utc)
        db.commit()

        return {
            "access_token":  newAccessToken,
            "refresh_token": newRefreshToken
        }