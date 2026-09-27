"""Run with project dependencies: python tests/check_nodes_updates.py."""
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
    from sqlalchemy import event, select
    from src.core.data.db import _engine, get_session, init_db
    from src.core.data.models import Node, Peer, Citation
    from src.core.data import nods_and_peers as nodes
    from src.core.data.citations import citations
    from src.core.search.nodes_downtime import dead_probability_ci, gamma_ppf

    init_db()
    # Existing installations also get the index; repeated startup is harmless.
    with _engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX idx_nodes_listing")
    init_db()
    init_db()
    with get_session() as session:
        for i in range(45):
            session.add(Node(dst=f"{i:032x}", identity=str(i % 3), name=f"Node {i}",
                             time=100, rank=i % 5, created_at=0, updated_at=0, removed=i == 44))
        for i in range(4):
            session.add(Peer(dst=f"{i:032x}", identity=str(i % 2), name=f"Owner {i}",
                             time=100, created_at=0, updated_at=0))
        for i in range(45):
            for page in ("one", "two"):
                session.add(Citation(target_address="f" * 32, src_address=f"{i:032x}",
                                     src_url=f"{i:032x}:/{page}", created_at=0, removed=i == 43))

    queries = []
    def record(conn, cursor, statement, parameters, context, many):
        queries.append(statement)
    event.listen(_engine, "before_cursor_execute", record)
    total = nodes.count_nodes_filtered()
    page = nodes.get_nodes_page(0, 20)
    owners = nodes.find_owners(n["identity"] for n in page)
    counts = citations.get_amounts_for(n["dst"] for n in page)
    assert total == 44 and len(page) == 20 and len(queries) == 4
    assert counts == {}
    for n in page:
        assert owners.get(n["identity"]) == nodes.find_owner(n["identity"])
    assert citations.get_amount_for("f" * 32) == 44  # Distinct nodes, not 88 pages.
    assert citations.get_amount_for("missing") == 0
    assert nodes.find_owners([]) == citations.get_amounts_for([]) == {}

    addresses = citations.get_citations_for("f" * 32)
    with get_session() as session:
        expected = list(session.scalars(select(Node.dst).where(
            Node.dst.in_(addresses), Node.removed.is_(False)).order_by(Node.dst)))
    with patch.object(nodes, "_node_to_dict", wraps=nodes._node_to_dict) as convert:
        count, page = nodes.get_nodes_for_addresses_page(addresses, 1, 20)
        assert count == 43 and [n["dst"] for n in page] == expected[20:40]
        assert convert.call_count == 20
    assert nodes.get_nodes_for_addresses_page(addresses, 99, 20) == (43, [])
    assert nodes.get_nodes_for_addresses_page([], 0, 20) == (0, [])
    with _engine.connect() as conn:
        plan = str(conn.exec_driver_sql(
            "EXPLAIN QUERY PLAN SELECT * FROM nodes WHERE removed IS 0 "
            "ORDER BY rank DESC, time DESC LIMIT 20").all())
        assert "idx_nodes_listing" in plan and "TEMP B-TREE" not in plan

    gamma_ppf.cache_clear()
    first = dead_probability_ci(3, 1800, 60)
    second = dead_probability_ci(3, 1800, 3600)
    assert first != second and gamma_ppf.cache_info().hits == 2
    dead_probability_ci(4, 1800, 3600)
    assert gamma_ppf.cache_info().misses == 4
    assert gamma_ppf(.95, 4, 1800) == gamma_ppf.__wrapped__(.95, 4, 1800)
    print("nodes checks passed: 4 queries, distinct citations, pagination, index, live availability")
