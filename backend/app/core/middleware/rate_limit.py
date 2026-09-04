from fastapi import Request, HTTPException, status
from collections import defaultdict
from datetime import datetime, timedelta

_store: dict = defaultdict(list)

# v1 paths — updated
LIMITS = {
    "/api/v1/auth/login":           (5,   60),
    "/api/v1/auth/register":        (3, 3600),
    "/api/v1/auth/forgot-password": (3, 3600),
}
DEFAULT_AUTH   = (100, 60)
DEFAULT_UNAUTH = (20,  60)

async def rateLimitMiddleware(request: Request, callNext):
    path = request.url.path
    ip   = request.client.host
    key  = f"{ip}:{path}"

    isAuthenticated = "access_token" in request.cookies
    maxCalls, window = LIMITS.get(path,
        DEFAULT_AUTH if isAuthenticated else DEFAULT_UNAUTH
    )

    now         = datetime.utcnow()
    _store[key] = [t for t in _store[key] if now - t < timedelta(seconds=window)]

    if len(_store[key]) >= maxCalls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"success": False, "error": {"code": "RATE_LIMITED", "message": "Too many requests"}}
        )

    _store[key].append(now)
    return await callNext(request)