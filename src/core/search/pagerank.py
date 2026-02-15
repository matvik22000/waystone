# from __future__ import annotations
#
import logging
import time
from typing import Hashable, Iterable, Sequence

from sqlalchemy import bindparam, select, update

from src.core.data.db import get_session
from src.core.data.models import Citation, Node

_LOGGER = logging.getLogger(__name__)


def pagerank(batch_size: int = 500) -> dict[Hashable, float]:
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")

    with get_session() as session:
        edges = session.execute(
            select(Citation.src_address, Citation.target_address).where(
                Citation.removed.is_(False)
            )
        ).all()
        vertices = session.execute(
            select(Node.dst).where(Node.removed.is_(False))
        ).scalars().all()

    _LOGGER.info("started pagerank for %s edges; %s nodes", len(edges), len(vertices))
    ranks = pagerank_impl(edges, set(vertices))
    _LOGGER.info("pagerank finished")
    if not ranks:
        return ranks

    rows = [{"dst": dst, "rank": rank} for dst, rank in ranks.items()]
    stmt = (
        update(Node.__table__)
        .where(Node.__table__.c.dst == bindparam("dst_key"))
        .values(rank=bindparam("rank"))
    )
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i + batch_size]
        params = [{"dst_key": r["dst"], "rank": r["rank"]} for r in chunk]
        with get_session() as session:
            session.execute(stmt, params)

    _LOGGER.info("ranks updated")
    return ranks


def pagerank_impl(
        edges: Sequence[tuple[Hashable, Hashable]],
        vertices: Iterable[Hashable] | None = None,
        alpha: float = 0.15,  # teleport probability
        max_iters: int = 100,
        tol: float = 1e-10,
        personalize: dict[Hashable, float] | None = None,  # teleport distribution v
        sleep_config: tuple[int, float] = (5, 0.005),
) -> dict[Hashable, float]:
    """
    PageRank (power iteration) without external deps.

    MODEL (random surfer):
      - With probability (1 - alpha), follow an outgoing link uniformly at random.
      - With probability alpha, "teleport" according to distribution v.
    Dangling pages (outdeg=0):
      - If surfer is at a dangling page and wants to follow a link, there is no link.
      - Standard fix: treat it as a teleport (i.e., redistribute that probability mass by v).

    MATHEMATICS:
      Let r be the rank distribution (sum(r)=1).
      Let P be the transition matrix defined by outgoing links (row-stochastic for non-dangling rows).
      Then iteration is:

        r_new = (1 - alpha) * (r * P) + ((1 - alpha) * dangling_mass + alpha) * v

      where dangling_mass = sum(r[i] for pages with outdeg(i)=0)
            v is teleport distribution (sum(v)=1)

    WHY THIS FORM:
      - We avoid building an N×N matrix.
      - We only traverse existing edges each iteration: O(E).
      - Works for small graphs in pure Python; same structure scales if later replaced by CSR/Numba.

    INPUT:
      edges: list of (src, dst). Multiple identical edges are treated as one link by default.
      vertices: optional explicit list/set of vertices. If None, inferred from edges.
      personalize: optional teleport distribution v as dict {vertex: weight}.
                   If None, v is uniform over all vertices.
                   If provided, weights are normalized and missing vertices get 0.

    OUTPUT:
      dict {vertex: pagerank_score} where sum(scores)=1.0
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    if max_iters < 1:
        raise ValueError(f"max_iters must be >= 1, got {max_iters}")
    if tol <= 0.0:
        raise ValueError(f"tol must be > 0, got {tol}")
    if sleep_config[0] <= 0:
        raise ValueError(
            f"sleep_config[0] must be > 0, got {sleep_config[0]}"
        )
    if sleep_config[1] < 0.0:
        raise ValueError(
            f"sleep_config[1] must be >= 0, got {sleep_config[1]}"
        )

    # ------------------------------------------------------------------
    # 1) Collect vertices and map them to contiguous indices 0..N-1
    # ------------------------------------------------------------------
    if vertices is None:
        verts = set()
        for s, d in edges:
            verts.add(s)
            verts.add(d)
        vertices_list = list(verts)
    else:
        vertices_list = list(vertices)

    N = len(vertices_list)
    if N == 0:
        return {}

    idx_of = {v: i for i, v in enumerate(vertices_list)}
    vtx_of = vertices_list  # index -> vertex

    # ------------------------------------------------------------------
    # 2) Build adjacency lists (outgoing), and outdegree
    #    We deduplicate edges so outdeg isn't inflated by duplicates from DB.
    # ------------------------------------------------------------------
    out_neighbors: list[list[int]] = [[] for _ in range(N)]
    seen = set()
    for s, d in edges:
        if s not in idx_of or d not in idx_of:
            continue
        si = idx_of[s]
        di = idx_of[d]
        if (si, di) in seen:
            continue
        seen.add((si, di))
        out_neighbors[si].append(di)

    outdeg = [len(out_neighbors[i]) for i in range(N)]
    dangling = [i for i in range(N) if outdeg[i] == 0]

    # ------------------------------------------------------------------
    # 3) Build teleport distribution v (as a dense list length N)
    # ------------------------------------------------------------------
    if personalize is None:
        v = [1.0 / N] * N
    else:
        # normalize user-provided weights
        v = [0.0] * N
        total = 0.0
        for node, w in personalize.items():
            if node in idx_of and w > 0:
                v[idx_of[node]] += float(w)
                total += float(w)
        if total <= 0.0:
            # fallback to uniform if personalization is empty / all non-positive
            v = [1.0 / N] * N
        else:
            inv = 1.0 / total
            v = [x * inv for x in v]

    # ------------------------------------------------------------------
    # 4) Initialize rank vector r uniformly
    # ------------------------------------------------------------------
    r = [1.0 / N] * N

    # constant part for link-following
    one_minus_alpha = 1.0 - alpha

    # ------------------------------------------------------------------
    # 5) Power iteration
    # ------------------------------------------------------------------
    for it in range(max_iters):
        # do small interruptions during iterations, to prevent 100% cpu load
        if it % sleep_config[0] == 0:
            time.sleep(sleep_config[1])
        # (A) Start with zero; we'll accumulate incoming contributions.
        r_new = [0.0] * N

        # (B) Compute dangling mass: rank sitting on pages with no out-links.
        dangling_mass = 0.0
        for i in dangling:
            dangling_mass += r[i]

        # (C) Distribute rank through edges:
        #     For each node i with outlinks, spread (1-alpha)*r[i] equally among neighbors.
        for i in range(N):
            d = outdeg[i]
            if d == 0:
                continue
            share = one_minus_alpha * r[i] / d
            for j in out_neighbors[i]:
                r_new[j] += share

        # (D) Add teleport + dangling redistribution using v:
        #     teleport contributes alpha*v
        #     dangling contributes (1-alpha)*dangling_mass*v
        #     combine into a single coefficient times v
        coeff = alpha + one_minus_alpha * dangling_mass
        if coeff != 0.0:
            for j in range(N):
                r_new[j] += coeff * v[j]

        # (E) Normalize (guards against floating drift; also nice if graph weird)
        s = sum(r_new)
        if s != 0.0:
            inv_s = 1.0 / s
            for j in range(N):
                r_new[j] *= inv_s

        # (F) Convergence check: L1 distance between successive vectors
        diff = 0.0
        for j in range(N):
            diff += abs(r_new[j] - r[j])

        r = r_new
        if diff < tol:
            break

    # ------------------------------------------------------------------
    # 6) Convert back to {vertex: score * N}
    # ------------------------------------------------------------------
    return {vtx_of[i]: r[i] * len(vertices_list) for i in range(N)}
