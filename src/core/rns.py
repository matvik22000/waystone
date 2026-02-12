import datetime
import logging

import LXMF
import RNS

from src.api import create_rns_dest
from src.config import CONFIG
from src.core.data.store import upsert_node, upsert_peer
from src.core.utils import now
import RNS.vendor.umsgpack as msgpack

# dst, identity = create_rns_dest("~/.reticulum", "~/.nomadnetwork/storage/identity")
dst, identity = create_rns_dest(CONFIG.RNS_CONFIGDIR, CONFIG.NODE_IDENTITY_PATH)


class AnnounceHandler:
    def __init__(self, aspect_filter: str, key: str):
        self.aspect_filter = aspect_filter
        self.key = key

    def received_announce(
            self, destination_hash, announced_identity: RNS.Identity, app_data
    ):
        if not app_data:
            return  # don't save announces without name
        destination = RNS.prettyhexrep(destination_hash)
        logging.getLogger(self.aspect_filter).debug(
            "received announce ident: %s, dst: %s, data: %s",
            announced_identity,
            destination,
            app_data,
        )
        if app_data.startswith(b"\x92\xc4\x0e") and app_data.endswith(b"\xc0"):
            name = app_data[3:-1].decode("utf-8")  # Вырезаем известные байты
        else:
            name = app_data.decode("utf-8", errors="replace")  # Фолбэк с заменой ошибок
        dst_clean = destination.replace("<", "").replace(">", "")
        ts = now().timestamp()
        if self.key == "nodes":
            upsert_node(destination, dst_clean, f"{announced_identity.hexhash}", name, ts)
        else:
            upsert_peer(destination, dst_clean, f"{announced_identity.hexhash}", name, ts)


RNS.Transport.register_announce_handler(AnnounceHandler("lxmf.delivery", "peers"))
RNS.Transport.register_announce_handler(AnnounceHandler("nomadnetwork.node", "nodes"))
