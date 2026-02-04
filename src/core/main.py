from threading import Thread

from src.config import CONFIG
from src.core.data.citations import citations
from src.core.data.store import find_node_by_address


def main():
    import logging

    from src.core.data.db import init_db

    init_db()

    from src.api.handlers.response import AbstractResponse, render_template
    from src.core.crawl import crawl
    from src.core.jinja import register_filters
    from src.core.rns import dst
    from src.core.views import app

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

    app.scheduler.every(5).minutes.do(
        lambda: logging.getLogger("announce").debug(
            "announce with data %s", CONFIG.ANNOUNCE_NAME
        )
        or dst.announce(CONFIG.ANNOUNCE_NAME.encode("utf-8"))
    )
    app.scheduler.every(5).minutes.do(start_crawling_in_thread)

    register_filters()

    @app.exception(Exception)
    def handle_exception(e: Exception) -> AbstractResponse:
        log = logging.getLogger("e_handler")
        log.error("Uncaught exception: %s", e)
        log.debug(e, exc_info=True)

        return render_template("error.mu", dict(error=str(e)))

    app.register_handlers(dst)
    app.run()
