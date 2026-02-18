import logging
import os
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


def config_logger(level: int, log_folder_path: str, announce_keep_days):
    # Подавим логи сторонних библиотек
    for noisy in ["asyncio", "schedule", "httpx", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Общий формат
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    os.makedirs(log_folder_path, exist_ok=True)
    # Основной лог — всё кроме crawler-*
    main_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_folder_path, "app.log"), maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
    )
    main_handler.setFormatter(formatter)
    main_handler.addFilter(NotCrawlerFilter())

    # Лог только для crawler-*
    crawler_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_folder_path, "crawler.log"), maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
    )
    crawler_handler.setFormatter(formatter)
    crawler_handler.addFilter(CrawlerFilter())

    # Консоль
    console_handler = RNSLogHandler()
    console_handler.setFormatter(formatter)

    announce_dir = os.path.join(log_folder_path, "announces")
    os.makedirs(announce_dir, exist_ok=True)
    announce_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(announce_dir, "nomadnetwork.node.log"),
        when="midnight",
        interval=1,
        backupCount=max(1, int(announce_keep_days)),
        encoding="utf-8",
        utc=True,
    )
    announce_handler.setFormatter(logging.Formatter("%(message)s"))

    # Подключаем всё
    logging.basicConfig(
        level=level,
        handlers=[
            main_handler,
            crawler_handler,
            console_handler,
        ],
        force=True,
    )
    announce_logger = logging.getLogger("nomadnetwork.node.announce")
    announce_logger.handlers = [announce_handler]
    announce_logger.setLevel(logging.INFO)
    announce_logger.propagate = False
