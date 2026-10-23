from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from . import models

hasher = PasswordHash.recommended()
bearer = HTTPBearer()
ALGORITHM = "HS256"

def hash_password(p: str) -> str:
    return hasher.hash(p)

def verify_password(p: str, h: str) -> bool:
    return hasher.verify(p, h)

def create_token(user: models.User, hours: int = 12) -> str:
    payload = {"sub": str(user.id), "role": user.role,
               "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer),
                     db: Session = Depends(get_db)) -> models.User:
    try:
        data = jwt.decode(cred.credentials, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(models.User, int(data["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token. Please log in again.")
    if not user:
        raise HTTPException(401, "Account not found.")
    return user

def require_role(*roles):
    def checker(user: models.User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "You don't have permission to do this.")
        return user
    return checker