"""
TeachingAssistantService.

One-to-one with Course. Teachers do not create TAs directly — a TA is
created in the same transaction when a course is created (see CourseService).
This service is for reading and updating the TA that already exists.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.teaching_assistant import TAStatus, TeachingAssistant
from app.schemas.teaching_assistant import TAUpdate


class TANotFoundError(Exception):
    """Raised when the course has no TA, or the caller cannot see it."""


class TAAccessDeniedError(Exception):
    """Raised when the caller does not own the parent course."""


class TeachingAssistantService:
    def __init__(self, db: Session):
        self.db = db

    def _owned_course(self, teacher_id: UUID, course_id: UUID) -> Course:
        course = (
            self.db.query(Course)
            .filter(
                Course.id == course_id,
                Course.teacher_id == teacher_id,
                Course.is_active.is_(True),
            )
            .first()
        )
        if course is None:
            raise TAAccessDeniedError()
        return course

    # ---------- create (called only by CourseService) ----------

    def create_for_course(
        self,
        teacher_id: UUID,
        course_id: UUID,
        name: str,
        status: TAStatus = TAStatus.DRAFT,
    ) -> TeachingAssistant:
        """Called from CourseService.create_course. Does NOT commit —
        the caller commits both rows together."""
        ta = TeachingAssistant(
            course_id=course_id,
            teacher_id=teacher_id,
            name=name,
            status=status,
        )
        self.db.add(ta)
        self.db.flush()  # populates ta.id without committing
        return ta

    # ---------- read ----------

    def get_for_course(self, teacher_id: UUID, course_id: UUID) -> TeachingAssistant:
        self._owned_course(teacher_id, course_id)
        ta = (
            self.db.query(TeachingAssistant)
            .filter(
                TeachingAssistant.course_id == course_id,
                TeachingAssistant.teacher_id == teacher_id,
            )
            .first()
        )
        if ta is None:
            raise TANotFoundError()
        return ta

    # ---------- update ----------

    def update_for_course(
        self,
        teacher_id: UUID,
        course_id: UUID,
        data: TAUpdate,
    ) -> TeachingAssistant:
        self._owned_course(teacher_id, course_id)
        ta = (
            self.db.query(TeachingAssistant)
            .filter(
                TeachingAssistant.course_id == course_id,
                TeachingAssistant.teacher_id == teacher_id,
            )
            .first()
        )
        if ta is None:
            raise TANotFoundError()

        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(ta, field, value)
        self.db.commit()
        self.db.refresh(ta)
        return ta