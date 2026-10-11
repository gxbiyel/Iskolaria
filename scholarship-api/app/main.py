import os
from contextlib import contextmanager
from datetime import date

import psycopg2
from fastapi import Depends, FastAPI, HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from app.auth_util import require_admin
from app.logic import check_eligibility
from pydantic import BaseModel, Field

app = FastAPI()


@contextmanager
def conn_cursor():
    conn = psycopg2.connect(host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
                            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"])
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:  # rows come back as dicts
            yield cur
    finally:
        conn.close()


class ScholarshipIn(BaseModel):
    title: str
    description: str = ""
    max_gwa: float
    max_income: float
    year_levels: list[int]
    slots_total: int
    deadline: date
    required_documents: list[str]
    is_open: bool = True
    max_gwa: float = Field(ge=1, le=5)
    max_income: float = Field(ge=0)


class EligibilityIn(BaseModel):
    scholarship_id: int
    gwa: float
    income: float
    year_level: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/scholarships")
def list_scholarships():
    with conn_cursor() as cur:
        cur.execute("SELECT * FROM scholarships WHERE is_open ORDER BY deadline")
        return cur.fetchall()


@app.get("/scholarships/all")
def list_all_scholarships(_admin: int = Depends(require_admin)):
    with conn_cursor() as cur:
        cur.execute("SELECT * FROM scholarships ORDER BY is_open DESC, deadline")
        return cur.fetchall()


@app.get("/scholarships/{sid}")
def get_scholarship(sid: int):
    with conn_cursor() as cur:
        cur.execute("SELECT * FROM scholarships WHERE id=%s", (sid,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Scholarship not found")
    return row


@app.post("/scholarships", status_code=201)
def create_scholarship(body: ScholarshipIn, _admin: int = Depends(require_admin)):
    if body.slots_total < 1:
        raise HTTPException(422, "slots_total must be at least 1")
    with conn_cursor() as cur:
        cur.execute(
            """INSERT INTO scholarships
                    (title, description, max_gwa, max_income, year_levels,
                    slots_total, slots_remaining, deadline, is_open, required_documents)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (body.title, body.description, body.max_gwa, body.max_income, body.year_levels,
                body.slots_total, body.slots_total,          # slots_remaining = slots_total on create
                body.deadline, body.is_open, body.required_documents))
        return {"id": cur.fetchone()["id"]}


@app.put("/scholarships/{sid}")
def update_scholarship(sid: int, body: ScholarshipIn, _admin: int = Depends(require_admin)):
    with conn_cursor() as cur:
        # If the admin changes the total, shift the remaining slots by the same difference
        cur.execute(
            """UPDATE scholarships SET
                    title=%s, description=%s, max_gwa=%s, max_income=%s, year_levels=%s,
                    slots_remaining = GREATEST(0, slots_remaining + (%s - slots_total)),
                    slots_total=%s, deadline=%s, is_open=%s, required_documents=%s
                WHERE id=%s RETURNING id""",
            (body.title, body.description, body.max_gwa, body.max_income, body.year_levels,
                body.slots_total, body.slots_total, body.deadline, body.is_open,
                body.required_documents, sid))
        if not cur.fetchone():
            raise HTTPException(404, "Scholarship not found")
    return {"ok": True}


@app.post("/eligibility/check")
def eligibility(body: EligibilityIn):
    with conn_cursor() as cur:
        # No "is_open" filter here, so the result can say "Scholarship is closed"
        cur.execute("SELECT * FROM scholarships WHERE id=%s", (body.scholarship_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Scholarship not found")
    return check_eligibility(row, body.gwa, body.income, body.year_level)