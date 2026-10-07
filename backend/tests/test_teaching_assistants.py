import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.middleware.auth import get_current_user
from app.models.teaching_assistant import TAStatus
from app.services.course_provider import DummyCourseProvider

client = TestClient(app, raise_server_exceptions=False, headers={"x-test-suite": "true"})

BASE = "/api/v1/teaching-assistants"
TEACHER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TA_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


# -- Fixtures ---------------------------------------------------------------
@pytest.fixture
def mock_teacher():
    teacher = MagicMock()
    teacher.id = TEACHER_ID
    teacher.role.name = "TEACHER"
    return teacher


@pytest.fixture
def mock_student():
    student = MagicMock()
    student.id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    student.role.name = "STUDENT"
    return student


@pytest.fixture
def mock_ta():
    ta = MagicMock()
    ta.id = TA_ID
    ta.teacher_id = TEACHER_ID
    ta.name = "AI Assistant"
    ta.description = "Helps with the AI course"
    ta.status = TAStatus.DRAFT
    ta.created_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    ta.updated_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
    return ta


# -- Helpers ----------------------------------------------------------------
def override(user, fake_db=None):
    app.dependency_overrides[get_current_user] = lambda: user
    if fake_db is not None:
        app.dependency_overrides[get_db] = lambda: fake_db


def clear_overrides():
    app.dependency_overrides = {}


def db_returning(ta):
    """Fake DB whose 'find one TA' query returns `ta` (or None)."""
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = ta
    return fake_db


# -- RBAC -------------------------------------------------------------------
def test_student_cannot_list_tas(mock_student):
    override(mock_student)
    try:
        res = client.get(BASE)
        assert res.status_code == 403
        assert res.json()["detail"]["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    finally:
        clear_overrides()


def test_student_cannot_create_ta(mock_student):
    override(mock_student)
    try:
        res = client.post(BASE, json={"name": "Nope"})
        assert res.status_code == 403
    finally:
        clear_overrides()


# -- Create -----------------------------------------------------------------
def test_teacher_can_create_ta(mock_teacher):
    fake_db = MagicMock()

    def fake_refresh(ta):          # what the database would fill in
        ta.id = TA_ID
        ta.created_at = datetime(2026, 10, 5, tzinfo=timezone.utc)
        ta.updated_at = datetime(2026, 10, 5, tzinfo=timezone.utc)

    fake_db.refresh.side_effect = fake_refresh
    override(mock_teacher, fake_db)
    try:
        res = client.post(BASE, json={"name": "  AI Assistant  ", "description": "Helps"})
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["name"] == "AI Assistant"          # whitespace trimmed
        assert data["status"] == "DRAFT"               # new TAs start as DRAFT
        assert data["teacher_id"] == str(TEACHER_ID)   # owner = logged-in teacher
        fake_db.add.assert_called_once()
        fake_db.commit.assert_called_once()
    finally:
        clear_overrides()


def test_create_ta_rejects_blank_name(mock_teacher):
    override(mock_teacher, MagicMock())
    try:
        res = client.post(BASE, json={"name": "   "})
        assert res.status_code == 422
    finally:
        clear_overrides()


# -- List / get -------------------------------------------------------------
def test_teacher_can_list_tas(mock_teacher, mock_ta):
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_ta]
    override(mock_teacher, fake_db)
    try:
        res = client.get(BASE)
        assert res.status_code == 200
        tas = res.json()["data"]["teaching_assistants"]
        assert len(tas) == 1
        assert tas[0]["id"] == str(TA_ID)
    finally:
        clear_overrides()


def test_get_ta_returns_404_when_missing_or_not_owned(mock_teacher):
    # The service filters by teacher_id, so another teacher's TA looks
    # exactly like a missing one: the query returns nothing.
    override(mock_teacher, db_returning(None))
    try:
        res = client.get(f"{BASE}/{TA_ID}")
        assert res.status_code == 404
        assert res.json()["detail"]["error"]["code"] == "TA_NOT_FOUND"
    finally:
        clear_overrides()


# -- Update / delete --------------------------------------------------------
def test_teacher_can_update_ta(mock_teacher, mock_ta):
    fake_db = db_returning(mock_ta)
    override(mock_teacher, fake_db)
    try:
        res = client.put(f"{BASE}/{TA_ID}", json={"name": "ML Assistant", "status": "ACTIVE"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["name"] == "ML Assistant"
        assert data["status"] == "ACTIVE"
        fake_db.commit.assert_called_once()
    finally:
        clear_overrides()


def test_update_ta_rejects_unknown_status(mock_teacher, mock_ta):
    override(mock_teacher, db_returning(mock_ta))
    try:
        res = client.put(f"{BASE}/{TA_ID}", json={"status": "SLEEPING"})
        assert res.status_code == 422
    finally:
        clear_overrides()


def test_teacher_can_delete_ta(mock_teacher, mock_ta):
    fake_db = db_returning(mock_ta)
    override(mock_teacher, fake_db)
    try:
        res = client.delete(f"{BASE}/{TA_ID}")
        assert res.status_code == 200
        fake_db.delete.assert_called_once_with(mock_ta)
        fake_db.commit.assert_called_once()
    finally:
        clear_overrides()


# -- Course stub ------------------------------------------------------------
def test_course_stub_returns_agreed_shape():
    # This test must still pass when the stub is replaced by real Course data.
    courses = DummyCourseProvider().get_courses_for_ta(TEACHER_ID, TA_ID)
    assert isinstance(courses, list)
    for course in courses:
        assert {"id", "name", "code"} <= set(course)