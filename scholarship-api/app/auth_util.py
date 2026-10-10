import os
import jwt
from fastapi import Header, HTTPException

SECRET = os.environ["JWT_SECRET"]


def require_admin(authorization: str = Header(None)) -> int:
    try:
        payload = jwt.decode((authorization or "").replace("Bearer ", ""),
                                SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or missing token")
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return int(payload["sub"])