import time
import logging
from fastapi import Request
from app.core.security import decode_token

logger = logging.getLogger("tta.requests")

async def logging_middleware(request: Request, call_next):
    start    = time.time()
    user_id  = None

    token = request.cookies.get("access_token")
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("sub")

    response   = await call_next(request)
    duration   = round((time.time() - start) * 1000, 2)
    user_agent = request.headers.get("user-agent", "unknown")

    logger.info(
        f"{request.method} {request.url.path} | "
        f"user={user_id} | ip={request.client.host} | "
        f"agent={user_agent} | status={response.status_code} | {duration}ms"
    )
    return response