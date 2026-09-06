from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.session import Session as SessionModel
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.config import settings

class TokenService:

    @staticmethod
    def create_session(db: Session, user_id: str, role: str,
                       remember_me: bool, ip: str, user_agent: str) -> dict:

        if remember_me:
            access_exp  = timedelta(minutes=settings.REMEMBER_ME_ACCESS_EXPIRE_MINUTES)
            refresh_exp = timedelta(minutes=settings.REMEMBER_ME_REFRESH_EXPIRE_MINUTES)
        else:
            access_exp  = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            refresh_exp = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        access_token  = create_access_token({"sub": user_id, "role": role}, access_exp)
        refresh_token = create_refresh_token({"sub": user_id, "role": role}, refresh_exp)

        access_payload = decode_token(access_token)

        session = SessionModel(
            user_id       = user_id,
            jti           = access_payload["jti"],
            token         = access_token,
            refresh_token = refresh_token,
            ip_address    = ip,
            user_agent    = user_agent,
            expires_at    = datetime.now(timezone.utc) + access_exp,
        )
        db.add(session)
        db.commit()
        return {"access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    def invalidate_session(db: Session, token: str):
        session = db.query(SessionModel).filter(
            SessionModel.token == token
        ).first()
        if session:
            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def revoke_all_sessions(db: Session, user_id: str):
        db.query(SessionModel).filter(
            SessionModel.user_id   == user_id,
            SessionModel.is_active == True
        ).update({"is_active": False, "revoked_at": datetime.now(timezone.utc)})
        db.commit()

    @staticmethod
    def _is_inactive(session: SessionModel) -> bool:
        if not session.last_activity:
            return False
        delta = datetime.now(timezone.utc) - session.last_activity.replace(tzinfo=timezone.utc)
        return delta > timedelta(minutes=settings.SESSION_INACTIVITY_MINUTES)

    @staticmethod
    def refresh_access_token(db: Session, old_refresh_token: str):
        payload = decode_token(old_refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        session = db.query(SessionModel).filter(
            SessionModel.refresh_token == old_refresh_token,
            SessionModel.is_active     == True,
            SessionModel.revoked_at.is_(None)
        ).first()

        if not session:
            # Possible theft — revoke all
            compromised = db.query(SessionModel).filter(
                SessionModel.refresh_token == old_refresh_token
            ).first()
            if compromised:
                TokenService.revoke_all_sessions(db, str(compromised.user_id))
            return None

        if TokenService._is_inactive(session):
            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
            return None

        new_access  = create_access_token({"sub": payload["sub"], "role": payload.get("role")})
        new_refresh = create_refresh_token({"sub": payload["sub"], "role": payload.get("role")})
        new_payload = decode_token(new_access)

        session.token         = new_access
        session.refresh_token = new_refresh
        session.jti           = new_payload["jti"]
        session.last_activity = datetime.now(timezone.utc)
        db.commit()
        return {"access_token": new_access, "refresh_token": new_refresh}