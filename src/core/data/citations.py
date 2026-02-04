import time
from typing import List

from sqlalchemy import select

from src.core.crawler.rns_request import address_from_url
from src.core.data.db import get_session
from src.core.data.models import Citation


def _now() -> float:
    return time.time()


class Citations:
    def update_citations(self, src: str, links_to: List[str]) -> None:
        if len(links_to) == 0:
            return
        addresses_to = set(map(address_from_url, links_to))
        src_address = address_from_url(src)
        now_ = _now()

        with get_session() as session:
            for target_address in addresses_to:
                if target_address == src_address:
                    continue
                if len(target_address) != 32:
                    continue
                existing = session.execute(
                    select(Citation).where(
                        Citation.target_address == target_address,
                        Citation.src_address == src_address,
                    )
                ).scalars().first()
                if existing is None:
                    session.add(
                        Citation(
                            target_address=target_address,
                            src_address=src_address,
                            created_at=now_,
                        )
                    )

    def get_citations_for(self, address: str) -> set[str]:
        with get_session() as session:
            rows = session.execute(
                select(Citation.src_address).where(Citation.target_address == address)
            ).scalars().all()
            return set(rows) if rows else set()

    def get_amount_for(self, address: str) -> int:
        return len(self.get_citations_for(address))


citations = Citations()
