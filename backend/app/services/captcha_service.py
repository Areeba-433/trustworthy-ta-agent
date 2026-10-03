import httpx
import warnings
from typing import Optional
from app.core.config import settings

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_captcha(token: str, remote_ip: Optional[str] = None) -> bool:
    """
    Verify a Cloudflare Turnstile token server-side.

    If TURNSTILE_SECRET_KEY isn't configured, CAPTCHA is treated as
    disabled (always passes) so local dev and the test suite keep working
    before real keys are set up. Once a real secret is added to .env,
    enforcement turns on automatically.
    """
    if not settings.TURNSTILE_SECRET_KEY:
        warnings.warn("TURNSTILE_SECRET_KEY not set - CAPTCHA is not being enforced.")
        return True

    if not token:
        return False

    payload = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=payload)
            data = resp.json()
            return bool(data.get("success"))
    except Exception:
        # Network issue talking to Cloudflare - fail closed (reject) rather
        # than silently letting an unverified registration through.
        return False
