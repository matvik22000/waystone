import time
import typing as tp

from sqlalchemy import select

from src.core.data.db import get_session
from src.core.data.models import Node, Peer


def _now() -> float:
    return time.time()


def get_nodes() -> dict:
    """Return nodes as dict[destination, {dst, identity, name, time}] for backward compatibility."""
    with get_session() as session:
        rows = session.execute(select(Node)).scalars().all()
        return {
            row.destination: {
                "dst": row.dst,
                "identity": row.identity,
                "name": row.name,
                "time": row.time,
            }
            for row in rows
        }


def get_peers() -> dict:
    """Return peers as dict[destination, {dst, identity, name, time}] for backward compatibility."""
    with get_session() as session:
        rows = session.execute(select(Peer)).scalars().all()
        return {
            row.destination: {
                "dst": row.dst,
                "identity": row.identity,
                "name": row.name,
                "time": row.time,
            }
            for row in rows
        }


def upsert_node(destination: str, dst: str, identity: str, name: str, ts: float) -> None:
    with get_session() as session:
        row = session.execute(select(Node).where(Node.destination == destination)).scalars().first()
        now_ = _now()
        if row:
            row.dst = dst
            row.identity = identity
            row.name = name
            row.time = ts
            row.updated_at = now_
        else:
            session.add(
                Node(
                    destination=destination,
                    dst=dst,
                    identity=identity,
                    name=name,
                    time=ts,
                    created_at=now_,
                    updated_at=now_,
                )
            )


def upsert_peer(destination: str, dst: str, identity: str, name: str, ts: float) -> None:
    with get_session() as session:
        row = session.execute(select(Peer).where(Peer.destination == destination)).scalars().first()
        now_ = _now()
        if row:
            row.dst = dst
            row.identity = identity
            row.name = name
            row.time = ts
            row.updated_at = now_
        else:
            session.add(
                Peer(
                    destination=destination,
                    dst=dst,
                    identity=identity,
                    name=name,
                    time=ts,
                    created_at=now_,
                    updated_at=now_,
                )
            )


def find_owner(identity: str) -> tp.Optional[tp.Tuple[str, str]]:
    with get_session() as session:
        row = session.execute(select(Peer).where(Peer.identity == identity)).scalars().first()
        if row is None:
            return None
        return row.name, row.dst


def find_node_by_address(address: str) -> tp.Optional[dict]:
    with get_session() as session:
        row = session.execute(select(Node).where(Node.dst == address)).scalars().first()
        if row is None:
            return None
        return {
            "dst": row.dst,
            "identity": row.identity,
            "name": row.name,
            "time": row.time,
        }


# Backward compatibility: store.get("nodes", {}) and store.get("peers", {})
class _StoreCompat:
    def get(self, key: str, default=None):
        if key == "nodes":
            return get_nodes()
        if key == "peers":
            return get_peers()
        return default


store = _StoreCompat()
