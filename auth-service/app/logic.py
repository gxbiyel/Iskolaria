import re
import time
import bcrypt
import jwt


def normalize_student_number(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw).upper()


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def valid_email(email: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def make_token(user_id: int, role: str, secret: str, ttl: int = 3600) -> str:
    now = int(time.time())
    # PyJWT requires "sub" to be a string
    return jwt.encode({"sub": str(user_id), "role": role, "iat": now, "exp": now + ttl},
                        secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])