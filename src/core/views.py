import datetime
import logging
import re
from typing import OrderedDict, Optional

from src.core.data.citations import citations
from src.api import NomadAPI
from src.api.app import Config
from src.api.exceptions import NotIdentified, BadRequest
from src.api.handlers import Request, render_template
from src.api.store import JsonFileStore
from src.config import CONFIG
from src.core.data import search_engine, get_path
from src.core.data import store
from src.core.data.store import find_owner
from src.core.rns import dst, identity
from src.core.utils import now

app = NomadAPI(Config(
    templates_dir=CONFIG.TEMPLATES_DIR,
    # enable_propagation_node=False,
    # propagation_node_identity=identity,
    # propagation_node_config=dict(storagepath=get_path("propagation"))
))
TIME_FORMAT = CONFIG.TIME_FORMAT
logger = logging.getLogger("views")

queries = JsonFileStore(get_path("queries.json"))


@app.request("/page/index.mu")
def index(r: Request):
    return render_template("index.mu", dict(
        pages=search_engine.get_index_size(),
        nodes=len(store.get("nodes", {})),
        links=len(dst.links),
        queries=get_last_10_queries(),
        now=now().strftime(TIME_FORMAT)
    ))


def get_last_10_queries():
    raw_queries = queries.get("queries", [])
    unique_queries = list(OrderedDict.fromkeys(reversed(raw_queries)))
    return unique_queries[:10]


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

    return ' '.join(parts)


@app.request("/page/nodes.mu")
def nodes_mu(r: Request, query: str = "", mentions_for: str = ""):
    nodes_raw = store.get("nodes", {})
    nodes_parsed = []
    items = []
    mentions_for_name = ""

    if mentions_for and query:
        raise Exception("mentioned_at and q mustn't be used together")
    if mentions_for:
        mentioned_at = citations.get_citations_for(mentions_for)
        mentions_for_name = nodes_raw.get(f"<{mentions_for}>").get("name")
        for dst, n in nodes_raw.items():
            if format_for_link(dst) in mentioned_at:
                items.append((dst, n))
    elif query:
        for dst, n in nodes_raw.items():
            if query in n["name"].lower() or query in n["dst"]:
                items.append((dst, n))
    else:
        items = nodes_raw.items()

    for dst, n in items:
        last_online = datetime.datetime.fromtimestamp(n["time"], tz=datetime.timezone.utc)
        nodes = dict(
            dst=format_for_link(dst),
            name=n["name"],
            ident=format_for_link(n["identity"]),
            owner=find_owner(n["identity"]) or ("Unknown", "Unknown"),
            citations=citations.get_amount_for(format_for_link(dst)),
            last_online=last_online.strftime(TIME_FORMAT),
            since_online=format_timedelta(since_online(last_online))
        )
        nodes_parsed.append(nodes)

    return render_template("nodes.mu", dict(
        mentions_for=mentions_for_name,
        query=query or "",
        now=now().strftime(TIME_FORMAT),
        nodes=sorted(nodes_parsed, key=lambda p: (p["citations"], p["last_online"]), reverse=True)
    ))


@app.request("/page/peers.mu")
def peers_mu(r: Request, query: str = ""):
    peers_raw = store.get("peers", {})
    peers_parsed = []
    items = []
    if query:
        for dst, p in peers_raw.items():
            if query in p["name"].lower() or query in p["dst"]:
                items.append((dst, p))
    else:
        items = peers_raw.items()

    for dst, p in items:
        last_online = datetime.datetime.fromtimestamp(p["time"], tz=datetime.timezone.utc)
        peer = dict(
            dst=format_for_link(dst),
            name=p["name"],
            last_online=last_online.strftime(TIME_FORMAT),
            since_online=format_timedelta(since_online(last_online))
        )
        peers_parsed.append(peer)
    return render_template("peers.mu", dict(
        query=query or "",
        now=now().strftime(TIME_FORMAT),
        peers=sorted(peers_parsed, key=lambda p: p["last_online"], reverse=True)
    ))


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
def search(r: Request, query: str):
    queries.set("queries", queries.get("queries", []) + [replace_line_breaks(query).strip()])

    entries = search_engine.query(query)
    nodes = store.get("nodes")
    for e in entries:
        e.text = format_text(e.text)
        node_info = nodes.get(f"<{e.address}>")
        if node_info:
            e.name = node_info["name"] + " " + e.url.split(":")[1]
        else:
            e.name = e.url

    try:
        hist = r.get_user_data([])
        hist.append(dict(q=query, time=now().timestamp()))
        r.save_user_data(hist)
    except NotIdentified:
        pass
    return render_template("search.mu",
                           dict(
                               entries=[e.to_dict() for e in entries],
                               total=len(entries),
                               query=replace_line_breaks(query).strip()
                           ))


@app.request("/page/history.mu", identifying_required=True)
def history(r: Request, page: int = 0):
    hist = list(reversed(r.get_user_data([])))
    page_size = 20
    hist_cut = hist[page * page_size:(page + 1) * page_size]
    return render_template("history.mu", dict(
        history=[dict(q=v["q"], time=datetime.datetime.fromtimestamp(v["time"], tz=datetime.timezone.utc)) for v in
                 hist_cut],
        total=len(hist_cut),
        page=page,
        has_next=(page + 1) * page_size < len(hist),
        has_prev=page != 0
    ))


@app.exception(NotIdentified)
def not_identified(exception):
    return render_template("not_identified.mu", dict())
