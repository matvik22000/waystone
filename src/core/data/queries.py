import time
from typing import List

from sqlalchemy import select
from src.core.data.db import get_session
from src.core.data.models import SearchQuery


def _now() -> float:
    return time.time()


def add_search_query(query: str) -> None:
    with get_session() as session:
        session.add(SearchQuery(query=query.strip(), created_at=_now()))


def get_last_search_queries(limit: int = 200) -> List[str]:
    """Return recent query strings (newest first). Caller may dedupe and slice to 10."""
    with get_session() as session:
        rows = (
            session.execute(
                select(SearchQuery.query).order_by(SearchQuery.created_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(rows) if rows else []
