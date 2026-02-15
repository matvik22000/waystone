import asyncio
import logging
import re
from dataclasses import dataclass
import typing as tp
from typing import Callable

import RNS

from src.core.search import SearchDocument
from src.core.search import engine as search_engine
from src.config import CONFIG
from src.core.crawler.crawler import Crawler
from src.core.crawler.parser import extract_links
from src.core.crawler.rns_request import address_from_url, request
from src.core.data.nods_and_peers import get_recent_nodes_for_crawl

logger = logging.getLogger("crawler")

# Компилируем регулярки один раз
_RE_FB = re.compile(r"`[fb]")
_RE_FB_CAPS = re.compile(r"`[FB]...")
_RE_TAGS = re.compile(r"`<[^>]*>")
_RE_COMMENT = re.compile(r"#.*$", flags=re.MULTILINE)
_RE_GT_LINE_START = re.compile(r"^\s*>+", flags=re.MULTILINE)
_RE_SPACES = re.compile(r"[ \t]+")
_RE_PARAGRAPH = re.compile(r"\n\s*\n+")

# Символы для удаления как `x`
_MICRON_CHARS = "car!_=`"


def strip_micron(text: str) -> str:
    text = _RE_FB.sub("", text)
    text = _RE_FB_CAPS.sub("", text)

    for t in _MICRON_CHARS:
        text = text.replace(f"`{t}", "")

    text = _RE_TAGS.sub(" ", text)
    text = _RE_COMMENT.sub("", text)
    text = _RE_GT_LINE_START.sub("", text)
    text = text.replace("\\", " ")
    text = _RE_SPACES.sub(" ", text)
    text = _RE_PARAGRAPH.sub("\n\n", text)
    text = text.replace("`", "")

    return text


@dataclass
class Document:
    url: str
    response: RNS.RequestReceipt | None

    def get_info(self) -> tuple[RNS.Link | None, str | None]:
        if self.response is None:
            return None, None
        response = self.response
        # Explicitly release receipt reference to reduce retained memory.
        self.response = None
        try:
            text = response.response.decode("utf-8")
        except Exception:
            logging.debug("Empty document")
            text = None
        return response.link, text


def load(url: str) -> Document | None:
    try:
        if ".mu" not in url:
            logger.debug("skipping url %s", url)
            return None
        res = request(url)
        return Document(url, res)
    except asyncio.exceptions.TimeoutError:
        logger.debug("loading %s failed due to timeout", url)
        return None


def extract(
    doc: Document | None,
    get_name_by_address: Callable[[str], str | None] | None = None,
    update_citations: Callable[[str, tp.List[str]], None] | None = None,
) -> tp.List[str]:
    if not doc:
        return []
    link, text = doc.get_info()
    if not link or not text:
        return []
    remote_identity: RNS.Identity = link.get_remote_identity()
    address = address_from_url(doc.url)
    index_entry = SearchDocument(
        url=doc.url,
        text=strip_micron(text),
        owner=remote_identity.hexhash,
        address=address,
        nodeName=None,
    )

    if get_name_by_address:
        nodeName = get_name_by_address(address)
        if nodeName:
            index_entry.nodeName = nodeName

    search_engine.queue_document(index_entry)
    internal_links, external_links = extract_links(address, text)

    if update_citations:
        update_citations(doc.url, external_links)

    logging.getLogger("crawler").debug(
        "Extracted %s internal, %s external links from %s",
        len(internal_links),
        len(external_links),
        doc.url,
    )
    return internal_links + external_links


def crawl(
    get_node_by_address: Callable[[str], str],
    update_citations: Callable[[str, tp.List[str]], None],
):
    logger = logging.getLogger("crawl-scheduler")
    crawler = Crawler(
        load,
        lambda doc: extract(doc, get_node_by_address, update_citations),
        queue_maxsize=CONFIG.CRAWLER_QUEUE_MAXSIZE,
        visited_cache_seconds=CONFIG.CRAWLER_VISITED_CACHE_SECONDS,
    )
    recent_nodes = get_recent_nodes_for_crawl(within_seconds=CONFIG.CRAWLER_VISITED_CACHE_SECONDS)
    if not recent_nodes:
        logger.warning("No known nodes to crawl")
        return
    logger.info("starting crawl")
    for dst in recent_nodes:
        crawler.add_url(dst + ":/page/index.mu")
    logger.info("enqueued %s urls", len(recent_nodes))
    crawler.start(CONFIG.CRAWLER_THREADS)
    crawler.join()
    # Flush any remaining batched documents after crawl completion.
    search_engine.flush_index_queue()
