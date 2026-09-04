from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta, timezone
from app.core.security import decodeToken

# Time-bound cache — memory leak prevent karne ke liye
_store: dict = {}

LIMITS = {
    "/api/v1/auth/login":           (5,   60),
    "/api/v1/auth/register":        (3, 3600),
    "/api/v1/auth/forgot-password": (3, 3600),
}
DEFAULT_AUTH   = (100, 60)
DEFAULT_UNAUTH = (20,  60)

def isValidToken(request: Request) -> bool:
    # Cookie presence check nahi — actual token validate karo
    token = request.cookies.get("access_token")
    if not token:
        return False
    payload = decodeToken(token)
    return payload is not None and payload.get("type") == "access"

def cleanStore(key: str, window: int):
    now = datetime.now(timezone.utc)
    if key in _store:
        _store[key] = [t for t in _store[key] if now - t < timedelta(seconds=window)]
    # Purane keys evict karo — memory leak prevent
    keysToDelete = [k for k, v in _store.items() if not v]
    for k in keysToDelete:
        del _store[k]

async def rateLimitMiddleware(request: Request, callNext):
    path = request.url.path

    # X-Forwarded-For — reverse proxy ke peeche sahi IP
    ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    key = f"{ip}:{path}"

    authenticated = isValidToken(request)
    maxCalls, window = LIMITS.get(path,
        DEFAULT_AUTH if authenticated else DEFAULT_UNAUTH
    )

    cleanStore(key, window)

    if key not in _store:
        _store[key] = []

    if len(_store[key]) >= maxCalls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"success": False, "error": {
                "code": "RATE_LIMITED",
                "message": f"Too many requests. Max {maxCalls} per {window}s."
            }}
        )

    _store[key].append(datetime.now(timezone.utc))
    return await callNext(request)