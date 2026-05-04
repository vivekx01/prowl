from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

import config

_is_sqlite = config.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=not _is_sqlite,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _migrate_postgres():
    """Add columns that create_all() won't add to existing Postgres tables."""
    with engine.begin() as conn:
        def has_col(table, col):
            return conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=:t AND column_name=:c"
            ), {"t": table, "c": col}).first() is not None

        if not has_col("score_runs", "company_ids"):
            conn.execute(text("ALTER TABLE score_runs ADD COLUMN company_ids JSONB"))


def _migrate():
    if not _is_sqlite:
        _migrate_postgres()
        return
    with engine.begin() as conn:
        def cols(table):
            return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}

        # ── job_listings: add description ────────────────────────────────────
        if "description" not in cols("job_listings"):
            conn.execute(text("ALTER TABLE job_listings ADD COLUMN description TEXT"))

        # ── profile: add user_id ─────────────────────────────────────────────
        if "user_id" not in cols("profile"):
            conn.execute(text("ALTER TABLE profile ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        # ── companies: add config (workday legacy migration) ──────────────────
        if "config" not in cols("companies"):
            conn.execute(text("ALTER TABLE companies ADD COLUMN config TEXT DEFAULT '{}'"))
            if "listing_endpoint" in cols("companies"):
                conn.execute(text("""
                    UPDATE companies SET config = json_object(
                        'listing_endpoint', COALESCE(listing_endpoint, ''),
                        'jd_base',          COALESCE(jd_base, ''),
                        'base_careers_url', COALESCE(base_careers_url, ''),
                        'payload',          COALESCE(payload, '{}')
                    )
                """))

        # ── job_scores: add user_id, new composite unique ────────────────────
        if "user_id" not in cols("job_scores"):
            conn.execute(text("""
                CREATE TABLE job_scores_new (
                    id INTEGER PRIMARY KEY,
                    listing_id INTEGER NOT NULL REFERENCES job_listings(id),
                    user_id INTEGER REFERENCES users(id),
                    score REAL DEFAULT 0.0,
                    verdict VARCHAR DEFAULT 'skip',
                    reason TEXT DEFAULT '',
                    processed_at DATETIME,
                    UNIQUE(user_id, listing_id)
                )
            """))
            conn.execute(text("""
                INSERT INTO job_scores_new(id, listing_id, user_id, score, verdict, reason, processed_at)
                SELECT id, listing_id, NULL, score, verdict, reason, processed_at FROM job_scores
            """))
            conn.execute(text("DROP TABLE job_scores"))
            conn.execute(text("ALTER TABLE job_scores_new RENAME TO job_scores"))

        # ── applications: add user_id, new composite unique ──────────────────
        if "user_id" not in cols("applications"):
            conn.execute(text("""
                CREATE TABLE applications_new (
                    id INTEGER PRIMARY KEY,
                    listing_id INTEGER NOT NULL REFERENCES job_listings(id),
                    user_id INTEGER REFERENCES users(id),
                    status VARCHAR DEFAULT 'saved',
                    applied_at DATETIME,
                    notes TEXT DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME,
                    UNIQUE(user_id, listing_id)
                )
            """))
            conn.execute(text("""
                INSERT INTO applications_new(id, listing_id, user_id, status, applied_at, notes, created_at, updated_at)
                SELECT id, listing_id, NULL, status, applied_at, notes, created_at, updated_at FROM applications
            """))
            conn.execute(text("DROP TABLE applications"))
            conn.execute(text("ALTER TABLE applications_new RENAME TO applications"))

        # ── users: add is_active ─────────────────────────────────────────────
        if "is_active" not in cols("users"):
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))

        # ── score_runs: add days_back ─────────────────────────────────────────
        if "days_back" not in cols("score_runs"):
            conn.execute(text("ALTER TABLE score_runs ADD COLUMN days_back INTEGER"))

        # ── score_runs: add per-stage token counts + cost ─────────────────────
        sr_cols = cols("score_runs")
        for col_def in [
            ("filter_input_tokens",  "INTEGER DEFAULT 0"),
            ("filter_output_tokens", "INTEGER DEFAULT 0"),
            ("score_input_tokens",   "INTEGER DEFAULT 0"),
            ("score_output_tokens",  "INTEGER DEFAULT 0"),
            ("cached_tokens",        "INTEGER DEFAULT 0"),
            ("cost_usd",             "REAL DEFAULT 0.0"),
        ]:
            if col_def[0] not in sr_cols:
                conn.execute(text(f"ALTER TABLE score_runs ADD COLUMN {col_def[0]} {col_def[1]}"))

        # ── profile: assign orphaned rows to the first admin user ────────────
        conn.execute(text("""
            UPDATE profile SET user_id = (
                SELECT id FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1
            )
            WHERE user_id IS NULL
            AND EXISTS (SELECT 1 FROM users WHERE is_admin = 1)
        """))

        # ── score_runs: add company_ids ───────────────────────────────────────
        if "company_ids" not in cols("score_runs"):
            conn.execute(text("ALTER TABLE score_runs ADD COLUMN company_ids JSON"))

        # ── score_run_logs: create if missing ─────────────────────────────────
        existing_tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "score_run_logs" not in existing_tables:
            conn.execute(text("""
                CREATE TABLE score_run_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES score_runs(id),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level VARCHAR DEFAULT 'info',
                    message TEXT NOT NULL
                )
            """))

        # ── companies: drop legacy columns (listing_endpoint etc.) ────────────
        if "listing_endpoint" in cols("companies"):
            conn.execute(text("""
                CREATE TABLE companies_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    platform VARCHAR NOT NULL DEFAULT 'workday',
                    active BOOLEAN DEFAULT 1,
                    config TEXT DEFAULT '{}',
                    created_at DATETIME
                )
            """))
            conn.execute(text("""
                INSERT INTO companies_new (id, name, platform, active, config, created_at)
                SELECT id, name, platform, active, config, created_at FROM companies
            """))
            conn.execute(text("DROP TABLE companies"))
            conn.execute(text("ALTER TABLE companies_new RENAME TO companies"))

        # ── settings: add id PK + user_id (table recreation) ─────────────────
        s_cols = cols("settings")
        if "user_id" not in s_cols:
            conn.execute(text("""
                CREATE TABLE settings_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    key VARCHAR NOT NULL,
                    value VARCHAR NOT NULL,
                    UNIQUE(user_id, key)
                )
            """))
            conn.execute(text("""
                INSERT INTO settings_new(user_id, key, value)
                SELECT NULL, key, value FROM settings
            """))
            conn.execute(text("DROP TABLE settings"))
            conn.execute(text("ALTER TABLE settings_new RENAME TO settings"))


def init_db():
    from db import models  # noqa: F401
    Base.metadata.create_all(engine)
    _migrate()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
