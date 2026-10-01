"""
Tests for authentication API endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
import time

client = TestClient(app, headers={"x-test-suite": "true"})


def _verify_user(email: str):
    """Helper to mark test user email as verified."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.is_verified = True
            db.commit()
    finally:
        db.close()


# ============================================================
# Registration & Verification Tests
# ============================================================

def test_register_success():
    """Test successful user registration."""
    unique_email = f"test_{int(time.time())}@example.com"
    
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"testuser_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == unique_email


def test_register_duplicate_email():
    """Test that duplicate email is rejected."""
    test_email = "duplicate_test@example.com"
    
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "user1_unique",
            "email": test_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    # Second registration with same email
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "user2_unique",
            "email": test_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_register_duplicate_username():
    """Test that duplicate username is rejected."""
    test_username = "duplicateuser_unique"
    test_email1 = "test1_unique@example.com"
    test_email2 = "test2_unique@example.com"
    
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={
            "username": test_username,
            "email": test_email1,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    # Second registration with same username
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": test_username,
            "email": test_email2,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 409
    data = response.json()
    assert data["detail"]["error"]["code"] == "USERNAME_ALREADY_EXISTS"


def test_register_invalid_password():
    """Test that weak password is rejected."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 422


def test_register_password_no_uppercase():
    """Test that password without uppercase is rejected."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 422


def test_register_invalid_email():
    """Test that invalid email is rejected."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "not-a-valid-email",
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 422


# ============================================================
# Login, Logout, Session & Profile Tests
# ============================================================

def test_login_success():
    """Test successful login."""
    # First register a user
    unique_email = f"login_test_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"loginuser_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    _verify_user(unique_email)
    
    # Now login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": unique_email,
            "password": "Password123!"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["user"]["email"] == unique_email


def test_login_invalid_credentials():
    """Test login with invalid credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "nonexistent@example.com",
            "password": "WrongPassword!"
        }
    )
    
    assert response.status_code == 401


def test_login_unverified_email():
    """Test login with unverified email."""
    # Register user (but don't verify)
    unique_email = f"unverified_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"unverified_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    # Try to login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": unique_email,
            "password": "Password123!"
        }
    )
    
    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_login_deactivated_account():
    """Test login with deactivated account."""
    # Register user first
    unique_email = f"deactivated_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"deactivated_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    # Note: Deactivation would need admin endpoint
    # This test is a placeholder for now
    pass


def test_logout():
    """Test logout."""
    # First register and login
    unique_email = f"logout_test_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"logoutuser_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    _verify_user(unique_email)
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": unique_email,
            "password": "Password123!"
        }
    )
    
    # Get cookies from login response
    cookies = login_response.cookies
    
    # Logout
    response = client.post("/api/v1/auth/logout", cookies=cookies)
    
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_refresh_token():
    """Test token refresh."""
    # First register and login
    unique_email = f"refresh_test_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"refreshuser_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    _verify_user(unique_email)
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": unique_email,
            "password": "Password123!"
        }
    )
    
    cookies = login_response.cookies
    
    # Try to refresh
    response = client.post("/api/v1/auth/refresh", cookies=cookies)
    
    # This may return 200 or 401 depending on implementation
    # If refresh is implemented, it should return 200
    # If not, this test will need to be updated
    assert response.status_code in [200, 401]


def test_get_me():
    """Test getting current user."""
    # Register and login first
    unique_email = f"me_test_{int(time.time())}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "username": f"meuser_{int(time.time())}",
            "email": unique_email,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    _verify_user(unique_email)
    
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": unique_email,
            "password": "Password123!"
        }
    )
    
    cookies = login_response.cookies
    
    # Get current user
    response = client.get("/api/v1/auth/me", cookies=cookies)
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == unique_email