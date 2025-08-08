import logging
import typing as tp

from src.api.handlers.response import AbstractResponse

handle_exception_signature = tp.Callable[[Exception], AbstractResponse | str]


class ExceptionHandler:
    _handle: handle_exception_signature

    def __init__(self, handle: handle_exception_signature):
        self._handle = handle

    def __call__(self, e: Exception) -> tp.Optional[bytes]:
        res = self._handle(e)
        return bytes(AbstractResponse.parse(res))


def __handle_exception(e: Exception) -> AbstractResponse | str:
    log = logging.getLogger("e_handler")
    log.error("Uncaught exception: %s", e)
    log.debug(e, exc_info=True)

    return "#!c=0\n" + str(e)


base_handler = ExceptionHandler(__handle_exception)
