import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseUpdate
from app.services.course_service import CourseNotFoundError, CourseService

TEACHER_A = uuid.uuid4()
TEACHER_B = uuid.uuid4()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Course.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make(service, teacher, name="AI", code="AI-101"):
    return service.create_course(teacher, CourseCreate(name=name, code=code))


def test_create_sets_defaults(db):
    course = make(CourseService(db), TEACHER_A)
    assert course.id is not None
    assert course.teacher_id == TEACHER_A
    assert course.ta_id is None
    assert course.is_active is True
    assert course.join_code and len(course.join_code) == 6


def test_join_codes_are_unique(db):
    svc = CourseService(db)
    a = make(svc, TEACHER_A, "A1")
    b = make(svc, TEACHER_A, "A2")
    assert a.join_code != b.join_code


def test_list_returns_only_own_active_courses(db):
    service = CourseService(db)
    make(service, TEACHER_A, "A1")
    make(service, TEACHER_A, "A2")
    make(service, TEACHER_B, "B1")
    names = {c.name for c in service.list_courses(TEACHER_A)}
    assert names == {"A1", "A2"}


def test_other_teacher_cannot_get_course(db):
    service = CourseService(db)
    course = make(service, TEACHER_A)
    with pytest.raises(CourseNotFoundError):
        service.get_course(TEACHER_B, course.id)


def test_other_teacher_cannot_update_course(db):
    service = CourseService(db)
    course = make(service, TEACHER_A, "Original")
    with pytest.raises(CourseNotFoundError):
        service.update_course(TEACHER_B, course.id, CourseUpdate(name="Hacked"))
    assert service.get_course(TEACHER_A, course.id).name == "Original"


def test_other_teacher_cannot_delete_course(db):
    service = CourseService(db)
    course = make(service, TEACHER_A)
    with pytest.raises(CourseNotFoundError):
        service.delete_course(TEACHER_B, course.id)
    assert service.get_course(TEACHER_A, course.id).is_active is True


def test_partial_update_changes_only_sent_fields(db):
    service = CourseService(db)
    course = make(service, TEACHER_A, "Old", "AI-101")
    updated = service.update_course(TEACHER_A, course.id, CourseUpdate(name="New"))
    assert updated.name == "New"
    assert updated.code == "AI-101"


def test_delete_is_soft_and_hides_course(db):
    service = CourseService(db)
    course = make(service, TEACHER_A)
    service.delete_course(TEACHER_A, course.id)
    assert db.query(Course).filter(Course.id == course.id).one().is_active is False
    assert service.list_courses(TEACHER_A) == []
    with pytest.raises(CourseNotFoundError):
        service.get_course(TEACHER_A, course.id)
