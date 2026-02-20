from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, isfinite
from pathlib import Path
from typing import Iterable, Optional, Tuple, Union, List
from scipy.stats import gamma  # type: ignore
from sqlalchemy import select

from src.config import CONFIG
from src.core.data.db import get_session
from src.core.data.models import Node

Number = Union[int, float]

PRIOR_DOWN = (4.006664496255316e-07, 2.7477094546713775e-05)  # alpha, beta or up/down formula
PRIOR_ANNOUNCE = (1.0, 60 * 30)  # by default, expecting 1 announce 30 minutes


@dataclass(frozen=True)
class SiteModelParams:
    alpha: float  # shape α
    beta: float  # rate  β  (НЕ scale!)
    window_seconds: float
    k_events: int


def _to_unix_seconds(t: Union[datetime, Number]) -> float:
    if isinstance(t, datetime):
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return t.timestamp()
    return float(t)


def fit_site_params(
        heard_announces: List[Union[datetime, Number]],
        window_seconds: float = None
) -> SiteModelParams:
    times = sorted([_to_unix_seconds(t) for t in heard_announces])

    k = sum(1 for _ in times)

    # posterior: μ|K ~ Gamma(a+K, b+T)
    alpha = float(PRIOR_ANNOUNCE[0]) + int(k)
    beta = float(PRIOR_ANNOUNCE[1]) + float(window_seconds)

    if alpha <= 0 or beta <= 0 or not isfinite(alpha) or not isfinite(beta):
        raise ValueError(f"Bad posterior params: alpha={alpha}, beta={beta}")

    return SiteModelParams(
        alpha=alpha,
        beta=beta,
        window_seconds=float(window_seconds) if window_seconds else (times[-1] - times[0]),
        k_events=int(k)
    )


# --- Gamma quantile (ppf) helpers -------------------------------------------------
def gamma_ppf(p: float, alpha: float, beta: float) -> float:
    return float(gamma.ppf(p, a=alpha, scale=1.0 / beta))


# --- Part (2): CI for P(dead) ----------------------------------------------------
def dead_probability_ci(
        alpha: float,
        beta: float,
        dt_seconds: float,
        *,
        ci: float = 0.90,
) -> Tuple[float, float]:
    dt = float(dt_seconds)
    if dt < 0:
        raise ValueError("dt_seconds must be >= 0")
    if not (0.0 < ci < 1.0):
        raise ValueError("ci must be in (0,1)")

    # 2-sided interval
    q_lo = (1.0 - ci) / 2.0
    q_hi = 1.0 - q_lo

    mu_low = gamma_ppf(q_lo, float(alpha), float(beta))
    mu_high = gamma_ppf(q_hi, float(alpha), float(beta))

    # Safety (numerics)
    mu_low = max(0.0, float(mu_low))
    mu_high = max(mu_low, float(mu_high))

    # P0 bounds
    p0_high = exp(-mu_low * dt)
    p0_low = exp(-mu_high * dt)

    # prior death probability π(dt)
    pi = pi_down(dt)

    def p_dead_from_p0(p0: float) -> float:
        # P_dead = π / (π + (1-π) P0)
        denom = pi + (1.0 - pi) * p0
        # denom > 0 always
        return pi / denom

    pdead_low = p_dead_from_p0(p0_high)
    pdead_high = p_dead_from_p0(p0_low)

    # clamp just in case
    pdead_low = min(max(pdead_low, 0.0), 1.0)
    pdead_high = min(max(pdead_high, 0.0), 1.0)

    # ensure ordering
    if pdead_low > pdead_high:
        pdead_low, pdead_high = pdead_high, pdead_low

    return pdead_low, pdead_high


def pi_down(dt_seconds: float):
    dt = float(dt_seconds)
    a = PRIOR_DOWN[0]
    b = PRIOR_DOWN[1]
    s = a + b
    if s <= 0 or dt <= 0:
        return 0.0
    return (a / s) * (1.0 - exp(-s * dt))


def _nomad_announce_log_dir() -> Path:
    return Path(CONFIG.LOG_PATH) / "announces"


def _load_recent_nomad_node_announces(
        lookback_days: int,
) -> tuple[dict[str, list[float]], float | None]:
    since_ts = datetime.now(timezone.utc).timestamp() - max(1, int(lookback_days)) * 24 * 60 * 60
    log_dir = _nomad_announce_log_dir()
    announces: dict[str, list[float]] = {}
    earliest_ts: float | None = None
    if not log_dir.exists():
        return announces, earliest_ts
    for log_path in sorted(log_dir.glob("nomadnetwork.node.log*")):
        if not log_path.is_file():
            continue
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                dst = str(payload.get("dst", "")).strip()
                ts_raw = payload.get("datetime")
                if not dst or not ts_raw:
                    continue
                try:
                    ts = datetime.fromisoformat(str(ts_raw)).replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    continue
                if earliest_ts is None or ts < earliest_ts:
                    earliest_ts = ts
                if ts < since_ts:
                    continue
                announces.setdefault(dst, []).append(ts)
    return announces, earliest_ts


def recalc_node_survival_params(lookback_days: int) -> int:
    announces, earliest_ts = _load_recent_nomad_node_announces(lookback_days=lookback_days)
    now_ts = datetime.now(timezone.utc).timestamp()
    max_window_seconds = max(1, int(lookback_days)) * 24 * 60 * 60
    if earliest_ts is None:
        lookback_seconds = 0
    else:
        lookback_seconds = max(0, min(max_window_seconds, int(now_ts - earliest_ts)))
    updated = 0
    with get_session() as session:
        rows = session.execute(select(Node).where(Node.removed.is_(False))).scalars().all()
        for row in rows:
            params = fit_site_params(sorted(announces.get(row.dst, [])), lookback_seconds)

            row.announce_alpha = params.alpha
            row.announce_beta = params.beta
            row.announce_window_seconds = params.window_seconds
            row.announce_k_events = params.k_events

            updated += 1
    return updated


# --- Example usage ---------------------------------------------------------------
if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    amount = 200
    heard = [now.timestamp() - i * (14 * 24 * 3600 / amount) for i in range(amount)]
    print(*[i * (14 * 24 * 3600 / amount) for i in range(amount)])

    params = fit_site_params(heard)

    dt = 12 * 3600

    lo, hi = dead_probability_ci(params.alpha, params.beta, dt, ci=0.90)
    print("90% CI for P(dead):", (lo, hi))
