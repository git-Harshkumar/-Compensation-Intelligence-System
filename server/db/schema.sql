CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    discipline TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    rank INTEGER NOT NULL UNIQUE,
    scope TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    market_multiplier REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    stage TEXT NOT NULL,
    size_band TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compensation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_family_id INTEGER NOT NULL REFERENCES role_families(id),
    level_id INTEGER NOT NULL REFERENCES levels(id),
    location_id INTEGER NOT NULL REFERENCES locations(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    base_salary INTEGER NOT NULL,
    bonus INTEGER NOT NULL,
    equity_annual_value INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    effective_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role_family_id INTEGER NOT NULL REFERENCES role_families(id),
    level_id INTEGER NOT NULL REFERENCES levels(id),
    location_id INTEGER NOT NULL REFERENCES locations(id),
    company_name TEXT NOT NULL,
    base_salary INTEGER NOT NULL,
    bonus INTEGER NOT NULL,
    equity_annual_value INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_compare
ON compensation_records(role_family_id, level_id, location_id);

CREATE INDEX IF NOT EXISTS idx_submissions_user
ON submissions(user_id, created_at);

