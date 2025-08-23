import datetime
import itertools
import logging
import random
import threading
import time
import typing as tp
from contextlib import contextmanager
from datetime import time
from queue import Queue, Empty
from threading import Thread
from time import sleep

from src.core.crawler.parser import extract_links

Document = tp.TypeVar("Document")
Loader = tp.Callable[[str], Document]
Extractor = tp.Callable[[Document], tp.List[str]]


class _Set:
    def __init__(self):
        self.__lock = threading.Lock()
        self.__set = set()

    def add(self, obj):
        with self.__lock:
            self.__set.add(obj)

    def contains(self, obj):
        with self.__lock:
            return obj in self.__set


class _Downloader(Thread):
    downloading: bool = False
    _queue: Queue
    _alive: bool = True
    _set: _Set

    _load: Loader
    _extract: Extractor

    def __init__(
        self, queue: Queue, name: str, _set: _Set, load: Loader, extract: Extractor
    ):
        super().__init__()
        self._queue = queue
        self._load = load
        self._extract = extract
        self._set = _set
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

        for url in urls:
            if self._set.contains(url):
                continue
            self._set.add(url)
            self._queue.put(url)

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

    _queue: Queue = Queue()
    _threads: tp.List[_Downloader]
    _logger = logging.getLogger("crawler")
    __started_at: datetime.datetime
    _set = _Set()

    def __init__(self, load: Loader, page_processor: Extractor):
        self._load = load
        self._extract = page_processor

    def start(self, threads=5):
        self._threads = []
        for i in range(threads):
            t = _Downloader(self._queue, str(i), self._set, self._load, self._extract)
            t.start()
            self._threads.append(t)
        self._logger.debug("started with %s downloader threads", threads)
        self.__started_at = datetime.datetime.now()

    def add_url(self, url: str):
        self._queue.put(url)

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


if __name__ == "__main__":

    def load(url):
        sleep(1)
        return (
            "addr",
            """"
`Faaa`B333

Here is a link without any label: `[:/page/index.mu]

This is a `[labeled link`72914442a3689add83a09a767963f57c:/page/index.mu] to the same page, but it's hard to see if you don't know it

Here is `F00f`_`[a more visible link`72914442a3689add83a09a767963f57c:/page/index.mu]`_`f

If you want to include pre-set variables, you can do it like this:

`Faaa
`=
`[Query the System`:/page/fields.mu`username|auth_token|action=view|amount=64]
`=
``
""",
        )

    def extract(a):
        internal, external = extract_links(*a)
        return internal + external

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(module)s %(message)s",
        handlers=[logging.StreamHandler()],
    )

    crawler = Crawler(load, extract)
    crawler.start(threads=2)
    crawler.add_url("l1")
    crawler.join()
