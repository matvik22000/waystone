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

    TEMPLATES_DIR: str = required()
    LOG_PATH: str = optional("app.log")


CONFIG: __Cfg = __Cfg()

config_logger(logging.DEBUG, CONFIG.LOG_PATH)
