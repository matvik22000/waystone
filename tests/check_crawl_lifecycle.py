"""Crawl concurrency and worker lifecycle checks, without network access."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(STORAGE_PATH=tmp, LOG_PATH=tmp, LOG_LEVEL="CRITICAL",
                      RNS_CONFIGDIR=tmp, NODE_IDENTITY_PATH=tmp + "/unused",
                      TEMPLATES_DIR="templates", OPENBLAS_NUM_THREADS="1")
    module = importlib.import_module("src.core.crawl")
    entered, finish, flushing, flushed = [threading.Event() for _ in range(4)]
    made, errors = [], []
    class FakeCrawler:
        def __init__(self, *args, **kwargs):
            made.append(self)
            self.stopped = False
        def add_url(self, url): pass
        def start(self, threads): entered.set()
        def join(self): assert finish.wait(5)
        def stop(self): self.stopped = True
    def flush():
        flushing.set()
        assert flushed.wait(5)
    def invoke():
        try: module.crawl(lambda _: None, lambda *_: None)
        except BaseException as e: errors.append(e)
    with patch.object(module, "Crawler", FakeCrawler), \
         patch.object(module, "get_recent_nodes_for_crawl", return_value=["a" * 32]), \
         patch.object(module.search_engine, "flush_index_queue", side_effect=flush):
        thread = threading.Thread(target=invoke)
        thread.start()
        try:
            assert entered.wait(5)
            invoke()
            assert len(made) == 1
            finish.set()
            assert flushing.wait(5)
            invoke()  # The guard must remain held during final index flush.
            assert len(made) == 1
        finally:
            finish.set(); flushed.set(); thread.join(5)
        assert not thread.is_alive() and not errors and made[0].stopped
        invoke()
        assert len(made) == 2 and made[1].stopped
        for phase in ("start", "join"):
            with patch.object(FakeCrawler, phase, side_effect=RuntimeError(phase)):
                invoke()
            assert isinstance(errors.pop(), RuntimeError) and made[-1].stopped
            invoke()  # Recovery after an exception must allow another crawl.
            assert made[-1].stopped and not errors
        with patch.object(module.search_engine, "flush_index_queue", side_effect=OSError("disk")):
            invoke()
        assert isinstance(errors.pop(), OSError) and made[-1].stopped
        invoke()
        assert not errors
        with patch.object(module, "get_recent_nodes_for_crawl", return_value=[]):
            invoke()
        invoke()
        assert not errors

    from src.core.data.db import init_db
    from src.core.crawler.crawler import Crawler
    init_db()
    parent, child = "b" * 32 + ":/page/index.mu", "b" * 32 + ":/page/child.mu"
    processing, release = threading.Event(), threading.Event()
    seen = []
    def extract(url):
        seen.append(url)
        if url == parent:
            processing.set()
            assert release.wait(5)
            return [child]
        raise ValueError("simulated parser error")
    crawler = Crawler(lambda url: url, extract, queue_maxsize=10, visited_cache_seconds=60)
    crawler.add_url(parent)
    joined = threading.Event()
    def join():
        try: crawler.join()
        except BaseException as e: errors.append(e)
        finally: joined.set()
    with patch("src.core.crawler.crawler.random.random", return_value=0):
        crawler.start(2)
        thread = threading.Thread(target=join, daemon=True)
        thread.start()
        try:
            assert processing.wait(5)
            assert not joined.wait(0.05)
        finally:
            release.set()
        assert joined.wait(5), "worker error left the queue stuck"
        thread.join(1)
    assert seen == [parent, child] and not errors
    assert crawler._queue.unfinished_tasks == 0
    assert crawler.finished() and all(not t.is_alive() for t in crawler._threads)

print("OK: no overlap through flush, recovery after failures/empty crawl, child URLs, worker errors, all workers joined")
