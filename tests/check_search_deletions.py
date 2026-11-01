"""Regression check for deletion commits and rollback; no production data or RNS."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(STORAGE_PATH=tmp, LOG_PATH=tmp, LOG_LEVEL="CRITICAL",
                      RNS_CONFIGDIR=tmp, NODE_IDENTITY_PATH=tmp + "/unused",
                      TEMPLATES_DIR="templates", OPENBLAS_NUM_THREADS="1")
    from src.core.data.db import init_db
    init_db()
    from src.core.search.search_engine import engine, SearchDocument

    docs = [SearchDocument(url=f"{i:032x}:/page/index.mu", text="needle",
                           owner="a" * 32, address=f"{i:032x}", nodeName="Example")
            for i in range(4)]
    engine.index_documents(docs)
    assert len(engine.query("needle")) == 4
    with patch("whoosh.writing.OPTIMIZE", side_effect=AssertionError("full optimize called")):
        engine.delete_by_address(docs[0].address)
    assert {r.address for r in engine.query("needle")} == {d.address for d in docs[1:]}

    # Both a partial deletion failure and a commit failure must roll back and unlock.
    for failure in ("delete", "commit"):
        writer = engine.ix.writer()
        original_delete = writer.delete_by_term
        calls = []
        error = OSError("simulated write failure")
        def delete(field, value):
            calls.append(value)
            if len(calls) == 2:
                raise error
            return original_delete(field, value)
        failing = (patch.object(writer, "delete_by_term", side_effect=delete)
                   if failure == "delete" else patch.object(writer, "commit", side_effect=error))
        with patch.object(engine.ix, "writer", return_value=writer), failing:
            try:
                engine.delete_by_address([docs[1].address, docs[2].address])
            except OSError as caught:
                assert caught is error
            else:
                raise AssertionError("failure was swallowed")
        assert writer.is_closed
        assert not (Path(tmp) / "search_index" / "MAIN.tmp").exists()
        with engine.ix.searcher() as searcher:
            assert searcher.document(url=docs[1].url) is not None
            assert searcher.document(url=docs[2].url) is not None
        # Taking a real writer verifies that the failed operation released its lock.
        probe = engine.ix.writer()
        probe.cancel()

    with patch.object(engine.ix, "writer", side_effect=AssertionError("empty deletion writes")):
        engine.delete_by_address([])
    engine.delete_by_address([docs[1].address, docs[2].address])
    assert [r.address for r in engine.query("needle")] == [docs[3].address]

print("OK: immediate deletion, no full optimize, cache invalidation, rollback and cleanup on both failures")
