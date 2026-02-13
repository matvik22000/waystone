import logging
import math
import os
from dataclasses import dataclass, asdict
from threading import Lock
from typing import Dict, List, Optional, Sequence

from whoosh.analysis import StemmingAnalyzer, NgramWordAnalyzer
from whoosh.fields import *
from whoosh.filedb.filestore import FileStorage
from whoosh.highlight import Formatter, get_text
from whoosh.qparser import MultifieldParser, OrGroup

from . import get_path
from .citations import Citations, citations


@dataclass
class SearchDocument:
    """Документ для индексации в поисковой системе"""

    url: str
    text: str
    owner: str
    address: str
    nodeName: str | None

    def to_dict(self) -> Dict:
        """Конвертирует документ в словарь для индексации"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SearchDocument":
        """Создает документ из словаря"""
        return cls(**data)


@dataclass
class SearchResult:
    """Результат поиска с подсветкой и релевантностью"""

    url: str
    text: str
    owner: str
    address: str
    name: str
    score: float

    # highlighted_text: Optional[str] = None
    # highlighted_node_name: Optional[str] = None

    def to_dict(self) -> Dict:
        """Конвертирует результат в словарь"""
        result = asdict(self)
        # Убираем None значения для чистоты
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class SearchWeights:
    """Веса для ранжирования результатов поиска"""

    text_search: float = 1
    citations: float = 1.5


class MuBoldFormatter(Formatter):
    """Форматтер для подсветки результатов поиска"""

    def format_token(self, text, token, replace=False):
        tokentext = get_text(text, token, replace)
        return "`!`_%s`_`!" % tokentext


class SearchEngine:
    """Поисковая система с поддержкой индексации и поиска документов"""


    def __init__(self, schema: Schema, citations: Citations):
        self.__lock = Lock()
        self.schema = schema
        self.citations = citations
        self.weights = SearchWeights()
        self._index_queue: list[SearchDocument] = []
        self._index_batch_size = 10
        self._optimize_every_batches = 25
        self._batches_since_optimize = 0

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
        self, q: str, highlight: bool = True, max_results: Optional[int] = 20
    ) -> List[SearchResult]:
        """Выполняет поиск по запросу"""
        fields = ["url", "text", "nodeName", "owner", "address"]
        search_results = []

        with self.ix.searcher() as searcher:
            search_limit = None if max_results is None else max(max_results * 2, max_results)
            results = searcher.search(
                MultifieldParser(
                    fields, schema=self.schema, group=OrGroup.factory(1.5)
                ).parse(q),
                limit=search_limit,
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

                # Добавляем подсветку если нужно
                if highlight:
                    if r.get("text") and isinstance(r.get("text"), str):
                        result.text = r.highlights("text") or r["text"][:200]
                    # if r.get("nodeName") and isinstance(r.get("nodeName"), str):
                    #     result.highlighted_node_name = r.highlights("nodeName") or r["nodeName"][:200]

                search_results.append(result)

        search_results = self._filter_duplicates(search_results)
        search_results = self._filter_same_address(search_results)
        ranked = self._rank_results(search_results)
        if max_results is None:
            return ranked
        return ranked[:max_results]

    def _rank_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Ранжирует результаты с учетом цитирований"""
        ranked_results = []
        self.logger.debug("unranked results: %s", results)
        for result in results:
            # Вычисляем новый скор с учетом цитирований
            citation_score = self.citations.get_amount_for(result.address)
            new_score = (
                self.weights.text_search * result.score
                + self.weights.citations
                * (math.log(citation_score) if citation_score > 0 else 0)
            )

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
        self.logger.debug("ranked results: %s", ranked_results)
        return ranked_results

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

    def save(self, path: str):
        """Сохраняет индекс в указанную директорию"""
        self.flush_index_queue(force_optimize=False)
        if not os.path.exists(path):
            os.makedirs(path)
        self.ix.storage.close()
        self.ix.writer().commit(optimize=True)
        self.ix.storage.copyto(path)


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
engine = SearchEngine(schema, citations)
