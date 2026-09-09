from fastapi import Request, status
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from app.core.security import decode_token

_store: dict = {}

LIMITS = {
    "/api/v1/auth/login":           (5,   60),
    "/api/v1/auth/register":        (3, 3600),
    "/api/v1/auth/forgot-password": (3, 3600),
}
DEFAULT_AUTH   = (100, 60)
DEFAULT_UNAUTH = (20,  60)

def _is_valid_token(request: Request) -> bool:
    token = request.cookies.get("access_token")
    if not token:
        return False
    payload = decode_token(token)
    return payload is not None and payload.get("type") == "access"

def _clean_store(key: str, window: int):
    now = datetime.now(timezone.utc)
    if key in _store:
        _store[key] = [t for t in _store[key] if now - t < timedelta(seconds=window)]
    dead = [k for k, v in _store.items() if not v]
    for k in dead:
        del _store[k]

async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    ip   = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    key  = f"{ip}:{path}"

    authenticated        = _is_valid_token(request)
    max_calls, window    = LIMITS.get(path, DEFAULT_AUTH if authenticated else DEFAULT_UNAUTH)

    _clean_store(key, window)
    if key not in _store:
        _store[key] = []

    if len(_store[key]) >= max_calls:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"success": False, "error": {
                "code": "RATE_LIMITED",
                "message": f"Too many requests. Max {max_calls} per {window}s."
            }}
        )

    _store[key].append(datetime.now(timezone.utc))
    return await call_next(request)