from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwdContext = CryptContext(schemes=["argon2"], deprecated="auto")

def hashPassword(password: str) -> str:
    return pwdContext.hash(password)

def verifyPassword(plain: str, hashed: str) -> bool:
    return pwdContext.verify(plain, hashed)

def createAccessToken(data: dict, expires: Optional[timedelta] = None) -> str:
    expiry = expires or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now    = datetime.now(timezone.utc)
    payload = {
        **data,
        "jti":  str(uuid4()),
        "iat":  now,
        "exp":  now + expiry,
        "type": "access"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def createRefreshToken(data: dict, expires: Optional[timedelta] = None) -> str:
    expiry = expires or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    now    = datetime.now(timezone.utc)
    payload = {
        **data,
        "jti":  str(uuid4()),
        "iat":  now,
        "exp":  now + expiry,
        "type": "refresh"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decodeToken(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None