"""Run only against a local snapshot; never starts Reticulum or the app."""

import os, sys, json, time, statistics, resource, collections, argparse, tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "snapshot",
    type=Path,
    help="Local directory containing search_index and nomadapi.db",
)
parser.add_argument(
    "--memory",
    action="store_true",
    help="Measure RSS in a fresh process without corpus pre-scan",
)
parser.add_argument(
    "--mmap", action="store_true", help="Reproduce the high-memory production behavior"
)
parser.add_argument(
    "--query",
    action="append",
    help="Override benchmark queries; avoid wildcard queries",
)
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
root = args.snapshot.resolve()
if not (root / "search_index").is_dir() or not (root / "nomadapi.db").is_file():
    parser.error("snapshot must contain search_index/ and nomadapi.db")
if args.repeats < 1:
    parser.error("repeats must be positive")
repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
logs = tempfile.TemporaryDirectory(prefix="waystone-probe-")
os.environ.update(
    STORAGE_PATH=str(root),
    RNS_CONFIGDIR=str(root / "unused-rns"),
    NODE_IDENTITY_PATH=str(root / "unused-identity"),
    TEMPLATES_DIR=str(repo / "templates"),
    LOG_PATH=logs.name,
    LOG_LEVEL="CRITICAL",
    OPENBLAS_NUM_THREADS="1",
)
from src.core.search.search_engine import engine, MuBoldFormatter
from src.core.search.models import SearchResult

engine.ix.storage.supports_mmap = args.mmap
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh import scoring

if args.memory:

    def rss(stage):
        values = [
            line.strip()
            for line in Path("/proc/self/status").read_text().splitlines()
            if line.startswith(("VmRSS:", "VmHWM:", "VmSwap:"))
        ]
        print(json.dumps({"stage": stage, "memory": values}), flush=True)

    rss("import")
    with engine.ix.searcher() as searcher:
        rss("searcher")
        query = MultifieldParser(
            ["url", "text", "nodeName", "owner", "address"],
            schema=engine.schema,
            group=OrGroup,
        ).parse((args.query or ["network"])[0])
        hits = searcher.search(query, limit=None)
        rss("collect")
        for hit in hits:
            hit.fields()
        rss("fields_end")
    rss("closed")
    sys.exit(0)


def size(obj, seen=None):
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    n = sys.getsizeof(obj)
    if isinstance(obj, dict):
        n += sum(size(k, seen) + size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set)):
        n += sum(size(x, seen) for x in obj)
    elif hasattr(obj, "__dict__"):
        n += size(vars(obj), seen)
    return n


def measure(q, limit=None, late=False):
    t = time.perf_counter()
    stages = {}
    with engine.ix.searcher(weighting=scoring.BM25F()) as s:
        parsed = MultifieldParser(
            ["url", "text", "nodeName", "owner", "address"],
            schema=engine.schema,
            group=OrGroup,
        ).parse(q)
        hits = s.search(parsed, limit=limit)
        stages["collect"] = time.perf_counter() - t
        hits.formatter = MuBoldFormatter()
        hits.fragmenter.maxchars = 100
        out = []
        byurl = {}
        highlight_seconds = 0
        t = time.perf_counter()
        for h in hits:
            result = SearchResult(
                url=h["url"],
                text="" if late else h["text"],
                owner=h["owner"],
                address=h["address"],
                name=h.get("nodeName") or h["url"],
                score=h.score,
            )
            if late:
                byurl.setdefault(result.url, h)
            else:
                ht = time.perf_counter()
                result.text = h.highlights("text") or h["text"][:200]
                highlight_seconds += time.perf_counter() - ht
            out.append(result)
        stages["materialize_and_highlight"] = time.perf_counter() - t
        stages["highlight_all"] = highlight_seconds
        matched = len(out)
        t = time.perf_counter()
        out = engine.ranker.rerank(out)
        stages["rerank"] = time.perf_counter() - t
        if late:
            t = time.perf_counter()
            for r in out[:20]:
                h = byurl[r.url]
                r.text = h.highlights("text") or h["text"][:200]
            stages["highlight_page"] = time.perf_counter() - t
        else:
            stages["highlight_page"] = 0
    stages["total"] = sum(
        stages[k]
        for k in ["collect", "materialize_and_highlight", "rerank", "highlight_page"]
    )
    return {
        "seconds": stages,
        "matched": matched,
        "ranked": len(out),
        "result_bytes": size(out),
        "top20": [r.url for r in out[:20]],
    }


with engine.ix.searcher() as s:
    lengths = []
    addresses = collections.Counter()
    urls = collections.Counter()
    raw_equal = 0
    for doc in s.all_stored_fields():
        lengths.append(len(doc.get("text", "").encode()))
        addresses[doc["address"]] += 1
        urls[doc["url"]] += 1
        raw_equal += doc.get("raw") == doc.get("text")
    info = {
        "all_docs": s.doc_count_all(),
        "live_docs": s.doc_count(),
        "segments": len(s.reader().leaf_readers()),
        "text_bytes": sum(lengths),
        "text_max": max(lengths),
        "text_median": statistics.median(lengths),
        "text_p95": sorted(lengths)[int(len(lengths) * 0.95)],
        "addresses": len(addresses),
        "max_pages_per_address": max(addresses.values()),
        "duplicate_urls": sum(n - 1 for n in urls.values()),
        "raw_equal": raw_equal,
        "highlight_charlimit": s.search(
            MultifieldParser(["text"], schema=engine.schema).parse("test")
        ).fragmenter.charlimit,
    }
print(json.dumps({"index": info}), flush=True)
for q in args.query or ["zzzzunfindableaudit", "reticulum", "test", "network", "page"]:
    variants = {}
    for name, limit, late in [
        ("current", None, False),
        ("late_highlight", None, True),
        ("top200_late", 200, True),
    ]:
        runs = [measure(q, limit, late) for _ in range(args.repeats)]
        v = runs[-1]
        v["seconds"] = {
            k: statistics.median(r["seconds"][k] for r in runs) for k in v["seconds"]
        }
        variants[name] = v
    base = variants["current"]["top20"]
    assert variants["late_highlight"]["top20"] == base, (
        "Late highlighting changed ranking"
    )
    assert variants["late_highlight"]["ranked"] == variants["current"]["ranked"]
    for name, v in variants.items():
        top = v.pop("top20")
        v["top20_overlap"] = len(set(top) & set(base))
        v["top20_same_order"] = base == top
    print(
        json.dumps(
            {
                "query": q,
                "variants": variants,
                "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                / 1024,
            }
        ),
        flush=True,
    )
