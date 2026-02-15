import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, asdict
from functools import lru_cache
from threading import Lock
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from whoosh.analysis import StemmingAnalyzer, NgramWordAnalyzer
from whoosh.fields import *
from whoosh.filedb.filestore import FileStorage
from whoosh.highlight import Formatter, get_text
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh import scoring

from core.data import get_path
from core.search.models import SearchDocument, SearchResult
from core.search.rerank import Ranker, ranker


class MuBoldFormatter(Formatter):
    """Форматтер для подсветки результатов поиска"""

    def format_token(self, text, token, replace=False):
        tokentext = get_text(text, token, replace)
        return "`!`_%s`_`!" % tokentext


class SearchEngine:
    """Поисковая система с поддержкой индексации и поиска документов"""

    def __init__(self, schema: Schema, ranker: Ranker):
        self.__lock = Lock()
        self.__cache_lock = Lock()
        self.schema = schema
        self.ranker = ranker
        self._index_queue: list[SearchDocument] = []
        self._index_batch_size = 10
        self._optimize_every_batches = 25
        self._batches_since_optimize = 0
        self._query_cache: "OrderedDict[str, tuple[float, list[SearchResult]]]" = OrderedDict()

        self._query_cache_ttl_seconds = 300
        self._query_cache_max_entries = 200

        self.schema.add("raw", STORED())
        storage_path = get_path("search_index")
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)
            self.ix = FileStorage(storage_path).create_index(self.schema)
        else:
            self.ix = FileStorage(storage_path).open_index()

        self.logger = logging.getLogger("search")

    def index_documents(self, docs: Sequence[SearchDocument]):
        """Индексирует документы в поисковой системе"""
        with self.__lock:
            self._commit_documents(docs, optimize=False)

    def queue_document(self, doc: SearchDocument):
        with self.__lock:
            self._index_queue.append(doc)
            if len(self._index_queue) >= self._index_batch_size:
                self._flush_index_queue_locked(force_optimize=False)

    def flush_index_queue(self, force_optimize: bool = False):
        with self.__lock:
            self._flush_index_queue_locked(force_optimize=force_optimize)

    def _flush_index_queue_locked(self, force_optimize: bool = False):
        if not self._index_queue:
            return
        docs = self._index_queue
        self._index_queue = []

        optimize_now = force_optimize or (
                self._batches_since_optimize + 1 >= self._optimize_every_batches
        )
        self._commit_documents(docs, optimize=optimize_now)

        if optimize_now:
            self._batches_since_optimize = 0
        else:
            self._batches_since_optimize += 1

    def _commit_documents(self, docs: Sequence[SearchDocument], optimize: bool):
        writer = self.ix.writer()
        for doc in docs:
            doc_dict = doc.to_dict()
            # Фильтруем только поля, которые есть в схеме
            filtered_dict = {
                k: v for k, v in doc_dict.items() if k in self.schema.stored_names()
            }
            filtered_dict["raw"] = doc.text
            writer.update_document(**filtered_dict)
        writer.commit(optimize=optimize)

    def get_index_size(self) -> int:
        """Возвращает количество документов в индексе"""
        return self.ix.doc_count_all()

    def query(
            self, q: str, highlight: bool = True
    ) -> List[SearchResult]:
        """Выполняет поиск по запросу"""
        cache_key = self._normalize_query_cache_key(q)
        cached = self._get_cached_results(cache_key)
        if cached is not None:
            return cached

        ranked = self._query_impl(highlight, q)

        self._set_cached_results(cache_key, ranked)
        return ranked

    def _query_impl(self, highlight, q):
        fields = ["url", "text", "nodeName", "owner", "address"]
        search_results: list[SearchResult] = []
        with self.ix.searcher(weighting=scoring.BM25F()) as searcher:
            # We intentionally fetch full candidate set here and cache the globally ranked
            # result list, so pagination can reuse it cheaply for a few minutes.
            results = searcher.search(
                MultifieldParser(
                    fields, schema=self.schema, group=OrGroup
                ).parse(q),
                limit=None,
            )
            results.formatter = MuBoldFormatter()
            results.fragmenter.maxchars = 100

            for r in results:
                # Создаем результат поиска
                result = SearchResult(
                    url=r["url"],
                    text=r["text"],
                    owner=r["owner"],
                    address=r["address"],
                    name=r.get("nodeName") or r["url"],
                    score=r.score,
                )

                if highlight:
                    if r.get("text") and isinstance(r.get("text"), str):
                        result.text = r.highlights("text") or r["text"][:200]

                search_results.append(result)

        self.logger.debug("unranked results: %s", search_results)
        ranked = self.ranker.rerank(search_results)
        self.logger.debug("reranked results: %s", ranked)
        return ranked

    def save(self, path: str):
        """Сохраняет индекс в указанную директорию"""
        self.flush_index_queue(force_optimize=False)
        if not os.path.exists(path):
            os.makedirs(path)
        self.ix.storage.close()
        self.ix.writer().commit(optimize=True)
        self.ix.storage.copyto(path)

    def _normalize_query_cache_key(self, q: str) -> str:
        return (q or "").strip()

    def _get_cached_results(self, key: str) -> Optional[List[SearchResult]]:
        if not key:
            return None
        now_ts = time.time()
        with self.__cache_lock:
            entry = self._query_cache.get(key)
            if not entry:
                return None
            expires_at, results = entry
            if expires_at <= now_ts:
                self._query_cache.pop(key)
                return None
            self._query_cache.move_to_end(key)
            return results.copy()

    def _set_cached_results(self, key: str, results: List[SearchResult]) -> None:
        if not key:
            return
        now_ts = time.time()
        with self.__cache_lock:
            self._query_cache[key] = (
                now_ts + self._query_cache_ttl_seconds,
                results.copy(),
            )
            self._query_cache.move_to_end(key)
            while len(self._query_cache) > self._query_cache_max_entries:
                self._query_cache.popitem(last=False)


# Схема для индексации
schema = Schema(
    url=ID(stored=True, unique=True),
    text=TEXT(stored=True, analyzer=StemmingAnalyzer()),
    owner=KEYWORD(stored=True),
    address=KEYWORD(stored=True),
    nodeName=TEXT(
        stored=True,
        analyzer=NgramWordAnalyzer(minsize=4, maxsize=15),
        phrase=False,
        field_boost=2.0,
    ),
)

# Глобальный экземпляр поисковой системы
engine = SearchEngine(schema, ranker)
