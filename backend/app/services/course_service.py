from typing import List
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.join_codes import generate_join_code
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseUpdate


class CourseNotFoundError(Exception):
    """Raised when a course does not exist OR belongs to another teacher.
    Both cases look identical on purpose, so UUIDs cannot be probed."""


class CourseService:
    """Course operations. Every query is scoped by teacher_id (ownership)."""

    def __init__(self, db: Session):
        self.db = db

    def create_course(self, teacher_id: UUID, data: CourseCreate) -> Course:
        for _ in range(5):
            course = Course(
                teacher_id=teacher_id,
                name=data.name,
                code=data.code,
                description=data.description,
                join_code=generate_join_code(),
                ta_id=None,
                is_active=True,
            )
            self.db.add(course)
            try:
                self.db.commit()
                self.db.refresh(course)
                return course
            except IntegrityError:
                self.db.rollback()
                continue
        raise RuntimeError("Could not generate a unique join code")

    def list_courses(self, teacher_id: UUID) -> List[Course]:
        return (
            self.db.query(Course)
            .filter(Course.teacher_id == teacher_id, Course.is_active.is_(True))
            .order_by(Course.created_at.desc())
            .all()
        )

    def get_course(self, teacher_id: UUID, course_id: UUID) -> Course:
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
            raise CourseNotFoundError()
        return course

    def update_course(self, teacher_id: UUID, course_id: UUID, data: CourseUpdate) -> Course:
        course = self.get_course(teacher_id, course_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(course, field, value)
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete_course(self, teacher_id: UUID, course_id: UUID) -> None:
        """Soft delete: keeps the row so future TA/chat data is not orphaned."""
        course = self.get_course(teacher_id, course_id)
        course.is_active = False
        self.db.commit()