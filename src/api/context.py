from dataclasses import dataclass

from jinja2 import Environment, FileSystemLoader

from src.api.store import AbstractStore


@dataclass
class _Context:
    jinja_env: Environment | None
    store: AbstractStore

    def init_jinja(self, path):
        file_loader = FileSystemLoader(path)
        self.jinja_env = Environment(loader=file_loader)


__ctx: _Context | None = None


def init_context(env: Environment, store: AbstractStore):
    global __ctx
    __ctx = _Context(env, store)


def ctx() -> _Context:
    if not __ctx:
        raise ValueError("Context is not initialized")
    return __ctx
