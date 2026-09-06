from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires: Optional[timedelta] = None) -> str:
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

def create_refresh_token(data: dict, expires: Optional[timedelta] = None) -> str:
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

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None