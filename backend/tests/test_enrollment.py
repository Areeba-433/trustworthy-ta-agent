import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.schemas.course import CourseCreate
from app.services.course_service import CourseService
from app.services.enrollment_service import (
    AlreadyEnrolledError,
    CourseNotFoundByCodeError,
    EnrollmentService,
)

TEACHER = uuid.uuid4()
STUDENT_A = uuid.uuid4()
STUDENT_B = uuid.uuid4()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine, tables=[Course.__table__, Enrollment.__table__]
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_course(db):
    return CourseService(db).create_course(
        TEACHER, CourseCreate(name="AI", code="AI-101")
    )


def test_create_course_generates_join_code(db):
    c = make_course(db)
    assert c.join_code and len(c.join_code) == 6


def test_two_courses_have_different_join_codes(db):
    a = make_course(db)
    b = make_course(db)
    assert a.join_code != b.join_code


def test_join_with_valid_code(db):
    course = make_course(db)
    svc = EnrollmentService(db)
    joined = svc.join_by_code(STUDENT_A, course.join_code)
    assert joined.id == course.id
    assert len(svc.list_student_courses(STUDENT_A)) == 1


def test_join_with_lowercase_code(db):
    course = make_course(db)
    svc = EnrollmentService(db)
    joined = svc.join_by_code(STUDENT_A, course.join_code.lower())
    assert joined.id == course.id


def test_join_with_bad_code(db):
    make_course(db)
    with pytest.raises(CourseNotFoundByCodeError):
        EnrollmentService(db).join_by_code(STUDENT_A, "ZZZZZZ")


def test_double_join_is_rejected(db):
    course = make_course(db)
    svc = EnrollmentService(db)
    svc.join_by_code(STUDENT_A, course.join_code)
    with pytest.raises(AlreadyEnrolledError):
        svc.join_by_code(STUDENT_A, course.join_code)


def test_two_students_join_same_course(db):
    course = make_course(db)
    svc = EnrollmentService(db)
    svc.join_by_code(STUDENT_A, course.join_code)
    svc.join_by_code(STUDENT_B, course.join_code)
    assert len(svc.list_student_courses(STUDENT_A)) == 1
    assert len(svc.list_student_courses(STUDENT_B)) == 1


def test_leave_removes_enrollment(db):
    course = make_course(db)
    svc = EnrollmentService(db)
    svc.join_by_code(STUDENT_A, course.join_code)
    svc.leave_course(STUDENT_A, course.id)
    assert svc.list_student_courses(STUDENT_A) == []