CREATE TABLE students (
    student_number VARCHAR(20) PRIMARY KEY,
    full_name      VARCHAR(120) NOT NULL
);


CREATE TABLE users (
    id             SERIAL PRIMARY KEY,
    student_number VARCHAR(20) UNIQUE REFERENCES students(student_number),
    email          VARCHAR(120) UNIQUE NOT NULL,
    full_name      VARCHAR(120) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(10) NOT NULL DEFAULT 'applicant'
                    CHECK (role IN ('applicant','admin'))
);


CREATE TABLE scholarships (
    id                 SERIAL PRIMARY KEY,
    title              VARCHAR(120) NOT NULL,
    description        TEXT,
    max_gwa            NUMERIC(3,2) NOT NULL,       -- 1.00 is best; lower is better
    max_income         NUMERIC(12,2) NOT NULL,
    year_levels        INT[] NOT NULL,
    slots_total        INT NOT NULL,
    slots_remaining    INT NOT NULL,
    deadline           DATE NOT NULL,
    is_open            BOOLEAN NOT NULL DEFAULT TRUE,
    required_documents TEXT[] NOT NULL
);


CREATE TABLE applications (
    id            SERIAL PRIMARY KEY,
    user_id       INT NOT NULL REFERENCES users(id),
    scholarship_id INT NOT NULL REFERENCES scholarships(id),
    course        VARCHAR(80),
    gwa           NUMERIC(3,2) NOT NULL,
    family_income NUMERIC(12,2) NOT NULL,
    year_level    INT NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'submitted'
                    CHECK (status IN ('submitted','under_review','approved','rejected','waitlisted')),
    remarks       TEXT,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, scholarship_id)               -- duplicate prevention
);


CREATE TABLE documents (
    id             SERIAL PRIMARY KEY,
    user_id        INT NOT NULL REFERENCES users(id),
    scholarship_id INT NOT NULL REFERENCES scholarships(id),
    doc_type       VARCHAR(40) NOT NULL,
    stored_name    VARCHAR(80) NOT NULL,
    original_name  VARCHAR(255),
    verified       BOOLEAN NOT NULL DEFAULT FALSE,
    flagged        BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, scholarship_id, doc_type)
);

CREATE TABLE notifications (
    id             SERIAL PRIMARY KEY,
    user_id        INT NOT NULL,
    application_id INT NOT NULL,
    message        TEXT NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT now()
);