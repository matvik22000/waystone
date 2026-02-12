import os
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config import CONFIG
from src.core.data.models import Base

_db_path = os.path.join(CONFIG.STORAGE_PATH, "nomadapi.db")
_engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def init_db() -> None:
    os.makedirs(os.path.dirname(_db_path) or ".", exist_ok=True)
    Base.metadata.create_all(bind=_engine)
    _migrate_crawl_visited_urls_schema()


def _migrate_crawl_visited_urls_schema() -> None:
    """
    Lightweight schema compatibility migration for crawl_visited_urls.
    Adds last_visited_at for existing databases created before this field existed.
    """
    with _engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(crawl_visited_urls)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "last_visited_at" not in columns:
            conn.execute(text("ALTER TABLE crawl_visited_urls ADD COLUMN last_visited_at FLOAT"))
            if "created_at" in columns:
                conn.execute(
                    text(
                        "UPDATE crawl_visited_urls "
                        "SET last_visited_at = created_at "
                        "WHERE last_visited_at IS NULL"
                    )
                )


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
