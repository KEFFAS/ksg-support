import os
from datetime import datetime, timedelta
from jose import jwt, JWTError

SECRET = os.getenv("JWT_SECRET", "change-me")
ALG = "HS256"
EXP_MIN = 60 * 24  # 24 hours

def make_token(user_id: int, is_admin: bool) -> str:
    payload = {
        "sub": str(user_id),
        "adm": bool(is_admin),
        "exp": datetime.utcnow() + timedelta(minutes=EXP_MIN),
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)

def verify_token(token: str):
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALG])
        return {"user_id": int(data["sub"]), "is_admin": bool(data.get("adm", False))}
    except JWTError:
        return None
