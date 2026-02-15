import logging
import os.path

from .config import optional, required, Config
from .logger import config_logger


class __Cfg(Config):
    STORAGE_PATH: str = required()
    TIME_FORMAT: str = optional("%d.%m.%Y, %H:%M:%S")
    RNS_CONFIGDIR: str = required()
    NODE_IDENTITY_PATH: str = required()
    ANNOUNCE_NAME: str = optional("Waystone")
    CRAWLER_THREADS: int = optional(5)
    CRAWLER_QUEUE_MAXSIZE: int = optional(5000)
    CRAWLER_VISITED_CACHE_SECONDS: int = optional(24 * 60 * 60)
    NODE_REMOVE_AFTER_DAYS: int = optional(30)

    TEMPLATES_DIR: str = required()
    LOG_PATH: str = optional("app.log")
    LOG_LEVEL: str = required()


CONFIG: __Cfg = __Cfg()

config_logger(getattr(logging, CONFIG.LOG_LEVEL.upper(), logging.INFO), CONFIG.LOG_PATH)
