import abc
import inspect
import logging
import typing as tp

from src.api.exceptions import BadRequest, BadHandlerSignature, NotIdentified
from .request import Request
from .response import AbstractResponse, StrResponse

handle_func_signature = tp.Callable[
    [tp.Optional[Request], tp.Any], AbstractResponse | str | None
]

# Just like WSGI, but for NomadNet
NSGI = tp.Callable[
    [str, tp.Optional[tp.Any], bytes, bytes, tp.Optional[bytes], float],
    tp.Optional[bytes],
]


class Handler:
    _handle: handle_func_signature
    _request_params: tp.List[inspect.Parameter]
    _forward_raw_request: bool
    _identifying_required: bool

    def __init__(
        self, path: str, handle: handle_func_signature, identifying_required=False
    ):
        self._forward_raw_request = False
        self._request_params = []

        self._parse_signature(handle)
        self._handle = handle
        self._identifying_required = identifying_required

        self._logger = logging.getLogger(path)

    def _parse_signature(self, handle: tp.Callable):
        if not callable(handle):
            raise TypeError("Handle object must be callable")
        first = True
        sig = inspect.signature(handle)
        for p_name, p_value in sig.parameters.items():
            p_type = p_value.annotation
            if p_type == Request:
                if not first:
                    raise BadHandlerSignature(
                        "'Request' argument must be first or omitted"
                    )
                self._forward_raw_request = True
                continue
            self._request_params.append(p_value)
            first = False

    def _parse_request_params(self, r: Request) -> tp.List[tp.Any]:
        params = []
        omitted_params = []
        mistyped_params = []

        if self._forward_raw_request:
            params.append(r)

        for p in self._request_params:
            p_name, p_type = p.name, p.annotation

            if not r.has_param(p_name):
                if p.default is p.empty:
                    omitted_params.append((p_name, p_type))
                else:
                    params.append(p.default)
                continue
            try:
                parsed = p_type(r.get_param(p_name))
                params.append(parsed)
            except Exception as e:
                self._logger.debug(
                    "Exception during %s conversion to %s: %s", p_name, p_type, e
                )
                mistyped_params.append((p_name, p_type))
        if mistyped_params or omitted_params:
            raise BadRequest(omitted_params, mistyped_params)
        return params

    def __handle_request(self, r: Request) -> tp.Optional[bytes]:
        if self._identifying_required and not r.remote_identity:
            raise NotIdentified(f"Identifying is required for {r.path} request")
        params = self._parse_request_params(r)
        res = self._handle(*params)

        return bytes(AbstractResponse.parse(res))

    def __call__(
        self,
        path: str,
        data: tp.Optional[tp.Any],
        request_id: bytes,
        link_id: bytes,
        remote_identity: tp.Optional[bytes],
        requested_at: float,
    ) -> tp.Optional[bytes]:
        self._logger.info("Processing request to %s", path)
        r = Request(path, data, request_id, link_id, remote_identity, requested_at)
        self._logger.debug("Request data: %s", r.data)
        return self.__handle_request(r)
