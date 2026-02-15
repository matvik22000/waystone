"""
One-time migration: load data from JSON files (announces.json, citations.json,
queries.json, api_user_data.json) into SQLite.
Run from project root with env set: python -m src.core.data.migrate_json_to_sqlite
"""
import json
import os
import time

from src.config import CONFIG
from src.core.data.db import get_session, init_db
from src.core.data.models import (
    Citation,
    Node,
    Peer,
    SearchQuery,
    UserSearchHistory,
)


def _now() -> float:
    return time.time()


def migrate_announces(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        data = json.load(f)
    now_ = _now()
    count = 0
    with get_session() as session:
        for _, rec in data.get("nodes", {}).items():
            session.add(
                Node(
                    dst=rec["dst"],
                    identity=rec["identity"],
                    name=rec["name"],
                    time=rec["time"],
                    created_at=now_,
                    updated_at=now_,
                    rank=0.0,
                )
            )
            count += 1
        for _, rec in data.get("peers", {}).items():
            session.add(
                Peer(
                    dst=rec["dst"],
                    identity=rec["identity"],
                    name=rec["name"],
                    time=rec["time"],
                    created_at=now_,
                    updated_at=now_,
                )
            )
            count += 1
    return count


def migrate_citations(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        data = json.load(f)
    for_search = data.get("for_search", {})
    now_ = _now()
    count = 0
    with get_session() as session:
        for target_address, src_list in for_search.items():
            for src_address in set(src_list):  # dedupe
                if len(target_address) != 32 or len(src_address) != 32:
                    continue
                session.add(
                    Citation(
                        target_address=target_address,
                        src_address=src_address,
                        created_at=now_,
                    )
                )
                count += 1
    return count


def migrate_queries(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        data = json.load(f)
    queries_list = data.get("queries", [])
    now_ = _now()
    count = 0
    with get_session() as session:
        for q in queries_list:
            if not q or not isinstance(q, str):
                continue
            session.add(SearchQuery(query=q.strip(), created_at=now_))
            count += 1
    return count


def migrate_api_user_data(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        data = json.load(f)
    count = 0
    with get_session() as session:
        for remote_identity, items in data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or "q" not in item or "time" not in item:
                    continue
                session.add(
                    UserSearchHistory(
                        remote_identity=remote_identity,
                        query=item["q"],
                        time=item["time"],
                        created_at=item["time"],
                    )
                )
                count += 1
    return count


def main():
    storage = CONFIG.STORAGE_PATH
    os.makedirs(storage, exist_ok=True)

    init_db()

    announces_path = os.path.join(storage, "announces.json")
    citations_path = os.path.join(storage, "citations.json")
    queries_path = os.path.join(storage, "queries.json")
    api_user_data_path = os.path.join(storage, "api_user_data.json")

    n = migrate_announces(announces_path)
    print(f"announces.json -> nodes/peers: {n} rows")
    n = migrate_citations(citations_path)
    print(f"citations.json -> citations: {n} rows")
    n = migrate_queries(queries_path)
    print(f"queries.json -> search_queries: {n} rows")
    n = migrate_api_user_data(api_user_data_path)
    print(f"api_user_data.json -> user_search_history: {n} rows")
    print("Migration done.")


if __name__ == "__main__":
    main()
