const express = require("express");
const jwt = require("jsonwebtoken");
const Redis = require("ioredis");
const { Pool } = require("pg");
const { canTransition, canCancel, missingDocuments } = require("./logic");

const app = express();
app.use(express.json());

const pool = new Pool({
    host: process.env.DB_HOST,
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
});
const redis = new Redis({ host: process.env.REDIS_HOST || "redis" });

const REF = `'SCH-' || EXTRACT(YEAR FROM created_at)::int || '-' || LPAD(id::text, 5, '0')`;
// Use in queries with joins, where "id" would be ambiguous
const refOf = (t) =>
    `'SCH-' || EXTRACT(YEAR FROM ${t}.created_at)::int || '-' || LPAD(${t}.id::text, 5, '0')`;

// Express 4 does not catch async errors, so wrap handlers
const wrap = (fn) => (req, res, next) => fn(req, res, next).catch(next);

function auth(role) {
    return (req, res, next) => {
        try {
        const p = jwt.verify(
            (req.headers.authorization || "").replace("Bearer ", ""),
            process.env.JWT_SECRET,
        );
        if (role && p.role !== role)
            return res.status(403).json({ detail: "Forbidden" });
        req.user = { id: Number(p.sub), role: p.role }; // identity comes from the token
        next();
        } catch (e) {
        res.status(401).json({ detail: "Invalid or missing token" });
        }
    };
    }

    const queue = (application_id, user_id, status) =>
    redis.lpush(
        "notifications",
        JSON.stringify({ application_id, user_id, status }),
    );

app.get("/health", (req, res) => res.json({ status: "ok" }));

app.post(
    "/applications",
    auth(),
    wrap(async (req, res) => {
        const { scholarship_id, gwa, family_income, year_level, course } = req.body;

        // 1. Eligibility, deadline and closed check, asked of scholarship-api
        const r = await fetch(
        `${process.env.SCHOLARSHIP_API_URL}/eligibility/check`,
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
            scholarship_id,
            gwa,
            income: family_income,
            year_level,
            }),
        },
        );
        if (!r.ok) {
            const err = await r
                .json()
                .catch(() => ({ detail: "Eligibility check failed" }));
            return res.status(r.status).json(err);
        }
        const elig = await r.json();
        if (!elig.eligible)
        return res
            .status(422)
            .json({ detail: "Not eligible", reasons: elig.reasons });

        // 2. All required documents uploaded?
        const sch = await pool.query(
        "SELECT required_documents FROM scholarships WHERE id=$1",
        [scholarship_id],
        );
        const docs = await pool.query(
        "SELECT doc_type FROM documents WHERE user_id=$1 AND scholarship_id=$2",
        [req.user.id, scholarship_id],
        );
        const missing = missingDocuments(
        sch.rows[0].required_documents,
        docs.rows.map((d) => d.doc_type),
        );
        if (missing.length)
        return res.status(422).json({ detail: "Missing documents", missing });

        // 3. Insert. If the student previously CANCELLED, reuse that row; any other existing row is a duplicate.
        const ins = await pool.query(
            `INSERT INTO applications (user_id, scholarship_id, course, gwa, family_income, year_level)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (user_id, scholarship_id) DO UPDATE SET
                course=EXCLUDED.course, gwa=EXCLUDED.gwa, family_income=EXCLUDED.family_income,
                year_level=EXCLUDED.year_level, status='submitted', remarks=NULL,
                created_at=now(), updated_at=now()
            WHERE applications.status='cancelled'
            RETURNING id, ${REF} AS reference_no`,
            [req.user.id, scholarship_id, course, gwa, family_income, year_level],
        );

        if (!ins.rowCount) {
            const ex = await pool.query(
                `SELECT status, ${REF} AS reference_no FROM applications WHERE user_id=$1 AND scholarship_id=$2`,
                [req.user.id, scholarship_id],
            );
            return res.status(409).json({
                detail: "You already applied to this scholarship",
                existing: ex.rows[0],
            });
        }

        await queue(ins.rows[0].id, req.user.id, "submitted");
        res.status(201).json(ins.rows[0]);
    }),
    );

app.get(
    "/applications/mine",
    auth(),
    wrap(async (req, res) => {
        const r = await pool.query(
            `SELECT a.id, ${refOf("a")} AS reference_no, a.status, a.remarks, s.title,
            s.is_open AS scholarship_open
            FROM applications a JOIN scholarships s ON s.id = a.scholarship_id
            WHERE a.user_id=$1 ORDER BY a.created_at DESC`,
            [req.user.id],
        );
        res.json(r.rows);
    }),
);

// Applicant: cancel / revoke my own application
app.put("/applications/:id/cancel", auth(), wrap(async (req, res) => {
    const client = await pool.connect();
    try {
        await client.query("BEGIN");
        // user_id in the WHERE clause = ownership check
        const cur = await client.query(
            `SELECT a.status, a.scholarship_id, s.is_open
            FROM applications a JOIN scholarships s ON s.id = a.scholarship_id
            WHERE a.id=$1 AND a.user_id=$2 FOR UPDATE OF a`,
            [req.params.id, req.user.id],
        );
        if (!cur.rowCount) {
            await client.query("ROLLBACK");
            return res.status(404).json({ detail: "Not found" });
        }
        const row = cur.rows[0];
        if (!row.is_open) {
            await client.query("ROLLBACK");
            return res.status(409).json({ detail: "This scholarship is closed." });
        }
        if (!canCancel(row.status)) {
            await client.query("ROLLBACK");
            return res.status(409).json({ detail: `A ${row.status} application cannot be cancelled` });
        }
        await client.query(
            "UPDATE applications SET status='cancelled', updated_at=now() WHERE id=$1",
            [req.params.id],
        );
        await client.query("COMMIT");
        await queue(Number(req.params.id), req.user.id, "cancelled");
        res.json({ ok: true });
    } catch (e) {
        await client.query("ROLLBACK");
        throw e;
    } finally {
        client.release();
    }
}));

app.put(
    "/applications/:id/status",
    auth("admin"),
    wrap(async (req, res) => {
        const { status, remarks } = req.body;
        const client = await pool.connect();
        try {
        await client.query("BEGIN");
        const cur = await client.query(
            `SELECT a.status, a.scholarship_id, a.user_id, s.is_open
            FROM applications a JOIN scholarships s ON s.id = a.scholarship_id
            WHERE a.id=$1 FOR UPDATE OF a`,
            [req.params.id],
        );
        if (!cur.rowCount) {
            await client.query("ROLLBACK");
            return res.status(404).json({ detail: "Not found" });
        }
        const row = cur.rows[0];
        if (!row.is_open) {
            await client.query("ROLLBACK");
            return res.status(409).json({detail: "This scholarship is closed. Applications can no longer be reviewed.",});
        }
        if (!canTransition(row.status, status)) {
            await client.query("ROLLBACK");
            return res
            .status(409)
            .json({ detail: `Cannot move from ${row.status} to ${status}` });
        }
        if (status === "approved") {
            // atomic slot decrement
            const s = await client.query(
            "UPDATE scholarships SET slots_remaining = slots_remaining - 1 WHERE id=$1 AND slots_remaining > 0 RETURNING id",
            [row.scholarship_id],
            );
            if (!s.rowCount) {
            await client.query("ROLLBACK");
            return res.status(409).json({ detail: "No slots remaining" });
            }
        }
        if (row.status === "approved" && status === "removed") {
            // give the slot back (never above slots_total)
            await client.query(
                "UPDATE scholarships SET slots_remaining = LEAST(slots_total, slots_remaining + 1) WHERE id=$1",
                [row.scholarship_id],
            );
        }
        await client.query(
            "UPDATE applications SET status=$1, remarks=$2, updated_at=now() WHERE id=$3",
            [status, remarks || null, req.params.id],
        );
        await client.query("COMMIT");
        await queue(Number(req.params.id), row.user_id, status);
        res.json({ ok: true });
        } catch (e) {
        await client.query("ROLLBACK");
        throw e;
        } finally {
        client.release();
        }
    }),
);

// Admin: list all applications. Optional filters: ?status= and ?scholarship_id=
app.get('/applications', auth('admin'), wrap(async (req, res) => {
    const where = [];
    const params = [];
    if (req.query.status) {
        params.push(req.query.status);
        where.push(`a.status = $${params.length}`);
    }
    if (req.query.scholarship_id) {
        const sid = Number(req.query.scholarship_id);
        if (!Number.isInteger(sid)) return res.status(400).json({ detail: 'Invalid scholarship_id' });
        params.push(sid);
        where.push(`a.scholarship_id = $${params.length}`);
    }
    const r = await pool.query(
        `SELECT a.id, ${refOf("a")} AS reference_no, a.status, a.remarks, a.gwa,
                    a.family_income, a.year_level, a.created_at,
                    u.full_name, u.student_number, s.title, a.user_id, a.scholarship_id,
                    s.is_open AS scholarship_open
            FROM applications a
            JOIN users u ON u.id = a.user_id
            JOIN scholarships s ON s.id = a.scholarship_id
            ${where.length ? "WHERE " + where.join(" AND ") : ""}
            ORDER BY a.created_at DESC`,
        params,
    );
    res.json(r.rows);
}));

// Applicant: my notification history
app.get('/notifications/mine', auth(), wrap(async (req, res) => {
    const r = await pool.query(
        `SELECT id, application_id, message, created_at
        FROM notifications WHERE user_id=$1 ORDER BY created_at DESC`, [req.user.id]);
    res.json(r.rows);
}));

// Admin: dashboard summary
app.get('/reports/summary', auth('admin'), wrap(async (req, res) => {
    const byStatus = await pool.query(
        'SELECT status, COUNT(*)::int AS count FROM applications GROUP BY status');
    const byScholarship = await pool.query(
        `SELECT s.id, s.title, s.slots_total, s.slots_remaining, COUNT(a.id)::int AS applications
        FROM scholarships s LEFT JOIN applications a ON a.scholarship_id = s.id
        GROUP BY s.id ORDER BY s.id`);
    const today = await pool.query(
        'SELECT COUNT(*)::int AS count FROM applications WHERE created_at::date = CURRENT_DATE');
    res.json({ by_status: byStatus.rows, by_scholarship: byScholarship.rows, today: today.rows[0].count });
}));

app.use((err, req, res, next) => {
    console.error(err);
    res.status(500).json({ detail: "Server error" });
});

app.listen(3000, () => console.log("application-api on 3000"));
