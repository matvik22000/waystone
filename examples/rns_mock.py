import datetime

import RNS
import typing as tp


def dummy_request(path, data):
    return path, data, b"123", b"123", None, datetime.datetime.now().timestamp()


class RNSMock:
    def __init__(self):
        self.handlers = dict()

    def register_request_handler(
        self, path: str, response_generator: tp.Callable, allow=None, allow_list=None
    ):
        self.handlers[path] = response_generator

    def request(
        self,
        path: str,
        data: tp.Optional[tp.Any],
        request_id: bytes,
        link_id: bytes,
        remote_identity: tp.Optional[bytes],
        requested_at: float,
    ) -> tp.Optional[bytes]:
        return self.handlers[path](
            path, data, request_id, link_id, remote_identity, requested_at
        )
