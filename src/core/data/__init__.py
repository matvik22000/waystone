import os.path

from src.config import CONFIG

store_path_base = CONFIG.STORAGE_PATH
if not os.path.exists(store_path_base):
    os.makedirs(store_path_base)


def get_path(p: str):
    return os.path.join(store_path_base, p)


from .store import store
from .search import engine as search_engine
