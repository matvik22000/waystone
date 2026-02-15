import os
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
    _migrate_nodes_schema_drop_destination()
    _migrate_nodes_add_removed()
    _migrate_peers_schema_drop_destination()
    _migrate_citations_add_removed()


def _migrate_nodes_schema_drop_destination() -> None:
    with _engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(nodes)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "destination" not in columns:
            return
        has_rank = "rank" in columns

        conn.execute(
            text(
                "CREATE TABLE nodes_new ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "dst VARCHAR(64) NOT NULL UNIQUE, "
                "identity VARCHAR(64) NOT NULL, "
                "name TEXT NOT NULL, "
                "time FLOAT NOT NULL, "
                "created_at FLOAT NOT NULL, "
                "updated_at FLOAT NOT NULL, "
                "rank FLOAT NOT NULL, "
                "removed BOOLEAN NOT NULL DEFAULT 0)"
            )
        )
        if has_rank:
            conn.execute(
                text(
                    "INSERT INTO nodes_new (id, dst, identity, name, time, created_at, updated_at, rank, removed) "
                    "SELECT n.id, n.dst, n.identity, n.name, n.time, n.created_at, n.updated_at, n.rank, 0 "
                    "FROM nodes n "
                    "WHERE n.id = ("
                    "  SELECT n2.id FROM nodes n2 "
                    "  WHERE n2.dst = n.dst "
                    "  ORDER BY n2.updated_at DESC, n2.id DESC LIMIT 1"
                    ")"
                )
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO nodes_new (id, dst, identity, name, time, created_at, updated_at, rank, removed) "
                    "SELECT n.id, n.dst, n.identity, n.name, n.time, n.created_at, n.updated_at, 0.0, 0 "
                    "FROM nodes n "
                    "WHERE n.id = ("
                    "  SELECT n2.id FROM nodes n2 "
                    "  WHERE n2.dst = n.dst "
                    "  ORDER BY n2.updated_at DESC, n2.id DESC LIMIT 1"
                    ")"
                )
            )
        conn.execute(text("DROP TABLE nodes"))
        conn.execute(text("ALTER TABLE nodes_new RENAME TO nodes"))
        conn.execute(text("CREATE INDEX idx_nodes_identity ON nodes(identity)"))
        conn.execute(text("CREATE INDEX idx_nodes_time ON nodes(time)"))


def _migrate_nodes_add_removed() -> None:
    with _engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(nodes)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "removed" in columns:
            return
        conn.execute(
            text("ALTER TABLE nodes ADD COLUMN removed BOOLEAN NOT NULL DEFAULT 0")
        )


def _migrate_peers_schema_drop_destination() -> None:
    with _engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(peers)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "destination" not in columns:
            return

        conn.execute(
            text(
                "CREATE TABLE peers_new ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "dst VARCHAR(64) NOT NULL UNIQUE, "
                "identity VARCHAR(64) NOT NULL, "
                "name TEXT NOT NULL, "
                "time FLOAT NOT NULL, "
                "created_at FLOAT NOT NULL, "
                "updated_at FLOAT NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO peers_new (id, dst, identity, name, time, created_at, updated_at) "
                "SELECT p.id, p.dst, p.identity, p.name, p.time, p.created_at, p.updated_at "
                "FROM peers p "
                "WHERE p.id = ("
                "  SELECT p2.id FROM peers p2 "
                "  WHERE p2.dst = p.dst "
                "  ORDER BY p2.updated_at DESC, p2.id DESC LIMIT 1"
                ")"
            )
        )
        conn.execute(text("DROP TABLE peers"))
        conn.execute(text("ALTER TABLE peers_new RENAME TO peers"))
        conn.execute(text("CREATE INDEX idx_peers_identity ON peers(identity)"))
        conn.execute(text("CREATE INDEX idx_peers_time ON peers(time)"))


def _migrate_citations_add_removed() -> None:
    with _engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(citations)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "removed" in columns:
            return
        conn.execute(
            text("ALTER TABLE citations ADD COLUMN removed BOOLEAN NOT NULL DEFAULT 0")
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
