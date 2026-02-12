import time
from typing import List

from sqlalchemy import desc, func, select
from src.core.data.db import get_session
from src.core.data.models import SearchQuery


def _now() -> float:
    return time.time()


def add_search_query(query: str) -> None:
    with get_session() as session:
        session.add(SearchQuery(query=query.strip(), created_at=_now()))


def get_last_search_queries(limit: int = 200) -> List[str]:
    """Return unique recent query strings (newest first)."""
    with get_session() as session:
        last_ts = func.max(SearchQuery.created_at).label("last_ts")
        last_id = func.max(SearchQuery.id).label("last_id")
        rows = session.execute(
            select(SearchQuery.query, last_ts, last_id)
            .group_by(SearchQuery.query)
            .order_by(desc(last_ts), desc(last_id))
            .limit(limit)
        ).all()
        return [row[0] for row in rows] if rows else []
