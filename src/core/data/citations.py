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
        src_address = address_from_url(src)
        addresses_to = set()
        for link in links_to:
            target_address = address_from_url(link)
            if target_address == src_address:
                continue
            if len(target_address) != 32:
                continue
            addresses_to.add(target_address)
        now_ = _now()

        with get_session() as session:
            existing_rows = session.execute(
                select(Citation).where(Citation.src_address == src_address)
            ).scalars().all()
            existing_by_target = {row.target_address: row for row in existing_rows}

            for target_address, row in existing_by_target.items():
                if target_address in addresses_to:
                    if row.removed:
                        row.removed = False
                else:
                    if not row.removed:
                        row.removed = True

            for target_address in addresses_to:
                if target_address in existing_by_target:
                    continue
                session.add(
                    Citation(
                        target_address=target_address,
                        src_address=src_address,
                        created_at=now_,
                        removed=False,
                    )
                )

    def get_citations_for(self, address: str) -> set[str]:
        with get_session() as session:
            rows = session.execute(
                select(Citation.src_address).where(
                    Citation.target_address == address,
                    Citation.removed.is_(False),
                )
            ).scalars().all()
            return set(rows) if rows else set()

    def get_amount_for(self, address: str) -> int:
        return len(self.get_citations_for(address))


citations = Citations()
