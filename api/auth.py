import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SECRET = os.getenv("JWT_SECRET", "change-me")
ALG = "HS256"
EXP_MIN = 60 * 24  # 24 hours

# Allows Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def make_token(user_id: int, is_admin: bool) -> str:
    payload = {
        "sub": str(user_id),
        "adm": bool(is_admin),
        "exp": datetime.utcnow() + timedelta(minutes=EXP_MIN),
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)


def verify_token(
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(default=None),
):
    """
    Accepts token from:
    1) Authorization: Bearer <token>
    2) ?token=<token> (fallback)
    """

    raw_token = bearer_token or token

    if not raw_token:
        raise HTTPException(status_code=401, detail="Token required")

    try:
        data = jwt.decode(raw_token, SECRET, algorithms=[ALG])
        return {
            "user_id": int(data["sub"]),
            "is_admin": bool(data.get("adm", False)),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
