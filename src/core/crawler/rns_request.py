import asyncio
import re
from asyncio.futures import Future
import logging
from dataclasses import dataclass
from time import sleep

from async_timeout import timeout as atimeout

import RNS
import typing as tp

APP_NAME = "nomadnetwork"


class _AsyncWrapper:
    def __init__(self):
        self.res = None
        self._completed = False

    def on_success(self, res):
        self._completed = True
        self.res = res

    async def get(self):
        while not self._completed:
            await asyncio.sleep(0.1)
        return self.res


class RequestError(Exception):
    res: RNS.RequestReceipt

    def __init__(self, res, *args: object) -> None:
        super().__init__(*args)
        self.res = res

    def result(self):
        return self.res


async def establish_link(dst: RNS.Destination):
    link = _AsyncWrapper()
    RNS.Link(dst, established_callback=link.on_success)
    return await link.get()


async def async_request(url: str, data: dict | None = None) -> RNS.RequestReceipt:
    server, path = await parse_url(url)
    link = await establish_link(server)
    res = _AsyncWrapper()

    def fail(_res):
        raise RequestError(_res, "Request failed")

    link.request(
        path=path,
        data=data,
        # progress_callback=lambda r: logger.debug("in progress: %s", r),
        response_callback=res.on_success,
        failed_callback=fail,
    )
    return await res.get()


def request(
    url: str, data: dict | None = None, timeout: int = 20
) -> RNS.RequestReceipt:
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(asyncio.wait_for(async_request(url, data), timeout))


def address_from_url(url: str):
    return url.split(":")[0]


async def parse_url(url: str) -> tp.Tuple[RNS.Destination, str]:
    if ":" not in url:
        raise ValueError("':' expected in url")
    dst_hash, path = url.split(":")
    dst = await get_dest(dst_hash)
    return dst, path


async def get_dest(destination_hexhash: str) -> RNS.Destination:
    destination_hash = bytes.fromhex(destination_hexhash)
    if not RNS.Transport.has_path(destination_hash):
        RNS.log(
            "Destination is not yet known. Requesting path and waiting for announce to arrive..."
        )
        RNS.Transport.request_path(destination_hash)
        while not RNS.Transport.has_path(destination_hash):
            await asyncio.sleep(0.1)

    server_identity = RNS.Identity.recall(destination_hash)
    server_destination = RNS.Destination(
        server_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, APP_NAME, "node"
    )
    return server_destination
