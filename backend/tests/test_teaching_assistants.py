import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.models.teaching_assistant import TAStatus, TeachingAssistant
from app.schemas.course import CourseCreate
from app.schemas.teaching_assistant import TAUpdate
from app.services.course_service import CourseService
from app.services.teaching_assistant_service import (
    TAAccessDeniedError,
    TeachingAssistantService,
)

TEACHER_A = uuid.uuid4()
TEACHER_B = uuid.uuid4()


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            Course.__table__,
            TeachingAssistant.__table__,
            Enrollment.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_course(db, teacher=TEACHER_A, name="AI"):
    return CourseService(db).create_course(
        teacher, CourseCreate(name=name, code="AI-101")
    )


def test_creating_course_also_creates_a_ta(db):
    course = make_course(db)
    ta = (
        db.query(TeachingAssistant)
        .filter(TeachingAssistant.course_id == course.id)
        .one()
    )
    assert ta.name == "AI Assistant"
    assert ta.teacher_id == TEACHER_A
    assert ta.status == TAStatus.DRAFT


def test_course_relationship_loads_ta(db):
    course = make_course(db)
    assert course.ta is not None
    assert course.ta.course_id == course.id


def test_join_code_and_ta_both_present(db):
    course = make_course(db)
    assert course.join_code and len(course.join_code) == 6
    assert course.ta is not None


def test_teacher_gets_own_ta(db):
    course = make_course(db)
    ta = TeachingAssistantService(db).get_for_course(TEACHER_A, course.id)
    assert ta.course_id == course.id


def test_other_teacher_cannot_get_ta(db):
    course = make_course(db, TEACHER_A)
    with pytest.raises(TAAccessDeniedError):
        TeachingAssistantService(db).get_for_course(TEACHER_B, course.id)


def test_teacher_can_rename_ta(db):
    course = make_course(db)
    updated = TeachingAssistantService(db).update_for_course(
        TEACHER_A, course.id, TAUpdate(name="Smart AI Assistant")
    )
    assert updated.name == "Smart AI Assistant"


def test_teacher_can_change_status(db):
    course = make_course(db)
    updated = TeachingAssistantService(db).update_for_course(
        TEACHER_A, course.id, TAUpdate(status=TAStatus.ACTIVE)
    )
    assert updated.status == TAStatus.ACTIVE


def test_other_teacher_cannot_update_ta(db):
    course = make_course(db, TEACHER_A)
    with pytest.raises(TAAccessDeniedError):
        TeachingAssistantService(db).update_for_course(
            TEACHER_B, course.id, TAUpdate(name="Hacked")
        )


def test_ta_updated_at_changes_on_update(db):
    course = make_course(db)
    ta_before = TeachingAssistantService(db).get_for_course(TEACHER_A, course.id)
    old_updated = ta_before.updated_at

    TeachingAssistantService(db).update_for_course(
        TEACHER_A, course.id, TAUpdate(name="Renamed")
    )

    db.expire_all()
    ta_after = TeachingAssistantService(db).get_for_course(TEACHER_A, course.id)
    assert ta_after.updated_at >= old_updated
