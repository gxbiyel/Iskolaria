import os
from contextlib import asynccontextmanager, contextmanager

import jwt
import psycopg2
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app import logic

SECRET = os.environ["JWT_SECRET"]


@contextmanager
def conn_cursor():
    conn = psycopg2.connect(host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
                            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"])
    try:
        with conn, conn.cursor() as cur:   # commits on success, rolls back on error
            yield cur
    finally:
        conn.close()


def seed_admin():
    email = logic.normalize_email(os.environ["ADMIN_EMAIL"])
    with conn_cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (email, full_name, password_hash, role) "
                "VALUES (%s, 'Scholarship Officer', %s, 'admin')",
                (email, logic.hash_password(os.environ["ADMIN_PASSWORD"])))


@asynccontextmanager
async def lifespan(app):
    seed_admin()
    yield


app = FastAPI(lifespan=lifespan)


class RegisterIn(BaseModel):
    student_number: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=201)
def register(body: RegisterIn):
    sn = logic.normalize_student_number(body.student_number)
    email = logic.normalize_email(body.email)
    if not logic.valid_email(email) or len(body.password) < 8:
        raise HTTPException(422, "Valid email and a password of at least 8 characters required")
    with conn_cursor() as cur:
        cur.execute("SELECT full_name FROM students WHERE student_number=%s", (sn,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(400, "Student number not found")
        try:
            cur.execute(
                "INSERT INTO users (student_number, email, full_name, password_hash) "
                "VALUES (%s,%s,%s,%s) RETURNING id",
                (sn, email, student[0], logic.hash_password(body.password)))
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(409, "An account already exists for this student number or email")
        return {"id": cur.fetchone()[0], "full_name": student[0]}


@app.post("/login")
def login(body: LoginIn):
    email = logic.normalize_email(body.email)
    with conn_cursor() as cur:
        cur.execute("SELECT id, password_hash, role, full_name FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row or not logic.verify_password(body.password, row[1]):
        raise HTTPException(401, "Invalid email or password")   # same message for both cases
    return {"token": logic.make_token(row[0], row[2], SECRET), "role": row[2], "full_name": row[3]}


@app.get("/me")
def me(authorization: str = Header(None)):
    try:
        payload = logic.decode_token((authorization or "").replace("Bearer ", ""), SECRET)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or missing token")
    return {"id": int(payload["sub"]), "role": payload["role"]}