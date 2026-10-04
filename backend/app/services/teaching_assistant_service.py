from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.teaching_assistant import TAStatus, TeachingAssistant
from app.schemas.auth import error_response
from app.schemas.teaching_assistant import TACreate, TAUpdate
from app.services.course_provider import course_provider


class TeachingAssistantService:
    """Business logic for Teaching Assistants. Every query is filtered by
    teacher_id, so a teacher can only ever see or change their own TAs."""

    def __init__(self, db: Session, courses=course_provider):
        self.db = db
        self.courses = courses

    def create_ta(self, teacher_id: UUID, data: TACreate) -> TeachingAssistant:
        ta = TeachingAssistant(
            teacher_id=teacher_id,
            name=data.name,
            description=data.description,
            status=TAStatus.DRAFT,
        )
        self.db.add(ta)
        self.db.commit()
        self.db.refresh(ta)
        return ta

    def list_tas(self, teacher_id: UUID) -> list[TeachingAssistant]:
        return (
            self.db.query(TeachingAssistant)
            .filter(TeachingAssistant.teacher_id == teacher_id)
            .order_by(TeachingAssistant.created_at.desc())
            .all()
        )

    def get_ta(self, teacher_id: UUID, ta_id: UUID) -> TeachingAssistant:
        ta = (
            self.db.query(TeachingAssistant)
            .filter(
                TeachingAssistant.id == ta_id,
                TeachingAssistant.teacher_id == teacher_id,
            )
            .first()
        )
        if not ta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_response("TA_NOT_FOUND", "Teaching Assistant not found"),
            )
        return ta

    def update_ta(self, teacher_id: UUID, ta_id: UUID, data: TAUpdate) -> TeachingAssistant:
        ta = self.get_ta(teacher_id, ta_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("name") is None:
            changes.pop("name", None)      # name is required, never set it to NULL
        if changes.get("status") is None:
            changes.pop("status", None)    # same for status
        for field, value in changes.items():
            setattr(ta, field, value)
        self.db.commit()
        self.db.refresh(ta)
        return ta

    def delete_ta(self, teacher_id: UUID, ta_id: UUID) -> None:
        ta = self.get_ta(teacher_id, ta_id)
        self.db.delete(ta)
        self.db.commit()

    def to_dict(self, ta: TeachingAssistant) -> dict:
        return {
            "id": str(ta.id),
            "teacher_id": str(ta.teacher_id),
            "name": ta.name,
            "description": ta.description,
            "status": ta.status.value,
            "assigned_courses": self.courses.get_courses_for_ta(ta.teacher_id, ta.id),
            "created_at": ta.created_at.isoformat() if ta.created_at else None,
            "updated_at": ta.updated_at.isoformat() if ta.updated_at else None,
        }