"""
Tests for authentication API endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)


def test_register_success():
    """Test successful user registration."""
    # Use unique email with timestamp to avoid conflicts
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
    assert data["data"]["role"] == "STUDENT"


def test_register_duplicate_email():
    """Test that duplicate email is rejected."""
    # Use a unique email for this test
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
            "email": test_email,  # ← SAME EMAIL!
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
            "username": test_username,      # ← FIRST USERNAME
            "email": test_email1,
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    # Second registration with same username but DIFFERENT email
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": test_username,      # ← SAME USERNAME!
            "email": test_email2,           # ← DIFFERENT EMAIL
            "password": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "role": "STUDENT"
        }
    )
    
    assert response.status_code == 409
    data = response.json()
    # ✅ Now this should be USERNAME_ALREADY_EXISTS
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