import json
import os.path
from dataclasses import dataclass
from os import environ
import typing as tp

from src.api.store import JsonFileStore
from . import get_path

store = JsonFileStore(get_path("announces.json"))


def find_owner(identity: str) -> tp.Optional[tp.Tuple[str, str]]:
    peers = store.get("peers")
    if not peers:
        return None
    for peer in peers.values():
        if peer["identity"] == identity:
            return peer["name"], peer["dst"]
    return None


def find_node_by_address(address: str) -> tp.Optional[dict]:
    nodes = store.get("nodes")
    for node in nodes.values():
        if node["dst"] == address:
            return node
