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
            access_exp = timedelta(minutes=settings.REMEMBER_ME_ACCESS_EXPIRE_MINUTES)
            refresh_exp = timedelta(minutes=settings.REMEMBER_ME_REFRESH_EXPIRE_MINUTES)
        else:
            access_exp = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            refresh_exp = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        access_token = create_access_token({"sub": user_id, "role": role}, access_exp)
        refresh_token = create_refresh_token({"sub": user_id, "role": role}, refresh_exp)

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        session = SessionModel(
            user_id=user_id,
            token_jti=access_payload["jti"],
            refresh_token_hash=refresh_token,
            remember_me=remember_me,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + access_exp,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return {"access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    def invalidate_session(db: Session, token: str):
        payload = decode_token(token)
        if not payload:
            return
        jti = payload.get("jti")
        session = db.query(SessionModel).filter(
            SessionModel.token_jti == jti
        ).first()
        if session:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def revoke_all_sessions(db: Session, user_id: str):
        db.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.revoked_at.is_(None)
        ).update({"revoked_at": datetime.now(timezone.utc)})
        db.commit()

    @staticmethod
    def _is_inactive(session: SessionModel) -> bool:
        if not session.last_activity_at:
            return False
        delta = datetime.now(timezone.utc) - session.last_activity_at.replace(tzinfo=timezone.utc)
        return delta > timedelta(minutes=settings.SESSION_INACTIVITY_MINUTES)

    @staticmethod
    def refresh_access_token(db: Session, old_refresh_token: str):
        payload = decode_token(old_refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        session = db.query(SessionModel).filter(
            SessionModel.refresh_token_hash == old_refresh_token,
            SessionModel.revoked_at.is_(None)
        ).first()

        if not session:
            compromised = db.query(SessionModel).filter(
                SessionModel.refresh_token_hash == old_refresh_token
            ).first()
            if compromised:
                TokenService.revoke_all_sessions(db, str(compromised.user_id))
            return None

        if TokenService._is_inactive(session):
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
            return None

        new_access = create_access_token({"sub": payload["sub"], "role": payload.get("role")})
        new_refresh = create_refresh_token({"sub": payload["sub"], "role": payload.get("role")})
        new_payload = decode_token(new_access)
        refresh_payload = decode_token(new_refresh)

        session.token_jti = new_payload["jti"]
        session.refresh_token_hash = new_refresh
        session.last_activity_at = datetime.now(timezone.utc)
        db.commit()
        return {"access_token": new_access, "refresh_token": new_refresh}