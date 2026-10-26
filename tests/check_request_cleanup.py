"""Run with project dependencies: python tests/check_request_cleanup.py."""
import asyncio
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.crawler import rns_request as requests

links = []
loops = []
mode = "success"
new_loop = asyncio.events.new_event_loop


def make_loop():
    loop = new_loop()
    loops.append(loop)
    return loop


def init(link, destination, established_callback):
    link.status = requests.RNS.Link.PENDING
    link.remote_identity = object()
    link.close_count = 0
    links.append(link)
    requests.RNS.Transport.pending_links.append(link)
    if mode == "constructor_failure":
        raise RuntimeError("can't start new thread")
    if mode != "connect_timeout":
        link.status = requests.RNS.Link.ACTIVE
        established_callback(link)


def close(link):
    link.close_count += 1
    link.status = requests.RNS.Link.CLOSED


def send(link, **kwargs):
    if mode == "request_failure":
        raise ValueError("send failed")
    receipt = SimpleNamespace(link=link, response=b"page")
    if mode == "callback_failure":
        # RNS invokes callbacks on its own threads, not the asyncio loop.
        thread = Thread(target=kwargs["failed_callback"], args=(receipt,))
        thread.start()
        thread.join()
    elif mode != "response_timeout":
        kwargs["response_callback"](receipt)


with patch.object(requests.RNS.Transport, "pending_links", []), \
     patch.object(requests.RNS.Link, "__init__", init), \
     patch.object(requests.RNS.Link, "teardown", close), \
     patch.object(requests.RNS.Link, "request", send), \
     patch.object(requests, "parse_url", AsyncMock(return_value=(object(), "/page/index.mu"))), \
     patch("asyncio.events.new_event_loop", make_loop):
    for mode, error in [
        ("success", None),
        ("constructor_failure", RuntimeError),
        ("connect_timeout", asyncio.TimeoutError),
        ("response_timeout", asyncio.TimeoutError),
        ("callback_failure", requests.RequestError),
        ("request_failure", ValueError),
    ]:
        try:
            receipt = requests.request("test", timeout=.03)
            assert error is None, mode
            assert receipt.response == b"page" and receipt.link.remote_identity is not None
        except Exception as exc:
            assert error is not None and isinstance(exc, error), (mode, exc)
        assert links[-1].status == requests.RNS.Link.CLOSED, mode
        assert links[-1].close_count == 1, mode
        assert loops[-1].is_closed(), mode
    mode = "success"
    for _ in range(50):
        requests.request("test")
    assert all(link.status == requests.RNS.Link.CLOSED for link in links)
    assert len(loops) == len(links) == 56 and all(loop.is_closed() for loop in loops)
print("request checks passed: success, constructor failure, both timeouts, callback failure, send failure, repeated cleanup")
