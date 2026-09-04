import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mockUser():
    user = MagicMock()
    user.id         = "550e8400-e29b-41d4-a716-446655440000"
    user.email      = "areeba@test.com"
    user.username   = "areeba"
    user.first_name = "Areeba"
    user.last_name  = "Minhas"
    user.is_active  = True
    user.is_verified= True
    user.password_hash = "hashed"
    user.role.name  = "student"
    user.profile    = None
    return user

@pytest.fixture
def loginPayload():
    return {"identifier": "areeba@test.com", "password": "Test@1234", "remember_me": False}

# ── Login Tests ──────────────────────────────────────────────────────────────

def test_login_success(mockUser, loginPayload):
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.TokenService.createSession",
               return_value={"access_token": "acc", "refresh_token": "ref"}), \
         patch("app.api.auth.AuditService.log"), \
         patch("app.db.database.getDb") as mockDb:

        mockDb.return_value.__next__ = MagicMock(return_value=MagicMock(
            query=MagicMock(return_value=MagicMock(
                filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=mockUser)))
            ))
        ))
        res = client.post("/api/v1/auth/login", json=loginPayload)

    assert res.status_code == 200
    body = res.json()
    assert body["success"] == True
    assert "user" in body["data"]

def test_login_wrong_password(loginPayload):
    with patch("app.api.auth.verifyPassword", return_value=False), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=loginPayload)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

def test_login_inactive_user(mockUser, loginPayload):
    mockUser.is_active = False
    with patch("app.api.auth.verifyPassword", return_value=True):
        res = client.post("/api/v1/auth/login", json=loginPayload)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"

def test_login_unverified_user(mockUser, loginPayload):
    mockUser.is_verified = False
    with patch("app.api.auth.verifyPassword", return_value=True):
        res = client.post("/api/v1/auth/login", json=loginPayload)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

def test_login_sets_httponly_cookie(mockUser, loginPayload):
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.TokenService.createSession",
               return_value={"access_token": "acc", "refresh_token": "ref"}), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=loginPayload)
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies

# ── Logout Tests ─────────────────────────────────────────────────────────────

def test_logout_success():
    with patch("app.api.auth.getCurrentUser") as mockGetUser, \
         patch("app.api.auth.TokenService.invalidateSession"), \
         patch("app.api.auth.AuditService.log"):
        mockGetUser.return_value = MagicMock(id="uuid", role=MagicMock(name="student"))
        res = client.post("/api/v1/auth/logout",
                          cookies={"access_token": "valid_token"})
    assert res.status_code == 200
    assert res.json()["success"] == True

def test_logout_no_cookie():
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 401

# ── Refresh Tests ─────────────────────────────────────────────────────────────

def test_refresh_success():
    with patch("app.api.auth.TokenService.refreshAccessToken",
               return_value="new_access_token"):
        res = client.post("/api/v1/auth/refresh",
                          cookies={"refresh_token": "valid_refresh"})
    assert res.status_code == 200
    assert res.json()["success"] == True
    assert "access_token" in res.cookies

def test_refresh_no_cookie():
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "MISSING_TOKEN"

def test_refresh_invalid_token():
    with patch("app.api.auth.TokenService.refreshAccessToken", return_value=None):
        res = client.post("/api/v1/auth/refresh",
                          cookies={"refresh_token": "bad_token"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_TOKEN"

# ── /me Tests ─────────────────────────────────────────────────────────────────

def test_get_me_success():
    with patch("app.api.auth.getCurrentUser") as mockGetUser:
        user         = MagicMock()
        user.id      = "uuid"
        user.email   = "areeba@test.com"
        user.username= "areeba"
        user.first_name = "Areeba"
        user.last_name  = "Minhas"
        user.role.name  = "student"
        user.profile    = None
        mockGetUser.return_value = user
        res = client.get("/api/v1/auth/me",
                         cookies={"access_token": "valid_token"})
    assert res.status_code == 200
    assert res.json()["data"]["email"] == "areeba@test.com"

def test_get_me_no_cookie():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

# ── Rate Limit Test ───────────────────────────────────────────────────────────

def test_rate_limit_login():
    payload = {"identifier": "x", "password": "x", "remember_me": False}
    for _ in range(5):
        client.post("/api/v1/auth/login", json=payload)
    res = client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"