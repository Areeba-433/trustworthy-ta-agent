import time
import logging
from fastapi import Request
from app.core.security import decodeToken

logger = logging.getLogger("tta.requests")

async def loggingMiddleware(request: Request, callNext):
    start  = time.time()
    userId = None

    # Cookie se token lo — Authorization header se nahi
    token = request.cookies.get("access_token")
    if token:
        payload = decodeToken(token)
        if payload:
            userId = payload.get("sub")

    response  = await callNext(request)
    duration  = round((time.time() - start) * 1000, 2)
    userAgent = request.headers.get("user-agent", "unknown")

    logger.info(
        f"{request.method} {request.url.path} | "
        f"user={userId} | "
        f"ip={request.client.host} | "
        f"agent={userAgent} | "
        f"status={response.status_code} | "
        f"{duration}ms"
    )
    return response