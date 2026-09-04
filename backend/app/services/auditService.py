from sqlalchemy.orm import Session
from app.models.auditLog import AuditLog, AuditAction

class AuditService:

    @staticmethod
    def log(db: Session, action: AuditAction, actorUserId: str = None,
            targetUserId: str = None, description: str = None, ipAddress: str = None):
        entry = AuditLog(
            actor_user_id  = actorUserId,
            target_user_id = targetUserId,
            action         = action,
            description    = description,
            ip_address     = ipAddress,
        )
        db.add(entry)
        db.commit()