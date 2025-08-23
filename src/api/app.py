import logging
import os.path
import typing as tp
from dataclasses import dataclass, field
from functools import wraps
from time import sleep

import RNS
import LXMF
import schedule
from jinja2 import FileSystemLoader, Environment

from src.api.context import init_context
from src.api.exceptions import DoubleHandlerRegistration
from src.api.handlers.expetion_handler import (
    handle_exception_signature,
    base_handler,
    ExceptionHandler,
)
from src.api.handlers.handler import Handler, handle_func_signature
from src.api.store import AbstractStore, JsonFileStore
from src.config import CONFIG


@dataclass
class Config:
    templates_dir: str = field(default="templates")
    disable_templates: bool = field(default=False)
    store: AbstractStore = field(
        default=JsonFileStore(os.path.join(CONFIG.STORAGE_PATH, "api_user_data.json"))
    )

    enable_propagation_node: bool = field(default=False)
    propagation_node_identity: RNS.Identity = field(default=None)
    propagation_node_config: dict = field(default_factory=dict)


class NomadAPI:
    _handlers: tp.Dict[str, Handler]
    _exception_handlers: tp.Dict[tp.Type[Exception], ExceptionHandler]
    _config: Config
    scheduler: schedule.Scheduler

    def __init__(self, config=None):
        self._handlers = dict()
        self._exception_handlers = dict()
        self._config = config if config else Config()
        self.scheduler = schedule.Scheduler()
        self.logger = logging.getLogger("app")

        if not self._config.disable_templates:
            file_loader = FileSystemLoader(self._config.templates_dir)
            jinja_env = Environment(loader=file_loader)
        else:
            jinja_env = None

        self._store = self._config.store

        init_context(jinja_env, self._store)

    def request(self, *paths: str, identifying_required=False):
        def decorator(handle: handle_func_signature):
            for path in paths:
                handler = Handler(path, handle, identifying_required)
                self._add_handler(path, handler)

        return decorator

    def exception(self, *e_types: tp.Type[Exception]):
        def decorator(handle: handle_exception_signature):
            for e_type in e_types:
                self._add_exception_handler(e_type, ExceptionHandler(handle))

        return decorator

    def _handle_exception(self, e: Exception) -> tp.Optional[bytes]:
        for handle_exc, handler in self._exception_handlers.items():
            if issubclass(type(e), handle_exc):
                return handler(e)
        return base_handler(e)

    def _add_handler(self, path: str, handler: Handler):
        if path in self._handlers:
            raise DoubleHandlerRegistration("Duplicate handler for path %s" % path)
        self._handlers[path] = handler

    def _add_exception_handler(
        self, e_type: tp.Type[Exception], handler: handle_exception_signature
    ):
        if e_type in self._exception_handlers:
            raise DoubleHandlerRegistration(
                "Duplicate handler for exception %s" % e_type.__name__
            )
        self._exception_handlers[e_type] = handler

    def register_handlers(self, dst):
        for p, h in self._handlers.items():
            dst.deregister_request_handler(p)
            dst.register_request_handler(
                p, self._wrap_handler(h), allow=RNS.Destination.ALLOW_ALL
            )

    def _wrap_handler(self, handler: Handler):
        @wraps(handler)
        def inner(
            path: str,
            data: tp.Optional[tp.Any],
            request_id: bytes,
            link_id: bytes,
            remote_identity: tp.Optional[bytes],
            requested_at: float,
        ) -> tp.Optional[bytes]:
            try:
                return handler(
                    path, data, request_id, link_id, remote_identity, requested_at
                )
            except Exception as e:
                return self._handle_exception(e)

        return inner

    def run(self):
        # if self._config.enable_propagation_node:
        #     self._start_propagation_node()
        self.logger.info("app started")
        for job in self.scheduler.jobs:
            job.run()
        while True:
            self.scheduler.run_pending()
            sleep(10)

    # def _start_propagation_node(self):
    #     n = create_propagation_node(self._config.propagation_node_identity, **self._config.propagation_node_config)
    #     n.announce_propagation_node()
    #     n.enable_propagation()
    #     self.scheduler.every(10).minutes.do(n.announce_propagation_node)


# def create_propagation_node(identity: RNS.Identity, **kwargs):
#     lxm_router = LXMF.LXMRouter(identity=identity, **kwargs)
#     lxm_router.propagation_node = True
#     return lxm_router


def create_rns_dest(
    rns_configdir: str, identitypath: str
) -> tp.Tuple[RNS.Destination, RNS.Identity]:
    reticulum = RNS.Reticulum(rns_configdir)
    if os.path.exists(identitypath):
        identity = RNS.Identity.from_file(identitypath)
    else:
        logging.getLogger("destination").info(
            "Identity file %s not found, generating new" % identitypath
        )
        identity = RNS.Identity()
        os.makedirs(os.path.dirname(identitypath), exist_ok=True)
        identity.to_file(identitypath)
    dest = RNS.Destination(
        identity, RNS.Destination.IN, RNS.Destination.SINGLE, "nomadnetwork", "node"
    )
    return dest, identity
