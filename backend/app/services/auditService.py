from sqlalchemy.orm import Session
from app.models.auditLog import AuditLog

class AuditService:

    @staticmethod
    def log(db: Session, action: str, userId: int = None, entityType: str = None,
            entityId: int = None, oldValues: dict = None, newValues: dict = None,
            ipAddress: str = None, userAgent: str = None):

        entry = AuditLog(
            user_id     = userId,
            action      = action,
            entity_type = entityType,
            entity_id   = entityId,
            old_values  = oldValues,
            new_values  = newValues,
            ip_address  = ipAddress,
            user_agent  = userAgent,
        )
        db.add(entry)
        db.commit()