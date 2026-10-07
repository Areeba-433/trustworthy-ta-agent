import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.middleware.auth import get_current_user
from app.main import app
from app.services.course_service import CourseNotFoundError

client = TestClient(app, raise_server_exceptions=False, headers={"x-test-suite": "true"})

TEACHER_ID = uuid.uuid4()


def fake_course(**overrides):
    now = datetime.now(timezone.utc)
    data = dict(
        id=uuid.uuid4(),
        teacher_id=TEACHER_ID,
        name="Artificial Intelligence",
        code="AI-101",
        description="Intro",
        ta_id=None,
        join_code="ABC123",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def _user(role):
    user = MagicMock()
    user.id = TEACHER_ID
    user.role.name = role
    return user


@pytest.fixture
def as_teacher():
    app.dependency_overrides[get_current_user] = lambda: _user("TEACHER")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield
    app.dependency_overrides = {}


@pytest.fixture
def as_student():
    app.dependency_overrides[get_current_user] = lambda: _user("STUDENT")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield
    app.dependency_overrides = {}


def test_unauthenticated_gets_401():
    res = client.get("/api/v1/courses")
    assert res.status_code == 401


def test_student_cannot_list_courses(as_student):
    assert client.get("/api/v1/courses").status_code == 403


def test_teacher_creates_course(as_teacher):
    with patch("app.api.v1.courses.CourseService") as svc:
        svc.return_value.create_course.return_value = fake_course()
        res = client.post(
            "/api/v1/courses",
            json={"name": "Artificial Intelligence", "code": "AI-101"},
        )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["course"]["join_code"] == "ABC123"
    assert body["data"]["course"]["ta_id"] is None


def test_create_course_rejects_blank_name(as_teacher):
    assert client.post("/api/v1/courses", json={"name": "   "}).status_code == 422


def test_get_course_not_found(as_teacher):
    with patch("app.api.v1.courses.CourseService") as svc:
        svc.return_value.get_course.side_effect = CourseNotFoundError()
        res = client.get(f"/api/v1/courses/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json()["detail"]["error"]["code"] == "COURSE_NOT_FOUND"
