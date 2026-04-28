from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

import config

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _migrate_companies():
    """Add config column and migrate Workday-specific columns into it."""
    from sqlalchemy import text
    with engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(companies)"))}
        if "config" not in cols:
            conn.execute(text("ALTER TABLE companies ADD COLUMN config TEXT DEFAULT '{}'"))
            # Copy existing Workday columns into the new JSON config field
            if "listing_endpoint" in cols:
                conn.execute(text("""
                    UPDATE companies SET config = json_object(
                        'listing_endpoint', COALESCE(listing_endpoint, ''),
                        'jd_base',          COALESCE(jd_base, ''),
                        'base_careers_url', COALESCE(base_careers_url, ''),
                        'payload',          COALESCE(payload, '{}')
                    )
                """))


def init_db():
    from db import models  # noqa: F401 — registers all models against Base
    Base.metadata.create_all(engine)
    _migrate_companies()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
