from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.rbac import require_role
from app.models.audit_log import AuditAction
from app.services.token_service import TokenService
from app.services.audit_service import AuditService
from app.schemas.auth import success_response, error_response
from app.models.user import User, UserRole
from app.schemas.admin import UpdateStatusRequest, UpdateRoleRequest

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users")
async def get_users(page: int = 1, limit: int = 20,
                    search: Optional[str] = None,
                    role: Optional[str] = None,
                    status: Optional[str] = None,
                    admin: User = Depends(require_role("ADMIN")),
                    db: Session = Depends(get_db)):
    query = db.query(User)
    
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )
    
    if role:
        query = query.filter(User.role == role)
    
    # ✅ FIX: Add status filter
    if status:
        if status.lower() == "active":
            query = query.filter(User.is_active == True)
        elif status.lower() == "inactive":
            query = query.filter(User.is_active == False)
    
    total = query.count()
    users = query.offset((page-1)*limit).limit(limit).all()
    
    return success_response("Users fetched", {
        "users": [{
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "role": u.role.name,
            "is_active": u.is_active
        } for u in users],
        "pagination": {"page": page, "limit": limit, "total": total}
    })

@router.patch("/users/{user_id}/status")
async def update_status(user_id: str, body: UpdateStatusRequest,
                        admin: User = Depends(require_role("ADMIN")),
                        db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, detail=error_response("USER_NOT_FOUND", "User not found"))

    target.is_active = body.is_active  # type: ignore[assignment]
    action = AuditAction.ACCOUNT_DEACTIVATED if not body.is_active else AuditAction.ACCOUNT_ACTIVATED

    if not body.is_active:
        TokenService.revoke_all_sessions(db, str(target.id))

    AuditService.log(db, action=action, actor_user_id=str(admin.id), target_user_id=str(target.id))
    db.commit()
    return success_response("User status updated", {"user": {"id": str(target.id), "is_active": target.is_active}})


@router.patch("/users/{user_id}/role")
async def update_role(user_id: str, body: UpdateRoleRequest,
                       admin: User = Depends(require_role("ADMIN")),
                       db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, detail=error_response("USER_NOT_FOUND", "User not found"))

    if target.role == UserRole.TEACHER:
        raise HTTPException(400, detail=error_response("ALREADY_TEACHER", "User is already a teacher"))

    target.role = UserRole.TEACHER

    AuditService.log(db, action=AuditAction.ROLE_CHANGED, actor_user_id=str(admin.id), target_user_id=str(target.id))
    db.commit()
    return success_response("User promoted to teacher", {"user": {"id": str(target.id), "role": target.role.name}})
