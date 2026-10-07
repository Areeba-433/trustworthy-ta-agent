from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_role
from app.models.user import User
from app.schemas.auth import success_response
from app.schemas.teaching_assistant import TACreate, TAUpdate
from app.services.teaching_assistant_service import TeachingAssistantService

router = APIRouter(prefix="/teaching-assistants")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ta(
    data: TACreate,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    service = TeachingAssistantService(db)
    ta = service.create_ta(teacher_id=teacher.id, data=data)
    return success_response("Teaching Assistant created", service.to_dict(ta))


@router.get("")
async def list_tas(
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    service = TeachingAssistantService(db)
    tas = service.list_tas(teacher_id=teacher.id)
    return success_response(
        "Teaching Assistants fetched",
        {"teaching_assistants": [service.to_dict(ta) for ta in tas]},
    )


@router.get("/{ta_id}")
async def get_ta(
    ta_id: UUID,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    service = TeachingAssistantService(db)
    ta = service.get_ta(teacher_id=teacher.id, ta_id=ta_id)
    return success_response("Teaching Assistant fetched", service.to_dict(ta))


@router.put("/{ta_id}")
async def update_ta(
    ta_id: UUID,
    data: TAUpdate,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    service = TeachingAssistantService(db)
    ta = service.update_ta(teacher_id=teacher.id, ta_id=ta_id, data=data)
    return success_response("Teaching Assistant updated", service.to_dict(ta))


@router.delete("/{ta_id}")
async def delete_ta(
    ta_id: UUID,
    teacher: User = Depends(require_role("TEACHER")),
    db: Session = Depends(get_db),
):
    service = TeachingAssistantService(db)
    service.delete_ta(teacher_id=teacher.id, ta_id=ta_id)
    return success_response("Teaching Assistant deleted")