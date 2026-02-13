import datetime
import logging
import re

from src.core.data.citations import citations
from src.api import NomadAPI
from src.api.app import Config
from src.api.exceptions import NotIdentified, BadRequest
from src.api.handlers import Request, render_template
from src.config import CONFIG
from src.core.data import search_engine
from src.core.data.queries import add_search_query, get_last_search_queries
from src.core.data.store import (
    count_nodes_filtered,
    count_peers_filtered,
    count_nodes,
    find_node_by_address,
    find_owner,
    get_nodes_for_addresses,
    get_nodes_page,
    get_peers_page,
)
from src.core.rns import dst, identity
from src.core.utils import now

app = NomadAPI(
    Config(
        templates_dir=CONFIG.TEMPLATES_DIR,
        # enable_propagation_node=False,
        # propagation_node_identity=identity,
        # propagation_node_config=dict(storagepath=get_path("propagation"))
    )
)
TIME_FORMAT = CONFIG.TIME_FORMAT
DEFAULT_PAGE_SIZE = 20
logger = logging.getLogger("views")

@app.request("/page/index.mu")
def index(r: Request):
    return render_template(
        "index.mu",
        dict(
            pages=search_engine.get_index_size(),
            nodes=count_nodes(),
            links=len(dst.links),
            queries=get_last_10_queries(),
            now=now().strftime(TIME_FORMAT),
        ),
    )


def get_last_10_queries():
    return get_last_search_queries(limit=10)


def format_for_link(dst):
    return dst.replace("<", "").replace(">", "")


def since_online(t: datetime.datetime):
    return now() - t


def format_timedelta(td):
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def normalize_pagination(page: int, page_size: int) -> tuple[int, int]:
    return max(0, int(page)), max(1, int(page_size))


def calc_pages_total(total_items: int, page_size: int) -> int:
    return max(1, (total_items + page_size - 1) // page_size)


def get_page_bounds(page: int, page_size: int) -> tuple[int, int]:
    start = page * page_size
    return start, start + page_size


@app.request("/page/nodes.mu")
def nodes_mu(
    r: Request,
    query: str = "",
    mentions_for: str = "",
    page: int = 0,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    nodes_parsed = []
    items = []
    mentions_for_name = ""
    total_items = 0
    page, page_size = normalize_pagination(page, page_size)

    if mentions_for and query:
        raise Exception("mentioned_at and q mustn't be used together")
    if mentions_for:
        mentioned_at = citations.get_citations_for(mentions_for)
        mention_node = find_node_by_address(mentions_for)
        if mention_node:
            mentions_for_name = mention_node["name"]
        mention_nodes = get_nodes_for_addresses(mentioned_at)
        total_items = len(mention_nodes)
        start, end = get_page_bounds(page, page_size)
        for n in mention_nodes[start:end]:
            items.append((n["destination"], n))
    elif query:
        total_items = count_nodes_filtered(query=query)
        for n in get_nodes_page(page=page, page_size=page_size, query=query):
            items.append((n["destination"], n))
    else:
        total_items = count_nodes_filtered()
        for n in get_nodes_page(page=page, page_size=page_size):
            items.append((n["destination"], n))

    for dst, n in items:
        last_online = datetime.datetime.fromtimestamp(
            n["time"], tz=datetime.timezone.utc
        )
        nodes = dict(
            dst=format_for_link(dst),
            name=n["name"],
            ident=format_for_link(n["identity"]),
            owner=find_owner(n["identity"]) or ("Unknown", "Unknown"),
            citations=citations.get_amount_for(format_for_link(dst)),
            last_online=last_online.strftime(TIME_FORMAT),
            since_online=format_timedelta(since_online(last_online)),
        )
        nodes_parsed.append(nodes)

    return render_template(
        "nodes.mu",
        dict(
            location=r.path,
            location_params=(
                ("mentions_for=" + mentions_for + "|")
                if mentions_for
                else (("query=" + query + "|") if query else "")
            ),
            page=page,
            page_size=page_size,
            pages_total=calc_pages_total(total_items, page_size),
            mentions_for=mentions_for_name,
            query=query or "",
            now=now().strftime(TIME_FORMAT),
            nodes=sorted(
                nodes_parsed,
                key=lambda p: (p["citations"], p["last_online"]),
                reverse=True,
            ),
        ),
    )


@app.request("/page/peers.mu")
def peers_mu(
    r: Request, query: str = "", page: int = 0, page_size: int = DEFAULT_PAGE_SIZE
):
    page, page_size = normalize_pagination(page, page_size)
    peers_parsed = []
    total_items = count_peers_filtered(query=query)
    for p in get_peers_page(page=page, page_size=page_size, query=query):
        last_online = datetime.datetime.fromtimestamp(
            p["time"], tz=datetime.timezone.utc
        )
        peer = dict(
            dst=format_for_link(p["destination"]),
            name=p["name"],
            last_online=last_online.strftime(TIME_FORMAT),
            since_online=format_timedelta(since_online(last_online)),
        )
        peers_parsed.append(peer)
    return render_template(
        "peers.mu",
        dict(
            location=r.path,
            location_params=(("query=" + query + "|") if query else ""),
            page=page,
            page_size=page_size,
            pages_total=calc_pages_total(total_items, page_size),
            query=query or "",
            now=now().strftime(TIME_FORMAT),
            peers=sorted(peers_parsed, key=lambda p: p["last_online"], reverse=True),
        ),
    )


_re = re.compile("\s+")


def replace_line_breaks(text: str):
    text = text.replace("\n", " ")
    text = _re.sub(" ", text)
    return text


def remove_formatting(text: str):
    return text.replace("``", "")


def format_text(text: str) -> str:
    text = replace_line_breaks(text)
    text = remove_formatting(text)
    return text


@app.request("/page/search.mu")
def search(
    r: Request, query: str, page: int = 0, page_size: int = DEFAULT_PAGE_SIZE
):
    page, page_size = normalize_pagination(page, page_size)
    clean_query = replace_line_breaks(query).strip()
    if page == 0:
        add_search_query(clean_query)

    entries_all = search_engine.query(query, max_results=None)
    total_items = len(entries_all)
    start, end = get_page_bounds(page, page_size)
    entries = entries_all[start:end]
    for e in entries:
        e.text = format_text(e.text)
        node_info = find_node_by_address(e.address)
        if node_info:
            e.name = node_info["name"] + " " + e.url.split(":")[1]
        else:
            e.name = e.url

    try:
        hist = r.get_user_data([])
        hist.append(dict(q=clean_query, time=now().timestamp()))
        r.save_user_data(hist)
    except NotIdentified:
        pass
    return render_template(
        "search.mu",
        dict(
            location=r.path,
            location_params=("query=" + clean_query + "|"),
            page=page,
            page_size=page_size,
            pages_total=calc_pages_total(total_items, page_size),
            entries=[e.to_dict() for e in entries],
            total=total_items,
            query=clean_query,
        ),
    )


@app.request("/page/history.mu", identifying_required=True)
def history(r: Request, page: int = 0, page_size: int = DEFAULT_PAGE_SIZE):
    page, page_size = normalize_pagination(page, page_size)
    hist = list(reversed(r.get_user_data([])))
    start, end = get_page_bounds(page, page_size)
    hist_cut = hist[start:end]
    total_items = len(hist)
    return render_template(
        "history.mu",
        dict(
            location=r.path,
            location_params="",
            page_size=page_size,
            pages_total=calc_pages_total(total_items, page_size),
            history=[
                dict(
                    q=v["q"],
                    time=datetime.datetime.fromtimestamp(
                        v["time"], tz=datetime.timezone.utc
                    ),
                )
                for v in hist_cut
            ],
            total=total_items,
            page=page,
        ),
    )


@app.exception(NotIdentified)
def not_identified(exception):
    return render_template("not_identified.mu", dict())
