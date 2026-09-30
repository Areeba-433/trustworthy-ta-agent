"""
Wiring smoke tests.

These do not test business logic - they test that routers and middleware
are actually attached to the app. This is exactly the class of bug where
everything looks correct in the source file but is never registered in
main.py / api/v1/__init__.py, so it silently does nothing at runtime.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"x-test-suite": "true"})


def test_admin_routes_are_registered():
    # A 404 means the route does not exist at all (router never wired in).
    # 401/403/422/etc all mean it exists but this request was refused or
    # invalid, which is fine for this check - we only care that routing
    # itself resolves.
    res = client.get("/api/v1/admin/users")
    assert res.status_code != 404, "GET /api/v1/admin/users is not registered"

    res = client.patch("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/status",
                        json={"is_active": False})
    assert res.status_code != 404, "PATCH /api/v1/admin/users/{user_id}/status is not registered"

    res = client.patch("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/role",
                        json={})
    assert res.status_code != 404, "PATCH /api/v1/admin/users/{user_id}/role is not registered"


def test_expected_middleware_is_attached():
    dispatch_names = {
        m.kwargs["dispatch"].__name__
        for m in app.user_middleware
        if "dispatch" in m.kwargs
    }
    assert "rate_limit_middleware" in dispatch_names
    assert "logging_middleware" in dispatch_names
    assert "security_headers_middleware" in dispatch_names


def test_security_headers_present_on_response():
    res = client.get("/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
