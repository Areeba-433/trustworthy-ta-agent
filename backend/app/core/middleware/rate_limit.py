from fastapi import Request, HTTPException, status
from collections import defaultdict
from datetime import datetime, timedelta

_store: dict = defaultdict(list)

LIMITS = {
    "/api/auth/login":           (5,   60),
    "/api/auth/register":        (3, 3600),
    "/api/auth/forgot-password": (3, 3600),
}
DEFAULT_AUTH   = (100, 60)
DEFAULT_UNAUTH = (20,  60)

async def rateLimitMiddleware(request: Request, callNext):
    path = request.url.path
    ip   = request.client.host
    key  = f"{ip}:{path}"

    maxCalls, window = LIMITS.get(path,
        DEFAULT_AUTH if request.headers.get("Authorization") else DEFAULT_UNAUTH
    )

    now         = datetime.utcnow()
    _store[key] = [t for t in _store[key] if now - t < timedelta(seconds=window)]

    if len(_store[key]) >= maxCalls:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    _store[key].append(now)
    return await callNext(request)