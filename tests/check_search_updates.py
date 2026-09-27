"""Local regression check: python tests/check_search_updates.py (project dependencies required)."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(
        STORAGE_PATH=tmp, LOG_PATH=tmp, LOG_LEVEL="CRITICAL",
        RNS_CONFIGDIR=tmp, NODE_IDENTITY_PATH=tmp + "/unused-identity",
        TEMPLATES_DIR="templates", OPENBLAS_NUM_THREADS="1",
    )
    source, target, other = "a" * 32, "b" * 32, "c" * 32
    # Start with the deployed schema; migration must preserve rows and be repeatable.
    with sqlite3.connect(tmp + "/nomadapi.db") as db:
        db.execute("CREATE TABLE citations (id INTEGER PRIMARY KEY, target_address TEXT NOT NULL, "
                   "src_address TEXT NOT NULL, created_at FLOAT NOT NULL, removed BOOLEAN NOT NULL, "
                   "UNIQUE(target_address, src_address))")
        db.execute("INSERT INTO citations VALUES (1, ?, ?, 123, 0)", (target, source))
    from src.core.data.db import init_db, get_session
    from src.core.data.models import Citation, CrawlVisitedUrl
    from src.core.data.citations import citations
    from sqlalchemy import select, func

    init_db()
    init_db()
    with get_session() as session:
        legacy = session.get(Citation, 1)
        assert (legacy.src_url, legacy.created_at, legacy.removed) == ("", 123, False)
    one, two = source + ":/page/one.mu", source + ":/page/two.mu"
    citations.update_citations(one, [target + ":/page/index.mu", other + ":/page/index.mu"])
    citations.update_citations(two, [target + ":/page/index.mu"])
    assert citations.get_amount_for(target) == 1  # One node, two pages, one vote.
    citations.update_citations(one, [])
    assert citations.get_citations_for(target) == {source}
    assert citations.get_citations_for(other) == set()
    citations.update_citations(two, [])
    assert citations.get_citations_for(target) == set()
    citations.update_citations(one, [target + ":/page/index.mu"])
    assert citations.get_citations_for(target) == {source}
    with get_session() as session:
        assert session.get(Citation, 1).removed

    from src.core.crawler.crawler import Crawler
    crawler = Crawler(lambda _: None, lambda _: [], queue_maxsize=2, visited_cache_seconds=86400)
    for url in ["https://example.org/a.mu", "http://example.org/", "HTTPS://EXAMPLE.ORG/"]:
        assert not crawler.enqueue_url(url)
    with get_session() as session:
        assert session.scalar(select(func.count()).select_from(CrawlVisitedUrl)) == 0
    assert crawler.enqueue_url(source + ":/page/no-extension")
    assert crawler.enqueue_url(source + ":/page/a.mu`param=1")

    from src.core.search.search_engine import engine, SearchDocument, MuBoldFormatter
    from whoosh.searching import Hit
    from whoosh.qparser import MultifieldParser, OrGroup
    assert not engine.ix.storage.supports_mmap
    docs = [SearchDocument(url=f"{i:032x}:/page/index.mu", text="needle searchable content",
                           owner=source, address=f"{i:032x}", nodeName="Example")
            for i in range(510)]
    engine.index_documents(docs)
    with patch.object(Hit, "highlights", autospec=True, side_effect=AssertionError("premature highlight")):
        results = engine.query("needle")
        assert len(results) == 500
        assert all(r.text == "" for r in results)
        assert len(engine.query("needle")) == 500
    original = Hit.highlights
    calls = []
    def highlight(hit, *args, **kwargs):
        calls.append(hit["url"])
        return original(hit, *args, **kwargs)
    with patch.object(Hit, "highlights", highlight):
        page = engine.highlight_results("needle", results[20:40])
    assert calls == [r.url for r in results[20:40]]
    assert all("`!`_needle`_`!" in r.text for r in page)
    assert all(r.text == "" for r in results)
    # The snippets still use Whoosh's original query terms and formatter.
    with engine.ix.searcher() as searcher:
        parsed = MultifieldParser(["url", "text", "nodeName", "owner", "address"],
                                  schema=engine.schema, group=OrGroup).parse("needle")
        expected = searcher.search(parsed, limit=500)
        expected.formatter = MuBoldFormatter()
        expected.fragmenter.maxchars = 100
        snippets = {h["url"]: h.highlights("text") for h in expected}
    assert all(r.text == snippets[r.url] for r in page)
    assert engine.highlight_results("needle", []) == []
    page[0].name = "changed by view"
    results[0].name = "changed by caller"
    assert engine.query("needle")[0].name != "changed by caller"
    assert engine.query("brandnew") == []
    engine.index_documents([SearchDocument(docs[0].url, "brandnew needle", source, docs[0].address, "Example")])
    assert len(engine.query("brandnew")) == 1  # Commit invalidates cached misses.
    # URL resolution must survive segment merges and document renumbering.
    with engine.ix.writer() as writer:
        writer.delete_by_term("url", docs[1].url)
    engine.ix.optimize()
    surviving = engine.highlight_results("needle", results[:20])
    assert all(r.url != docs[1].url for r in surviving)
    assert all("needle" in r.text for r in surviving)

    commits = []
    with patch.object(engine, "_commit_documents", side_effect=lambda docs, optimize: commits.append(optimize)):
        for _ in range(2500):
            engine.queue_document(docs[0])
    assert commits == [False] * 249 + [True]
    assert engine._index_queue == []
    engine.queue_document(docs[0])
    with patch.object(engine, "_commit_documents", side_effect=OSError("disk failure")):
        try:
            engine.flush_index_queue()
            raise AssertionError("failure was swallowed")
        except OSError:
            pass
    assert len(engine._index_queue) == 1
    engine.flush_index_queue()
    assert engine._index_queue == []
    print("OK: citation migration/union, URL filtering, top-500, page highlights, cache, merge and batches")
