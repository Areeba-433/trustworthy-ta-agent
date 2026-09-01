from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwdContext = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hashPassword(password: str) -> str:
    return pwdContext.hash(password)

def verifyPassword(plain: str, hashed: str) -> bool:
    return pwdContext.verify(plain, hashed)

def createAccessToken(data: dict, expires: Optional[timedelta] = None) -> str:
    payload = {
        **data,
        "exp": datetime.utcnow() + (expires or timedelta(hours=1)),
        "type": "access"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def createRefreshToken(data: dict, expires: Optional[timedelta] = None) -> str:
    payload = {
        **data,
        "exp": datetime.utcnow() + (expires or timedelta(days=7)),
        "type": "refresh"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decodeToken(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None