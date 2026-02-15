import logging
from dataclasses import dataclass
from typing import List, Sequence, Dict, Tuple

from sqlalchemy import select
from sqlalchemy.sql.functions import count

from core.data.db import get_session
from core.data.models import Node
import numpy as np

from core.search.models import SearchResult

_LOGGER = logging.getLogger(__name__)


class Ranker:
    TEXT_WEIGHT = 0.7
    RANK_WEIGHT = 0.3

    def rerank(self, results: List[SearchResult]) -> List[SearchResult]:
        results = self._filter_duplicates(results)
        results = self._filter_same_address(results)
        results = self._rerank_impl(results)

        return results

    def _rerank_impl(self, results: List[SearchResult]) -> List[SearchResult]:
        """Ранжирует результаты с учетом метрик узла (сейчас: rank)."""
        if not results:
            return []
        ranked_results = []
        (ranks,) = map(np.array, zip(*self._get_node_features([r.address for r in results])))
        text_scores = np.array([r.score for r in results], dtype=float)

        text_scores_norm = self._minmax(text_scores)
        ranks_norm = self._minmax(np.log1p(ranks))

        _LOGGER.debug("===RAW SCORES===")
        _LOGGER.debug("text:\n%s", text_scores)
        _LOGGER.debug("ranks:\n%s", ranks)
        _LOGGER.debug("===NORM SCORES===")
        _LOGGER.debug("text norm:\n%s", text_scores_norm)
        _LOGGER.debug("ranks norm:\n%s", ranks_norm)

        for i, result in enumerate(results):
            new_score = self.TEXT_WEIGHT * text_scores_norm[i] + self.RANK_WEIGHT * ranks_norm[i]

            # Создаем новый результат с обновленным скором
            ranked_result = SearchResult(
                url=result.url,
                text=result.text,
                owner=result.owner,
                address=result.address,
                name=result.name,
                score=new_score,
            )
            ranked_results.append(ranked_result)

        ranked_results.sort(key=lambda x: x.score, reverse=True)

        return ranked_results

    def _minmax(self, x):
        min_score = np.min(x)
        max_score = np.max(x)
        den = max_score - min_score
        if den <= 0 or not np.isfinite(den):
            text_scores_norm = np.zeros_like(x)
        else:
            text_scores_norm = (x - min_score) / den
        return text_scores_norm

    @staticmethod
    def _get_node_features(addresses: Sequence[str]) -> List[Tuple[float]]:
        """

        :param addresses:
        :return: List[pagerank]
        """
        unique_addresses = set(dict.fromkeys(addresses))
        with get_session() as session:
            rows = session.execute(
                select(Node.dst, Node.rank).where(Node.dst.in_(unique_addresses))
            ).all()
            res = {dst: (float(rank),) for dst, rank in rows}

        return [res[addr] for addr in addresses]

    @staticmethod
    def _filter_duplicates(results: List[SearchResult]) -> List[SearchResult]:
        """
        drops duplicates identical urls, it's always a mistake to have more than one

        :param results:
        :return:
        """
        urls = set()
        filtered_results = []
        for result in results:
            if result.url in urls:
                continue
            urls.add(result.url)
            filtered_results.append(result)
        return filtered_results

    @staticmethod
    def _filter_same_address(
            results: List[SearchResult], max_same_address=2
    ) -> List[SearchResult]:
        """
        drop extra pages on one address (somtimes result of search is 10 pages on one node. I don't need all ot them)

        :param results:
        :return:
        """
        addresses = {}
        filtered_results = []

        for result in results:
            current_addresses_amount = addresses.get(result.address, 0)
            if current_addresses_amount < max_same_address:
                addresses[result.address] = current_addresses_amount + 1
                filtered_results.append(result)
        return filtered_results


ranker = Ranker()
