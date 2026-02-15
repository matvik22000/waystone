import time
from typing import List

from sqlalchemy import desc, func, select

from src.core.data.db import get_session
from src.core.data.models import UserSearchHistory as UserSearchHistoryRow


class UserSearchHistory:
    def add(self, remote_identity: str, query: str, ts: float | None = None) -> None:
        q = (query or "").strip()
        if not remote_identity or not q:
            return
        now_ = time.time()
        with get_session() as session:
            session.add(
                UserSearchHistoryRow(
                    remote_identity=remote_identity,
                    query=q,
                    time=float(ts if ts is not None else now_),
                    created_at=now_,
                )
            )

    def list(
        self, remote_identity: str, page: int = 0, page_size: int = 20
    ) -> List[dict]:
        if not remote_identity:
            return []
        page = max(0, int(page))
        page_size = max(1, min(int(page_size), 1000))
        with get_session() as session:
            rows = session.execute(
                select(UserSearchHistoryRow.query, UserSearchHistoryRow.time)
                .where(UserSearchHistoryRow.remote_identity == remote_identity)
                .order_by(desc(UserSearchHistoryRow.time), desc(UserSearchHistoryRow.id))
                .offset(page * page_size)
                .limit(page_size)
            ).all()
        return [{"q": q, "time": ts} for q, ts in rows]

    def count(self, remote_identity: str) -> int:
        if not remote_identity:
            return 0
        with get_session() as session:
            return int(
                session.execute(
                    select(func.count(UserSearchHistoryRow.id)).where(
                    UserSearchHistoryRow.remote_identity == remote_identity
                )
                ).scalar_one()
            )


user_search_history = UserSearchHistory()
