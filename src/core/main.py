from threading import Thread

from src.core.data.nods_and_peers import mark_stale_nodes_removed, upsert_node
from src.core.search.pagerank import pagerank
from src.config import CONFIG
from src.core.data.citations import citations
from src.core.data.nods_and_peers import find_node_by_address
from src.core.utils import get_process_rss_bytes, now


def main():
    import logging

    from src.core.data.db import init_db

    init_db()

    from src.api.handlers.response import AbstractResponse, render_template
    from src.core.crawl import crawl
    from src.core.jinja import register_filters
    from src.core.rns import dst
    from src.core.views import app
    from src.core.search.search_engine import engine as search_engine

    from time import sleep

    from src.core.crawl import crawl

    def find_node_name_by_address(address):
        node = find_node_by_address(address)
        if node:
            return node.get("name")
        else:
            return None

    def start_crawling_in_thread():
        Thread(
            target=crawl,
            args=(find_node_name_by_address, citations.update_citations),
            daemon=True,
        ).start()

    def remove_stale_nodes():
        removed_addresses = mark_stale_nodes_removed(CONFIG.NODE_REMOVE_AFTER_DAYS)
        if removed_addresses:
            search_engine.delete_by_address(removed_addresses)
        logging.getLogger("remove-stale-nodes").info("removed %s nodes", len(removed_addresses))

    def log_rss_usage():
        rss_bytes = get_process_rss_bytes()
        if rss_bytes is None:
            return
        rss_mb = rss_bytes / (1024 * 1024)
        logging.getLogger("memory").info("Process RSS: %.2f MB", rss_mb)

    app.scheduler.every(10).minutes.do(
        lambda: logging.getLogger("announce").debug(
            "announce with data %s", CONFIG.ANNOUNCE_NAME
        )
        or upsert_node(dst.hexhash, dst.identity.hexhash, CONFIG.ANNOUNCE_NAME, now().timestamp())
        or dst.announce(CONFIG.ANNOUNCE_NAME.encode("utf-8"))
    )
    app.scheduler.every(6).hours.do(pagerank)
    app.scheduler.every(1).days.do(remove_stale_nodes)
    app.scheduler.every(5).minutes.do(log_rss_usage)
    app.scheduler.every(1).hours.do(start_crawling_in_thread)

    register_filters()

    @app.exception(Exception)
    def handle_exception(e: Exception) -> AbstractResponse:
        log = logging.getLogger("e_handler")
        log.error("Uncaught exception: %s", e)
        log.error(e, exc_info=True)

        return render_template("error.mu", dict(error=str(e)))

    app.register_handlers(dst)
    app.run()
