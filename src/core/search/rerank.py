import logging
import time
from typing import List, Sequence

from sqlalchemy import select

from src.core.data.db import get_session
from src.core.data.models import Node
import numpy as np

from src.core.search.models import SearchResult
from src.core.search.nodes_downtime import PRIOR_ANNOUNCE, dead_probability_ci

DEAD_CONFIDENCE = 0.9

_LOGGER = logging.getLogger(__name__)


class Ranker:
    TEXT_WEIGHT = 0.65
    RANK_WEIGHT = 0.25
    ALIVE_WEIGHT = 0.1

    def rerank(self, results: List[SearchResult]) -> List[SearchResult]:
        results = self._filter_duplicates(results)
        results = self._filter_same_address(results)
        results = self._rerank_impl(results)

        return results

    def _rerank_impl(self, results: List[SearchResult]) -> List[SearchResult]:
        """Ранжирует результаты с учетом метрик узла (сейчас: rank)."""
        if not results:
            return []

        features = self._get_node_features([r.address for r in results])
        ranks, p_dead_low, p_dead_high, last_seen_ts = map(np.array, zip(*features))
        text_scores = np.array([r.score for r in results], dtype=float)

        text_scores_norm = self._minmax(text_scores)
        ranks_norm = self._minmax(np.log1p(ranks))
        node_alive = 1.0 - ((p_dead_low + p_dead_high) / 2.0)
        node_alive = np.clip(node_alive, 0.0, 1.0)

        _LOGGER.debug("===RAW SCORES===")
        _LOGGER.debug("text:\n%s", text_scores)
        _LOGGER.debug("ranks:\n%s", ranks)
        _LOGGER.debug("===NORM SCORES===")
        _LOGGER.debug("text norm:\n%s", text_scores_norm)
        _LOGGER.debug("ranks norm:\n%s", ranks_norm)
        _LOGGER.debug("node_alive:\n%s", node_alive)

        scored_rows = []
        for i, result in enumerate(results):
            new_score = (
                self.TEXT_WEIGHT * text_scores_norm[i]
                + self.RANK_WEIGHT * ranks_norm[i]
                + self.ALIVE_WEIGHT * node_alive[i]
            )

            # Создаем новый результат с обновленным скором
            ranked_result = SearchResult(
                url=result.url,
                text=result.text,
                owner=result.owner,
                address=result.address,
                name=result.name,
                score=new_score,
                p_dead_low=float(p_dead_low[i]),
                p_dead_high=float(p_dead_high[i]),
                time=float(last_seen_ts[i]),
            )
            scored_rows.append((ranked_result, float(p_dead_low[i])))

        scored_rows.sort(key=lambda x: (x[1] > DEAD_CONFIDENCE, -x[0].score))
        ranked_results = [row[0] for row in scored_rows]

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
    def _get_node_features(addresses: Sequence[str]) -> List[tuple[float, float, float, float]]:
        """

        :param addresses:
        :return: List[pagerank]
        """
        unique_addresses = set(dict.fromkeys(addresses))
        now_ts = time.time()
        with get_session() as session:
            rows = session.execute(
                select(
                    Node.dst,
                    Node.rank,
                    Node.time,
                    Node.announce_alpha,
                    Node.announce_beta,
                ).where(
                    Node.dst.in_(unique_addresses),
                    Node.removed.is_(False),
                )
            ).all()
            res = {
                dst: (
                    float(rank),
                    *dead_probability_ci(
                        float(announce_alpha) if announce_alpha is not None else float(PRIOR_ANNOUNCE[0]),
                        float(announce_beta) if announce_beta is not None else float(PRIOR_ANNOUNCE[1]),
                        max(0.0, float(now_ts) - float(last_seen_ts)),
                    ),
                    float(last_seen_ts),
                )
                for dst, rank, last_seen_ts, announce_alpha, announce_beta in rows
            }

        return [res.get(addr, (0.0, 0.0, 0.0, 0.0)) for addr in addresses]

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
