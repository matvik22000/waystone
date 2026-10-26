import asyncio
import typing as tp

import RNS

APP_NAME = "nomadnetwork"


class _AsyncWrapper:
    def __init__(self):
        self.res = None
        self._completed = False
        self._error = None

    def on_success(self, res):
        self.res = res
        self._completed = True

    def on_failure(self, res):
        self._error = RequestError(res, "Request failed")
        self._completed = True

    async def get(self):
        while not self._completed:
            await asyncio.sleep(0.1)
        if self._error is not None:
            raise self._error
        return self.res


class RequestError(Exception):
    res: RNS.RequestReceipt

    def __init__(self, res, *args: object) -> None:
        super().__init__(*args)
        self.res = res

    def result(self):
        return self.res


class _RequestLink(RNS.Link):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            # RNS registers the link before starting its watchdog thread.
            if self in RNS.Transport.pending_links:
                self.teardown()
            raise


async def async_request(url: str, data: dict | None = None) -> RNS.RequestReceipt:
    server, path = await parse_url(url)
    established = _AsyncWrapper()
    link = None
    try:
        link = _RequestLink(server, established_callback=established.on_success)
        await established.get()
        res = _AsyncWrapper()
        link.request(
            path=path,
            data=data,
            response_callback=res.on_success,
            failed_callback=res.on_failure,
        )
        return await res.get()
    finally:
        if link is not None and link.status != RNS.Link.CLOSED:
            link.teardown()


def request(
    url: str, data: dict | None = None, timeout: int = 20
) -> RNS.RequestReceipt:
    return asyncio.run(asyncio.wait_for(async_request(url, data), timeout))


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
