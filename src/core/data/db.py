import os
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
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
