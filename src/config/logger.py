import logging
import sys
from logging import LogRecord
import logging.handlers

import RNS


class RNSLogHandler(logging.StreamHandler):
    levels = {
        logging.DEBUG: RNS.LOG_DEBUG,
        logging.INFO: RNS.LOG_INFO,
        logging.WARNING: RNS.LOG_WARNING,
        logging.ERROR: RNS.LOG_ERROR,
        logging.CRITICAL: RNS.LOG_CRITICAL,
    }

    def emit(self, record: LogRecord) -> None:
        rns_level = self.levels[record.levelno]
        RNS.log(self.format(record), rns_level)


class CrawlerFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith("crawler")


class NotCrawlerFilter(logging.Filter):
    def filter(self, record):
        return not record.name.startswith("crawler")


def config_logger(level: int, log_file_path: str):
    # Suppress logs from third-party libraries
    for noisy in ["asyncio", "schedule", "httpx", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Common format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    # Main log — everything except crawler-*
    main_handler = logging.handlers.RotatingFileHandler(
        log_file_path, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
    )
    main_handler.setFormatter(formatter)
    main_handler.addFilter(NotCrawlerFilter())  # 👈 filter "everything except crawler-*"

    # Log only for crawler-*
    crawler_handler = logging.handlers.RotatingFileHandler(
        "crawler.log", maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
    )
    crawler_handler.setFormatter(formatter)
    crawler_handler.addFilter(CrawlerFilter())  # 👈 filter "only crawler-*"

    # Console
    console_handler = RNSLogHandler()
    console_handler.setFormatter(formatter)

    # Connect everything
    logging.basicConfig(
        level=level,
        handlers=[
            main_handler,
            crawler_handler,
            console_handler,
        ],
    )
