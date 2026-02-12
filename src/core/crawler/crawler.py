import datetime
import logging
import random
import threading
import time
import typing as tp
from contextlib import contextmanager
from queue import Empty, Queue
from threading import Thread
from time import sleep

from sqlalchemy import select

from src.core.data.db import get_session
from src.core.data.models import CrawlVisitedUrl

Document = tp.TypeVar("Document")
Loader = tp.Callable[[str], Document]
Extractor = tp.Callable[[Document], tp.List[str]]


class _DbVisitedSet:
    def __init__(self, cache_seconds: int):
        self.__lock = threading.Lock()
        self.__logger = logging.getLogger("crawler-visited")
        self._cache_seconds = max(1, int(cache_seconds))

    def add_if_missing(self, url: str) -> bool:
        with self.__lock:
            with get_session() as session:
                now_ts = time.time()
                existing = session.execute(
                    select(CrawlVisitedUrl).where(CrawlVisitedUrl.url == url)
                ).scalars().first()
                if existing is None:
                    session.add(
                        CrawlVisitedUrl(
                            url=url,
                            created_at=now_ts,
                            last_visited_at=now_ts,
                        )
                    )
                    return True

                last_ts = existing.last_visited_at or existing.created_at
                existing.last_visited_at = now_ts
                if now_ts - last_ts < self._cache_seconds:
                    return False
                return True


class _Downloader(Thread):
    downloading: bool = False
    _queue: Queue
    _alive: bool = True
    _crawler: "Crawler"

    _load: Loader
    _extract: Extractor

    def __init__(self, queue: Queue, name: str, crawler: "Crawler", load: Loader, extract: Extractor):
        super().__init__()
        self._queue = queue
        self._load = load
        self._extract = extract
        self._crawler = crawler
        self._logger = logging.getLogger(f"crawler-{name}")
        self.counter = 0

    def run(self) -> None:
        # sleep random time, to avoid simultaneous star
        sleep(random.random() * 3)
        try:
            while self._alive:
                try:
                    url = self._queue.get(timeout=1)
                    with self._loading():
                        self._process_url(url)
                    self._queue.task_done()
                    self.counter += 1
                except Empty:
                    pass
                except Exception as e:
                    self._logger.warning(
                        "Error in thread %s: %s", self.name, e, exc_info=True
                    )
        finally:
            self._logger.debug("Stopped %s", self.name)

    def _process_url(self, url: str):
        self._logger.debug("Loading %s", url)
        try:
            document = self._load(url)
        except Exception as e:
            self._logger.warning("Error during loading %s: %s", url, e)
            return
        self._logger.debug("Extracting %s", url)
        urls = self._extract(document)

        for next_url in urls:
            self._crawler.enqueue_url(next_url, source_url=url)

    def stop(self):
        self._alive = False

    @contextmanager
    def _loading(self):
        self.downloading = True
        yield
        self.downloading = False


class Crawler:
    _load: Loader
    _extract: Extractor

    _threads: tp.List[_Downloader]

    def __init__(
        self,
        load: Loader,
        page_processor: Extractor,
        queue_maxsize: int = 5000,
        visited_cache_seconds: int = 86400,
    ):
        self._load = load
        self._extract = page_processor
        self._logger = logging.getLogger("crawler")
        self._queue = Queue(maxsize=queue_maxsize)
        self._threads = []
        self.__started_at = datetime.datetime.now()
        self._visited = _DbVisitedSet(cache_seconds=visited_cache_seconds)
        self._enqueue_lock = threading.Lock()

    def start(self, threads=5):
        self._threads = []
        for i in range(threads):
            t = _Downloader(self._queue, str(i), self, self._load, self._extract)
            t.start()
            self._threads.append(t)
        self._logger.debug("started with %s downloader threads", threads)
        self.__started_at = datetime.datetime.now()

    def add_url(self, url: str):
        self.enqueue_url(url, source_url="seed")

    def enqueue_url(self, url: str, source_url: str = "") -> bool:
        with self._enqueue_lock:
            if self._queue.full():
                self._logger.warning(
                    "Queue is full (%s). Ignoring page %s discovered from %s",
                    self._queue.maxsize,
                    url,
                    source_url or "unknown",
                )
                return False
            if not self._visited.add_if_missing(url):
                return False
            self._queue.put_nowait(url)
            return True

    def finished(self):
        return all((not t.downloading for t in self._threads))

    def stop(self):
        self._logger.debug("Stopping all threads")
        for t in self._threads:
            t.stop()

    def total_crawled(self) -> int:
        total = 0
        for t in self._threads:
            total += t.counter
        return total

    def join(self) -> int:
        try:
            while not (self.finished() and self._queue.empty()):
                sleep(1)

            self.stop()
            # self._queue.join()
            total = datetime.datetime.now() - self.__started_at
            self._logger.info("Crawl finished in %s", total)
            self._logger.info("Crawled %s urls", self.total_crawled())
        except KeyboardInterrupt:
            self.stop()
        finally:
            return self.total_crawled()

