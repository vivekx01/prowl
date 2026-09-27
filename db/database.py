from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

import config

if not config.DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _migrate():
    """Add columns that create_all() won't add to existing tables."""
    with engine.begin() as conn:
        def has_col(table, col):
            return conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=:t AND column_name=:c"
            ), {"t": table, "c": col}).first() is not None

        if not has_col("score_runs", "company_ids"):
            conn.execute(text("ALTER TABLE score_runs ADD COLUMN company_ids JSONB"))

        if not has_col("job_listings", "last_seen_at"):
            conn.execute(text("ALTER TABLE job_listings ADD COLUMN last_seen_at TIMESTAMP"))
            conn.execute(text("UPDATE job_listings SET last_seen_at = first_seen_at WHERE last_seen_at IS NULL"))

        if has_col("api_keys", "user_id") and not has_col("api_keys", "label"):
            conn.execute(text("ALTER TABLE api_keys ADD COLUMN label VARCHAR DEFAULT ''"))
            conn.execute(text("ALTER TABLE api_keys DROP CONSTRAINT IF EXISTS uq_user_api_key"))

        for col, col_type in [
            ("filter_input_tokens",  "INTEGER DEFAULT 0"),
            ("filter_output_tokens", "INTEGER DEFAULT 0"),
            ("score_input_tokens",   "INTEGER DEFAULT 0"),
            ("score_output_tokens",  "INTEGER DEFAULT 0"),
            ("cached_tokens",        "INTEGER DEFAULT 0"),
            ("cost_usd",             "DOUBLE PRECISION DEFAULT 0.0"),
            ("days_back",            "INTEGER"),
        ]:
            if not has_col("score_runs", col):
                conn.execute(text(f"ALTER TABLE score_runs ADD COLUMN {col} {col_type}"))


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
