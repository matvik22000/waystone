from typing import List

from src.api.store import JsonFileStore
from src.core.crawler.rns_request import address_from_url
from src.core.data import get_path


class Citations:
    def __init__(self):
        self.citations = JsonFileStore(get_path("citations.json"))

    def update_citations(self, src: str, links_to: List[str]) -> None:
        if len(links_to) == 0:
            return
        # select distinct addresses from urls list
        addresses_to = set(map(address_from_url, links_to))
        # graph of citations, may be used later for visualization
        # citations dict used for search
        for_search = self.citations.get("for_search", {})

        src_address = address_from_url(src)

        for target_address in addresses_to:
            # don't index self citations
            if target_address == src_address:
                continue
            # skip corrupted addresses
            if len(target_address) != 32:
                continue
            current_citations = set(for_search.get(target_address, []))
            current_citations.add(src_address)
            for_search[target_address] = list(current_citations)

        self.citations["for_search"] = for_search

    def get_citations_for(self, address: str) -> set[str]:
        return self.citations.get("for_search", {}).get(address, set())

    def get_amount_for(self, address: str) -> int:
        return len(self.get_citations_for(address))


citations = Citations()
