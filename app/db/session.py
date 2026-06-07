from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base


def _normalize_sqlite_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    path_part = url.replace("sqlite:///", "", 1)
    if path_part == ":memory:":
        return url
    p = Path(path_part)
    if not p.is_absolute():
        root = Path(__file__).resolve().parent.parent.parent
        p = (root / p).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{p}"


_DATABASE_URL = _normalize_sqlite_url(settings.database_url)

engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _sqlite_column_names(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {str(r[1]) for r in rows}


def _migrate_sqlite_schema() -> None:
    if not _DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        for table in ("github_projects", "arxiv_papers"):
            cols = _sqlite_column_names(conn, table)
            if "ai_rating" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN ai_rating FLOAT"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()


def get_session() -> Session:
    return SessionLocal()
