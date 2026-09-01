import time
import logging
from fastapi import Request
from app.core.security import decodeToken

logger = logging.getLogger("tta.requests")

async def loggingMiddleware(request: Request, callNext):
    start  = time.time()
    userId = None

    authHeader = request.headers.get("Authorization", "")
    if authHeader.startswith("Bearer "):
        payload = decodeToken(authHeader.split(" ")[1])
        if payload:
            userId = payload.get("sub")

    response = await callNext(request)
    duration = round((time.time() - start) * 1000, 2)

    logger.info(
        f"{request.method} {request.url.path} | "
        f"user={userId} | ip={request.client.host} | "
        f"status={response.status_code} | {duration}ms"
    )
    return response