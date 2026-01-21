# api/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

from fastapi import HTTPException, Query
from jose import jwt, JWTError

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")  # set in Render env
JWT_ALG = "HS256"
JWT_EXP_MIN = int(os.getenv("JWT_EXP_MIN", "1440"))  # 24h default


def _is_admin_email(email: str) -> bool:
    # Simple rule for now. You can change later (e.g. ADMIN_EMAILS env).
    return email.lower().endswith("@ksg.ac.ke")


def make_token(name: Optional[str], email: str) -> Tuple[str, Dict[str, Any]]:
    user = {
        "name": name or "",
        "email": email,
        "is_admin": _is_admin_email(email),
    }

    payload = {
        "sub": email,
        "adm": user["is_admin"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MIN),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token, user


def verify_token(token: str = Query(...)) -> Dict[str, Any]:
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return {"email": data["sub"], "is_admin": bool(data.get("adm", False))}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
