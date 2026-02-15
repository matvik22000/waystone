import time
import typing as tp

from sqlalchemy import desc, func, or_, select, update

from src.core.data.db import get_session
from src.core.data.models import Citation, Node, Peer


def _now() -> float:
    return time.time()


def _node_to_dict(row: Node) -> dict:
    return {
        "destination": f"<{row.dst}>",
        "dst": row.dst,
        "identity": row.identity,
        "name": row.name,
        "time": row.time,
    }


def _peer_to_dict(row: Peer) -> dict:
    return {
        "destination": f"<{row.dst}>",
        "dst": row.dst,
        "identity": row.identity,
        "name": row.name,
        "time": row.time,
    }


def get_nodes() -> dict:
    """Return nodes as dict[destination, {dst, identity, name, time}] for backward compatibility."""
    with get_session() as session:
        rows = session.execute(select(Node).where(Node.removed.is_(False))).scalars().all()
        return {
            f"<{row.dst}>": {
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
            f"<{row.dst}>": {
                "dst": row.dst,
                "identity": row.identity,
                "name": row.name,
                "time": row.time,
            }
            for row in rows
        }


def get_nodes_page(page: int = 0, page_size: int = 100, query: str = "") -> list[dict]:
    page = max(0, int(page))
    page_size = max(1, min(int(page_size), 1000))

    with get_session() as session:
        q = select(Node).where(Node.removed.is_(False)).order_by(desc(Node.rank), desc(Node.time))
        if query:
            like = f"%{query}%"
            q = q.where((Node.name.ilike(like)) | (Node.dst.ilike(like)))

        rows = (
            session.execute(q.offset(page * page_size).limit(page_size))
            .scalars()
            .all()
        )
        return [_node_to_dict(r) for r in rows]


def get_peers_page(page: int = 0, page_size: int = 100, query: str = "") -> list[dict]:
    page = max(0, int(page))
    page_size = max(1, min(int(page_size), 1000))

    with get_session() as session:
        q = select(Peer).order_by(desc(Peer.time))
        if query:
            like = f"%{query}%"
            q = q.where((Peer.name.ilike(like)) | (Peer.dst.ilike(like)))
        rows = (
            session.execute(q.offset(page * page_size).limit(page_size))
            .scalars()
            .all()
        )
        return [_peer_to_dict(r) for r in rows]


def get_nodes_for_addresses(addresses: tp.Iterable[str]) -> list[dict]:
    addresses = list(addresses)
    if not addresses:
        return []
    with get_session() as session:
        rows = session.execute(
            select(Node).where(Node.dst.in_(addresses), Node.removed.is_(False))
        ).scalars().all()
        return [_node_to_dict(r) for r in rows]


def get_recent_nodes_for_crawl(within_seconds: int = 86400) -> list[str]:
    min_ts = _now() - max(1, within_seconds)
    with get_session() as session:
        rows = session.execute(
            select(Node.dst)
            .where(Node.time >= min_ts, Node.removed.is_(False))
            .order_by(desc(Node.time))
        ).scalars().all()
        return list(rows)


def count_nodes() -> int:
    with get_session() as session:
        return int(
            session.execute(select(func.count(Node.id)).where(Node.removed.is_(False))).scalar_one()
        )


def count_peers() -> int:
    with get_session() as session:
        return int(session.execute(select(func.count(Peer.id))).scalar_one())


def count_nodes_filtered(query: str = "") -> int:
    with get_session() as session:
        q = select(func.count(Node.id)).where(Node.removed.is_(False))
        if query:
            like = f"%{query}%"
            q = q.where((Node.name.ilike(like)) | (Node.dst.ilike(like)))
        return int(session.execute(q).scalar_one())


def count_peers_filtered(query: str = "") -> int:
    with get_session() as session:
        q = select(func.count(Peer.id))
        if query:
            like = f"%{query}%"
            q = q.where((Peer.name.ilike(like)) | (Peer.dst.ilike(like)))
        return int(session.execute(q).scalar_one())


def upsert_node(dst: str, identity: str, name: str, ts: float) -> None:
    with get_session() as session:
        row = session.execute(select(Node).where(Node.dst == dst)).scalars().first()
        now_ = _now()
        if row:
            row.identity = identity
            row.name = name
            row.time = ts
            row.updated_at = now_
            row.removed = False
        else:
            session.add(
                Node(
                    dst=dst,
                    identity=identity,
                    name=name,
                    time=ts,
                    created_at=now_,
                    updated_at=now_,
                    rank=0.0,
                    removed=False,
                )
            )


def mark_stale_nodes_removed(
        older_than_days: int,
) -> list[str]:
    older_than_seconds = max(1, int(older_than_days * 24 * 60 * 60))
    threshold_ts = _now() - older_than_seconds
    with get_session() as session:
        rows = session.execute(
            select(Node).where(Node.removed.is_(False), Node.time < threshold_ts)
        ).scalars().all()
        removed_addresses = [row.dst for row in rows]
        for row in rows:
            row.removed = True
        if removed_addresses:
            session.execute(
                update(Citation)
                .where(
                    or_(
                        Citation.src_address.in_(removed_addresses),
                        Citation.target_address.in_(removed_addresses),
                    ),
                )
                .values(removed=True)
            )
    return removed_addresses


def upsert_peer(dst: str, identity: str, name: str, ts: float) -> None:
    with get_session() as session:
        row = session.execute(select(Peer).where(Peer.dst == dst)).scalars().first()
        now_ = _now()
        if row:
            row.identity = identity
            row.name = name
            row.time = ts
            row.updated_at = now_
        else:
            session.add(
                Peer(
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
        row = session.execute(
            select(Node).where(Node.dst == address, Node.removed.is_(False))
        ).scalars().first()
        if row is None:
            return None
        return _node_to_dict(row)

