import os
import uuid
from contextlib import contextmanager

import jwt
import psycopg2
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.logic import EXT, MAX_BYTES, detect_type, media_type_for

SECRET = os.environ["JWT_SECRET"]
UPLOAD_DIR = "/data/uploads"

app = FastAPI()


@contextmanager
def conn_cursor():
    conn = psycopg2.connect(host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
                            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"])
    try:
        with conn, conn.cursor() as cur:   # commits on success, rolls back on error
            yield cur
    finally:
        conn.close()


def current_user(authorization: str | None):
    """Return (user_id, role) from the token. Identity never comes from the request body."""
    try:
        p = jwt.decode((authorization or "").replace("Bearer ", ""), SECRET, algorithms=["HS256"])
        return int(p["sub"]), p["role"]
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or missing token")


def require_admin(authorization: str | None):
    user_id, role = current_user(authorization)
    if role != "admin":
        raise HTTPException(403, "Forbidden")
    return user_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload", status_code=201)
async def upload(scholarship_id: int = Form(...), doc_type: str = Form(...),
                    file: UploadFile = File(...), authorization: str = Header(None)):
    user_id, _ = current_user(authorization)

    # 1. Is this a document the scholarship actually asks for?
    with conn_cursor() as cur:
        cur.execute("SELECT required_documents FROM scholarships WHERE id=%s", (scholarship_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Scholarship not found")
    if doc_type not in row[0]:
        raise HTTPException(422, f"'{doc_type}' is not a required document for this scholarship")

    # 2. Size check (read one byte past the limit so oversize files are detected)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File exceeds the 2 MB limit")

    # 3. Type check by file signature
    kind = detect_type(data[:8])
    if kind is None:
        raise HTTPException(415, "Only PDF, JPG or PNG files are allowed")

    # 4. Save under a random name; the original filename is never used on disk
    stored = uuid.uuid4().hex + EXT[kind]
    path = os.path.join(UPLOAD_DIR, stored)
    with open(path, "wb") as f:
        f.write(data)

    # 5. Record it; re-uploading the same document type replaces the old one
    try:
        with conn_cursor() as cur:
            cur.execute("SELECT stored_name FROM documents WHERE user_id=%s AND scholarship_id=%s AND doc_type=%s",
                        (user_id, scholarship_id, doc_type))
            old = cur.fetchone()
            cur.execute("""INSERT INTO documents (user_id, scholarship_id, doc_type, stored_name, original_name)
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT (user_id, scholarship_id, doc_type)
                            DO UPDATE SET stored_name = EXCLUDED.stored_name,
                                            original_name = EXCLUDED.original_name,
                                            verified = FALSE, flagged = FALSE
                            RETURNING id""",
                        (user_id, scholarship_id, doc_type, stored, (file.filename or "")[:255]))
            doc_id = cur.fetchone()[0]
    except Exception:
        os.remove(path)          # don't leave an orphan file if the DB write failed
        raise

    if old and old[0] != stored:   # remove the replaced file
        try:
            os.remove(os.path.join(UPLOAD_DIR, os.path.basename(old[0])))
        except FileNotFoundError:
            pass

    return {"id": doc_id, "doc_type": doc_type, "status": "uploaded"}


@app.get("/documents/mine")
def my_documents(scholarship_id: int, authorization: str = Header(None)):
    user_id, _ = current_user(authorization)
    with conn_cursor() as cur:
        cur.execute("SELECT id, doc_type, verified, flagged FROM documents "
                    "WHERE user_id=%s AND scholarship_id=%s", (user_id, scholarship_id))
        return [{"id": r[0], "doc_type": r[1], "verified": r[2], "flagged": r[3]} for r in cur.fetchall()]


@app.get("/documents")
def list_documents(user_id: int, scholarship_id: int, authorization: str = Header(None)):
    require_admin(authorization)
    with conn_cursor() as cur:
        cur.execute("SELECT id, doc_type, original_name, verified, flagged FROM documents "
                    "WHERE user_id=%s AND scholarship_id=%s", (user_id, scholarship_id))
        return [{"id": r[0], "doc_type": r[1], "original_name": r[2], "verified": r[3], "flagged": r[4]}
                for r in cur.fetchall()]


@app.get("/files/{doc_id}")
def download(doc_id: int, authorization: str = Header(None)):
    user_id, role = current_user(authorization)
    with conn_cursor() as cur:
        cur.execute("SELECT user_id, stored_name FROM documents WHERE id=%s", (doc_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    if role != "admin" and row[0] != user_id:     # owner or admin only
        raise HTTPException(403, "Forbidden")
    path = os.path.join(UPLOAD_DIR, os.path.basename(row[1]))
    if not os.path.exists(path):
        raise HTTPException(404, "File missing from storage")
    return FileResponse(path, media_type=media_type_for(row[1]))


class ReviewIn(BaseModel):
    verified: bool = False
    flagged: bool = False


@app.put("/documents/{doc_id}/review")
def review(doc_id: int, body: ReviewIn, authorization: str = Header(None)):
    require_admin(authorization)
    with conn_cursor() as cur:
        cur.execute("UPDATE documents SET verified=%s, flagged=%s WHERE id=%s RETURNING id",
                    (body.verified, body.flagged, doc_id))
        if not cur.fetchone():
            raise HTTPException(404, "Document not found")
    return {"ok": True}