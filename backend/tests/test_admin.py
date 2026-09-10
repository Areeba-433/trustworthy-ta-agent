import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.core.middleware.auth import get_current_user
from app.core.database import get_db

client = TestClient(app, raise_server_exceptions=False, headers={"x-test-suite": "true"})


# ── Fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture
def mock_admin():
    admin = MagicMock()
    admin.id = "11111111-1111-1111-1111-111111111111"
    admin.role.name = "ADMIN"
    return admin


@pytest.fixture
def mock_student():
    student = MagicMock()
    student.id = "22222222-2222-2222-2222-222222222222"
    student.role.name = "STUDENT"
    return student


@pytest.fixture
def mock_target_user():
    target = MagicMock()
    target.id = "33333333-3333-3333-3333-333333333333"
    target.username = "targetuser"
    target.email = "target@test.com"
    target.role.name = "STUDENT"
    target.is_active = True
    return target


# ── Helpers ──────────────────────────────────────────────────────────────
def override_current_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def override_db(fake_db):
    app.dependency_overrides[get_db] = lambda: fake_db


def clear_overrides():
    app.dependency_overrides = {}


# ── TTA-10.6: RBAC gate tests ───────────────────────────────────────────
def test_non_admin_cannot_access_admin_users(mock_student):
    override_current_user(mock_student)
    try:
        res = client.get("/api/v1/admin/users")
        assert res.status_code == 403
        assert res.json()["detail"]["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    finally:
        clear_overrides()


def test_admin_can_access_admin_users(mock_admin):
    override_current_user(mock_admin)
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
    fake_db.query.return_value.offset.return_value.limit.return_value.all.return_value = []
    fake_db.query.return_value.count.return_value = 0
    override_db(fake_db)
    try:
        res = client.get("/api/v1/admin/users")
        assert res.status_code == 200
        assert res.json()["success"] is True
    finally:
        clear_overrides()


# ── TTA-12.7: Admin deactivation flow tests ─────────────────────────────
def test_deactivate_user_by_admin(mock_admin, mock_target_user):
    override_current_user(mock_admin)
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = mock_target_user
    override_db(fake_db)
    try:
        with patch("app.api.v1.admin.TokenService.revoke_all_sessions") as mock_revoke, \
             patch("app.api.v1.admin.AuditService.log") as mock_audit_log:

            res = client.patch(
                f"/api/v1/admin/users/{mock_target_user.id}/status",
                json={"is_active": False}
            )

        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["user"]["is_active"] is False

        mock_revoke.assert_called_once_with(fake_db, str(mock_target_user.id))

        mock_audit_log.assert_called_once()
        _, kwargs = mock_audit_log.call_args
        assert kwargs["action"].name == "ACCOUNT_DEACTIVATED"
        assert kwargs["actor_user_id"] == str(mock_admin.id)
        assert kwargs["target_user_id"] == str(mock_target_user.id)
    finally:
        clear_overrides()


def test_activate_user_by_admin(mock_admin, mock_target_user):
    mock_target_user.is_active = False
    override_current_user(mock_admin)
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = mock_target_user
    override_db(fake_db)
    try:
        with patch("app.api.v1.admin.TokenService.revoke_all_sessions") as mock_revoke, \
             patch("app.api.v1.admin.AuditService.log") as mock_audit_log:

            res = client.patch(
                f"/api/v1/admin/users/{mock_target_user.id}/status",
                json={"is_active": True}
            )

        assert res.status_code == 200
        assert res.json()["data"]["user"]["is_active"] is True
        mock_revoke.assert_not_called()

        mock_audit_log.assert_called_once()
        _, kwargs = mock_audit_log.call_args
        assert kwargs["action"].name == "ACCOUNT_ACTIVATED"
    finally:
        clear_overrides()


def test_deactivate_nonexistent_user_returns_404(mock_admin):
    override_current_user(mock_admin)
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None
    override_db(fake_db)
    try:
        res = client.patch(
            "/api/v1/admin/users/99999999-9999-9999-9999-999999999999/status",
            json={"is_active": False}
        )
        assert res.status_code == 404
        assert res.json()["detail"]["error"]["code"] == "USER_NOT_FOUND"
    finally:
        clear_overrides()