from typing import List
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.enrollment import Enrollment


class CourseNotFoundByCodeError(Exception):
    """Join code did not match any active course."""


class AlreadyEnrolledError(Exception):
    """Student has already joined this course."""


class EnrollmentService:
    def __init__(self, db: Session):
        self.db = db

    def join_by_code(self, student_id: UUID, code: str) -> Course:
        normalized = code.strip().upper()
        course = (
            self.db.query(Course)
            .filter(
                Course.join_code == normalized,
                Course.is_active.is_(True),
            )
            .first()
        )
        if course is None:
            raise CourseNotFoundByCodeError()

        enrollment = Enrollment(course_id=course.id, student_id=student_id)
        self.db.add(enrollment)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AlreadyEnrolledError()
        return course

    def list_student_courses(self, student_id: UUID) -> List[Course]:
        return (
            self.db.query(Course)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .filter(
                Enrollment.student_id == student_id,
                Course.is_active.is_(True),
            )
            .order_by(Enrollment.enrolled_at.desc())
            .all()
        )

    def leave_course(self, student_id: UUID, course_id: UUID) -> None:
        enrollment = (
            self.db.query(Enrollment)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
            .first()
        )
        if enrollment is None:
            return
        self.db.delete(enrollment)
        self.db.commit()
