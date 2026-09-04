import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch, AsyncMock

from app.main import app
from app.db.database import Base, getDb

# SQLite in-memory
engine = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setupDb():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides = {}

client = TestClient(app, raise_server_exceptions=True)

# ── Helper ────────────────────────────────────────────────────────────────────

def makeUser(overrides={}):
    user               = MagicMock()
    user.id            = "550e8400-e29b-41d4-a716-446655440000"
    user.email         = "areeba@test.com"
    user.username      = "areeba"
    user.first_name    = "Areeba"
    user.last_name     = "Minhas"
    user.is_active     = True
    user.is_verified   = True
    user.password_hash = "hashed"
    user.role          = MagicMock()
    user.role.name     = "student"
    user.profile       = None
    user.last_login    = None
    for k, v in overrides.items():
        setattr(user, k, v)
    return user

def mockDbWithUser(user):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    app.dependency_overrides[getDb] = lambda: iter([db])
    return db

LOGIN_PAYLOAD = {
    "identifier":  "areeba@test.com",
    "password":    "Test@1234",
    "remember_me": False
}

# ── Login Tests ───────────────────────────────────────────────────────────────

def test_login_success():
    user = makeUser()
    mockDbWithUser(user)
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.TokenService.createSession",
               return_value={"access_token": "acc", "refresh_token": "ref"}), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert res.status_code == 200
    assert res.json()["success"] == True
    assert "user" in res.json()["data"]

def test_login_wrong_password():
    user = makeUser()
    mockDbWithUser(user)
    with patch("app.api.auth.verifyPassword", return_value=False), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "INVALID_CREDENTIALS"

def test_login_inactive_user():
    user = makeUser({"is_active": False})
    mockDbWithUser(user)
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert res.status_code == 403
    assert res.json()["detail"]["error"]["code"] == "ACCOUNT_DEACTIVATED"

def test_login_unverified_user():
    user = makeUser({"is_verified": False})
    mockDbWithUser(user)
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert res.status_code == 403
    assert res.json()["detail"]["error"]["code"] == "EMAIL_NOT_VERIFIED"

def test_login_sets_httponly_cookie():
    user = makeUser()
    mockDbWithUser(user)
    with patch("app.api.auth.verifyPassword", return_value=True), \
         patch("app.api.auth.TokenService.createSession",
               return_value={"access_token": "acc", "refresh_token": "ref"}), \
         patch("app.api.auth.AuditService.log"):
        res = client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert res.status_code == 200
    assert "access_token"  in res.cookies
    assert "refresh_token" in res.cookies

# ── Logout Tests ──────────────────────────────────────────────────────────────

def test_logout_success():
    with patch("app.api.auth.getCurrentUser",
               new_callable=lambda: lambda: AsyncMock(return_value=makeUser())), \
         patch("app.api.auth.TokenService.invalidateSession"), \
         patch("app.api.auth.AuditService.log"):
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
               return_value={"access_token": "new_acc", "refresh_token": "new_ref"}):
        res = client.post("/api/v1/auth/refresh",
                          cookies={"refresh_token": "valid_refresh"})
    assert res.status_code == 200
    assert res.json()["success"] == True
    assert "access_token"  in res.cookies
    assert "refresh_token" in res.cookies

def test_refresh_no_cookie():
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "MISSING_TOKEN"

def test_refresh_invalid_token():
    with patch("app.api.auth.TokenService.refreshAccessToken", return_value=None):
        res = client.post("/api/v1/auth/refresh",
                          cookies={"refresh_token": "bad_token"})
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "INVALID_TOKEN"

# ── /me Tests ─────────────────────────────────────────────────────────────────

def test_get_me_success():
    with patch("app.api.auth.getCurrentUser",
               new_callable=lambda: lambda: AsyncMock(return_value=makeUser())):
        res = client.get("/api/v1/auth/me",
                         cookies={"access_token": "valid_token"})
    assert res.status_code == 200
    assert res.json()["data"]["email"] == "areeba@test.com"

def test_get_me_no_cookie():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

# ── Rate Limit Test ───────────────────────────────────────────────────────────

def test_rate_limit_login():
    # Rate limit store reset karo
    import app.core.middleware.rate_limit as rl
    rl._store.clear()

    payload = {"identifier": "x", "password": "x", "remember_me": False}
    mockDbWithUser(None)

    with patch("app.api.auth.AuditService.log"):
        for _ in range(5):
            client.post("/api/v1/auth/login", json=payload)
        res = client.post("/api/v1/auth/login", json=payload)

    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"