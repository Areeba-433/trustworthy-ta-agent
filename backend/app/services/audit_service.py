
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog, AuditAction

class AuditService:

    @staticmethod
    def log(db: Session, action: AuditAction,
            actor_user_id: str = None, target_user_id: str = None,
            description: str = None, ip_address: str = None):

        entry = AuditLog(
            actor_user_id  = actor_user_id,
            target_user_id = target_user_id,
            action         = action,
            description    = description,
            ip_address     = ip_address,
        )
        db.add(entry)
        db.commit()