import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import HTTPException, Query
from jose import jwt, JWTError

SECRET = os.getenv("JWT_SECRET", "change-me")
ALG = "HS256"
EXP_MIN = 60 * 24  # 24 hours


def make_token(name: str, email: str, is_admin: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "name": name or "",
        "email": email,
        "adm": bool(is_admin),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=EXP_MIN),
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)


def verify_token(token: str = Query(...)) -> Dict[str, Any]:
    """
    FastAPI dependency. Reads token from query param: ?token=...
    """
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALG])
        return {
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "is_admin": bool(data.get("adm", False)),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
