"""Regression check for startup cleanup; uses only a temporary index."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(
        STORAGE_PATH=tmp, LOG_PATH=tmp, LOG_LEVEL="CRITICAL",
        RNS_CONFIGDIR=tmp, NODE_IDENTITY_PATH=tmp + "/unused-identity",
        TEMPLATES_DIR=str(repo / "templates"), OPENBLAS_NUM_THREADS="1",
    )
    from src.core.search.search_engine import engine

    index_dir = Path(tmp) / "search_index"
    temp_dir = index_dir / "MAIN.tmp"
    outside = Path(tmp) / "keep"
    outside.mkdir()
    (outside / "sentinel").write_text("keep")

    def start(expected_error=None):
        code = "from src.core.search.search_engine import engine"
        if expected_error:
            code = ("try:\n " + code + "\nexcept Exception as e:\n"
                    " assert type(e).__name__ == " + repr(expected_error) + "\n"
                    "else:\n raise AssertionError('startup should refuse cleanup')")
        subprocess.run([sys.executable, "-c", code], cwd=repo, check=True,
                       capture_output=True, text=True, timeout=30)

    writer = engine.ix.writer()
    writer.add_document(url="first", text="needle", raw="needle")
    writer.commit()
    generation = engine.ix.latest_generation()
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in index_dir.iterdir() if p.is_file() and p.suffix in (".seg", ".toc")}
    assert files
    temp_dir.mkdir()
    (temp_dir / "abandoned.run").write_text("unfinished")
    (temp_dir / "nested-link").symlink_to(outside, target_is_directory=True)
    start()
    start()  # An already clean startup is harmless.
    assert not temp_dir.exists()
    assert (outside / "sentinel").read_text() == "keep"
    assert engine.ix.latest_generation() == generation
    for name, digest in files.items():
        assert hashlib.sha256((index_dir / name).read_bytes()).hexdigest() == digest
    with engine.ix.searcher() as searcher:
        assert searcher.document(url="first")["text"] == "needle"

    writer = engine.ix.writer()
    try:
        marker = temp_dir / "live-writer.run"
        marker.write_text("in use")
        start("LockError")
        assert marker.read_text() == "in use"
        writer.add_document(url="second", text="still writable", raw="still writable")
        writer.commit()
    finally:
        if not writer.is_closed:
            writer.cancel()
    with engine.ix.searcher() as searcher:
        assert searcher.document(url="second")["text"] == "still writable"

    temp_dir.symlink_to(outside, target_is_directory=True)
    start("ValueError")
    assert (outside / "sentinel").read_text() == "keep"
    temp_dir.unlink()
    start()  # Failed cleanup must release the write lock.

print("OK: stale cleanup, repeat startup, unchanged index, active writer, symlinks, lock release")
