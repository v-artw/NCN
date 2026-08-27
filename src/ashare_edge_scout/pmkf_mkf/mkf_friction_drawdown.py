"""Friction + per-position drawdown study on the MKF post-cross target grid.

This study builds on the already-validated target grid panel
(``build_mkf_post_cross_lag_target_grid_panel``) and adds two layers that the
previous grids intentionally omitted:

* realistic A-share trading frictions per trade, at a fixed 3-lot (300 share)
  position size; and
* per-position (single 3-lot trade) drawdown, marked to daily closes.

It produces, for every ``(lag, T+n, target_pct)`` cell, an in-sample *net
return* (post friction) and an average / maximum single-position drawdown, and
ranks cells by ``net_return - drawdown`` (a 1:1 risk penalty).

This is descriptive, in-sample research evidence. It is NOT executable P&L and
does not change any production selector, watchlist, AI default, or broker path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .mkf_post_cross_lag_comparison import (
    GRID_HORIZONS,
    GRID_TARGET_PCTS,
    LAGS,
    build_mkf_post_cross_lag_target_grid_panel,
)

# --- Friction model: A-share standard three fees, commission with a 5 CNY floor.
SHARES_PER_TRADE = 300  # 3 手 = 300 shares (1 手 = 100 shares)
COMMISSION_RATE = 0.00025  # 佣金 万2.5
COMMISSION_FLOOR = 5.0  # CNY, minimum commission per side
TRANSFER_RATE = 0.00001  # 过户费 万0.1, both buy and sell
STAMP_RATE = 0.0005  # 印花税 0.05%, sell side only (halved Aug-2023)

GRID_SCHEMA_VERSION = "ncn_mkf_post_cross_lag_friction_drawdown_v1"

# horizon/target grids this study reuses from the parent grid
STUDY_HORIZONS = tuple(range(1, 21))
STUDY_TARGET_PCTS = tuple(range(1, 21))

# Pre-registered stability gate: a cell may be named a "best point" candidate only
# if it passes every gate below. Numbers are frozen before any grid run and must not
# be relaxed afterwards merely to produce a positive result. Mirrors the parent grid's
# sample/codewide/date coverage gates, which are required here too because the per-cell
# returns are small and otherwise dominated by tiny-n (single-stock) noise cells.
STABILITY_GATE_CONFIG = {
    "min_n": 300,
    "min_entry_dates": 120,
    "min_codes": 50,
}


def _buy_fee_per_share(entry_open: np.ndarray) -> np.ndarray:
    """Per-share buy cost: max(turnover*rate, floor)/shares + transfer fee."""
    commission_ps = np.maximum(entry_open * COMMISSION_RATE, COMMISSION_FLOOR / SHARES_PER_TRADE)
    return commission_ps + entry_open * TRANSFER_RATE


def _sell_fee_per_share(exit_price: np.ndarray) -> np.ndarray:
    """Per-share sell cost: floor commission + stamp duty + transfer fee."""
    commission_ps = np.maximum(exit_price * COMMISSION_RATE, COMMISSION_FLOOR / SHARES_PER_TRADE)
    return commission_ps + exit_price * STAMP_RATE + exit_price * TRANSFER_RATE


def _position_drawdown_and_return(
    *,
    entry_open: np.ndarray,
    closes: np.ndarray,
    highs: np.ndarray,
    target_pct: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For a batch of positions return (net_return, drawdown_magnitude, hit) per position.

    ``closes`` / ``highs`` are ``(P, horizon)`` arrays of daily closes/highs after entry.
    ``entry_open`` is ``(P,)``. A position hits when the running max high reaches the
    target price; then it is sold at the target price on the first such day. Otherwise it
    is sold at the horizon close. Drawdown is the peak-to-trough of the per-share equity
    curve marked to daily closes (day 0 = invested base).
    """
    entry_open = np.asarray(entry_open, dtype=float)
    closes = np.asarray(closes, dtype=float)
    highs = np.asarray(highs, dtype=float)
    positions = closes.shape[0]

    target_return = float(target_pct) / 100.0
    threshold = entry_open * (1.0 + target_return)

    # Hit if the running max high reaches the target anywhere in the window. Note
    # argmax over an all-False boolean returns 0, so the hit mask must come from the
    # true max rather than from the crossing index.
    hit = np.max(highs, axis=1) >= threshold
    crossing = np.argmax(highs >= threshold[:, None], axis=1)
    crossing_days = np.where(hit, crossing + 1, horizon)  # exit day, 1-based
    close_at_horizon = closes[:, -1]
    # Exit price: target price on a hit, otherwise the horizon close.
    exit_price = np.where(hit, threshold, close_at_horizon)

    invested_base = entry_open + _buy_fee_per_share(entry_open)
    final_per_share = exit_price - _sell_fee_per_share(exit_price)

    # Equity curve: day0 = invested base; day k (1..horizon) = close, replaced by the
    # net sell value from the exit day onward (the position is sold on the exit day, so
    # its mark is the proceeds that day and flat after). Flat postsale marks do not
    # change the peak-to-trough drawdown past the sale.
    day_index = np.arange(1, horizon + 1)
    post_sale = day_index[None, :] >= crossing_days[:, None]
    marks = np.where(post_sale, final_per_share[:, None], closes)
    equity = np.concatenate([invested_base[:, None], marks], axis=1)
    running_peak = np.maximum.accumulate(equity, axis=1)
    drawdown = (equity - running_peak) / running_peak
    drawdown_magnitude = -drawdown.min(axis=1)  # positive fraction

    return final_per_share / invested_base - 1.0, drawdown_magnitude, hit


def _lag_batch(
    panel: pd.DataFrame,
    lag: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.Series, pd.Series] | None:
    """Return (entry_open, closes, highs, entry_date, cross_date) for one lag, or None."""
    rows = panel.loc[pd.to_numeric(panel.get("post_cross_lag"), errors="coerce").eq(lag)]
    if rows.empty:
        return None
    entry = pd.to_numeric(rows.get("entry_open"), errors="coerce").to_numpy(dtype=float)
    entry_date = pd.to_datetime(rows.get("entry_date"), errors="coerce")
    valid = entry > 0 & entry_date.notna()
    entry = entry[valid]
    entry_date = entry_date[valid]
    closes = rows.loc[valid, [f"future_close_t{k}" for k in range(1, STUDY_HORIZONS[-1] + 1)]].to_numpy(dtype=float)
    highs = rows.loc[valid, [f"future_high_t{k}" for k in range(1, STUDY_HORIZONS[-1] + 1)]].to_numpy(dtype=float)
    return entry, closes, highs, entry_date, rows.loc[valid, "cross_date"]


def compute_stock_friction_drawdown(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
    lags: tuple[int, ...] = LAGS,
    horizon_limits: tuple[int, ...] = STUDY_HORIZONS,
) -> dict[str, Any]:
    """Compute per-cell net return + drawdown for one stock's panel.

    Returns three things:
    * ``cells``: per ``(lag, horizon, target_pct)`` partial sums (n, hits, return/dd sums).
    * ``codes``: per ``(lag, horizon)`` count of contributing stocks (always 1 per stock
      here, summed across stocks -> distinct-code count for the stability gate).
    * ``entry_dates``: per ``(lag, horizon)`` set of distinct entry dates contributed.
    """
    panel = build_mkf_post_cross_lag_target_grid_panel(
        code,
        frame,
        config,
        start_date=start_date,
        end_date=end_date,
        lags=lags,
        horizons=STUDY_HORIZONS,
        include_future_close=True,
    )

    cell_stats: dict[tuple[int, int, int], dict[str, Any]] = {}
    codes: dict[tuple[int, int], int] = {}
    entry_dates: dict[tuple[int, int], set] = {}
    for lag in lags:
        batch = _lag_batch(panel, lag)
        if batch is None:
            continue
        entry, closes, highs, entry_date, cross_date = batch
        closes = np.where(np.isfinite(closes), closes, np.nan)
        highs = np.where(np.isfinite(highs), highs, np.nan)

        for horizon in horizon_limits:
            # A position contributes to this horizon only if its full close/high path exists.
            finite = np.ones(len(entry), dtype=bool)
            for k in range(horizon):
                finite &= np.isfinite(closes[:, k]) & np.isfinite(highs[:, k])
            if not finite.any():
                continue
            e = entry[finite]
            c = closes[finite, :horizon]
            h = highs[finite, :horizon]

            codes[(lag, horizon)] = codes.get((lag, horizon), 0) + 1
            entry_dates.setdefault((lag, horizon), set()).update(entry_date[finite].tolist())

            for target_pct in STUDY_TARGET_PCTS:
                target_return = float(target_pct) / 100.0
                # The exact hit mask / net return / drawdown machinery lives in the
                # shared per-position helper so hit and risk are computed consistently.
                net_return, drawdown_mag, hit = _position_drawdown_and_return(
                    entry_open=e, closes=c, highs=h, target_pct=target_pct, horizon=horizon
                )
                n = int(hit.size)
                hits = int(hit.sum())
                cell_stats[(lag, horizon, target_pct)] = {
                    "n": n,
                    "hits": hits,
                    "sum_net_return": float(np.sum(net_return)),
                    "sum_net_return_sq": float(np.sum(net_return ** 2)),
                    "sum_drawdown": float(np.sum(drawdown_mag)),
                    "sum_drawdown_sq": float(np.sum(drawdown_mag ** 2)),
                    "max_drawdown": float(np.max(drawdown_mag)),
                }

    return {"cells": cell_stats, "codes": codes, "entry_dates": entry_dates}


def aggregate_cell_stats(
    per_stock: Mapping[tuple[int, int, int], Mapping[str, Any]],
) -> dict[tuple[int, int, int], Mapping[str, Any]]:
    """Combine per-stock partial sums into population-level cell metrics.

    Returns, for each ``(lag, horizon, target_pct)`` cell: total ``n``, ``hits``,
    ``hit_rate``, weighted ``mean_net_return``, weighted ``mean_drawdown``, and the
    maximum observed single-position ``max_drawdown`` (max of per-stock maxima).
    """
    combined: dict[tuple[int, int, int], dict[str, Any]] = {}
    for key, partial in per_stock.items():
        acc = combined.get(key)
        if acc is None:
            combined[key] = {
                "n": 0,
                "hits": 0,
                "sum_net_return": 0.0,
                "sum_drawdown": 0.0,
                "max_drawdown": 0.0,
            }
            acc = combined[key]
        acc["n"] += int(partial.get("n") or 0)
        acc["hits"] += int(partial.get("hits") or 0)
        acc["sum_net_return"] += float(partial.get("sum_net_return") or 0.0)
        acc["sum_drawdown"] += float(partial.get("sum_drawdown") or 0.0)
        acc["max_drawdown"] = max(acc["max_drawdown"], float(partial.get("max_drawdown") or 0.0))
    for cell, acc in combined.items():
        total = acc["n"]
        if total <= 0:
            acc["mean_net_return"] = None
            acc["mean_drawdown"] = None
            acc["hit_rate"] = 0.0
        else:
            acc["mean_net_return"] = acc["sum_net_return"] / total
            acc["mean_drawdown"] = acc["sum_drawdown"] / total
            acc["hit_rate"] = acc["hits"] / total
    return combined


def _score_cell(stats: Mapping[str, Any]) -> dict[str, Any]:
    """Attach the 1:1 net-return-minus-drawdown score to an aggregated cell."""
    mean_net_return = stats.get("mean_net_return")
    mean_drawdown = stats.get("mean_drawdown")
    if mean_net_return is None or mean_drawdown is None:
        score = None
    else:
        score = mean_net_return - mean_drawdown
    return {
        "lag": stats["lag"],
        "horizon": stats["horizon"],
        "target_pct": stats["target_pct"],
        "n": stats["n"],
        "hit_rate": stats["hit_rate"],
        "mean_net_return": mean_net_return,
        "mean_drawdown": mean_drawdown,
        "max_drawdown": stats.get("max_drawdown"),
        "score": score,
    }


def _lag_horizon_gate(
    per_stock: Mapping[tuple[int, int, int], Mapping[str, Any]],
    codes: Mapping[tuple[int, int], int],
    entry_dates: Mapping[tuple[int, int], set],
    lag: int,
    horizon: int,
    *,
    gate: Mapping[str, Any],
) -> bool:
    """Whether the ``(lag, horizon)`` cohort clears the stability gate.

    Uses the per-cell ``n`` (identical across targets for a fixed horizon), the
    distinct-code count, and the distinct-entry-date count.
    """
    combined = aggregate_cell_stats(per_stock)
    n = max(
        (combined[(lag, horizon, t)]["n"] for t in STUDY_TARGET_PCTS if (lag, horizon, t) in combined),
        default=0,
    )
    min_n = int(gate.get("min_n", 0))
    min_codes = int(gate.get("min_codes", 0))
    min_dates = int(gate.get("min_entry_dates", 0))
    return (
        n >= min_n
        and min_codes <= int(codes.get((lag, horizon), 0))
        and min_dates <= len(entry_dates.get((lag, horizon), set()))
    )


def aggregate_and_score(
    per_stock: Mapping[tuple[int, int, int], Mapping[str, Any]],
    *,
    codes: Mapping[tuple[int, int], int],
    entry_dates: Mapping[tuple[int, int], set],
    horizon_limits: tuple[int, ...] = STUDY_HORIZONS,
    lags: tuple[int, ...] = LAGS,
    gate: Mapping[str, Any] = STABILITY_GATE_CONFIG,
) -> dict[str, Any]:
    """Aggregate per-stock partial sums into scored, gated, sorted cells.

    Returns a dict with:
    * ``scored``: gated cells ranked by net-return-minus-mean drawdown (the 1:1 penalty).
    * ``scored_by_net_return``: same gated set, ranked by pure post-fee return.
    * ``scored_by_drawdown``: same gated set, ranked by least drawdown.
    * ``n_cells`` / ``n_gated`` counts.
    """
    combined = aggregate_cell_stats(per_stock)
    all_cells = [
        (lag, horizon, target_pct)
        for lag in lags
        for horizon in horizon_limits
        for target_pct in STUDY_TARGET_PCTS
    ]
    gated = [
        cell
        for cell in all_cells
        if cell in combined and _lag_horizon_gate(per_stock, codes, entry_dates, cell[0], cell[1], gate=gate)
    ]
    score_rows = [
        _score_cell({**combined[cell], "lag": cell[0], "horizon": cell[1], "target_pct": cell[2]})
        for cell in gated
    ]
    score_rows.sort(key=lambda row: (row["score"] if row["score"] is not None else -1.0), reverse=True)
    net_rows = sorted(score_rows, key=lambda row: (row["mean_net_return"] if row["mean_net_return"] is not None else -1.0), reverse=True)
    dd_rows = sorted(score_rows, key=lambda row: (row["mean_drawdown"] if row["mean_drawdown"] is not None else 1.0))
    return {
        "scored": score_rows,
        "scored_by_net_return": net_rows,
        "scored_by_drawdown": dd_rows,
        "n_cells": len(all_cells),
        "n_gated": len(gated),
    }


def build_report(
    per_stock: Mapping[tuple[int, int, int], Mapping[str, Any]],
    *,
    codes: Mapping[tuple[int, int], int],
    entry_dates: Mapping[tuple[int, int], set],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
    horizon_limits: tuple[int, ...] = STUDY_HORIZONS,
    lags: tuple[int, ...] = LAGS,
) -> dict[str, Any]:
    """Combine per-stock partial sums into a gated, ranked readout of optimal cells."""
    res = aggregate_and_score(
        per_stock,
        codes=codes,
        entry_dates=entry_dates,
        horizon_limits=horizon_limits,
        lags=lags,
    )
    score_rows = res["scored"]
    net_rows = res["scored_by_net_return"]
    dd_rows = res["scored_by_drawdown"]
    best = score_rows[0] if score_rows else {
        "lag": None,
        "horizon": None,
        "target_pct": None,
        "mean_net_return": None,
        "mean_drawdown": None,
        "score": None,
    }
    best_by_net = net_rows[0] if net_rows else best
    best_by_dd = dd_rows[0] if dd_rows else best
    return {
        "schema_version": GRID_SCHEMA_VERSION,
        "study": "mkf_post_cross_lag_friction_drawdown",
        "research_only": True,
        "production_enabled": False,
        "code_list_sha256": code_list_sha256,
        "start_date": start_date,
        "end_date": end_date,
        "workers": workers,
        "friction": {
            "shares_per_trade": SHARES_PER_TRADE,
            "commission_rate": COMMISSION_RATE,
            "commission_floor_cny": COMMISSION_FLOOR,
            "transfer_rate": TRANSFER_RATE,
            "stamp_rate": STAMP_RATE,
        },
        "gating": {
            "stability_gate": dict(STABILITY_GATE_CONFIG),
            "n_total_cells": res["n_cells"],
            "n_gated_cells": res["n_gated"],
        },
        "ranking": "net_return - mean_drawdown (1:1 risk penalty)",
        "best_cell": best,
        "best_by_net_return": best_by_net,
        "best_by_drawdown": best_by_dd,
        "scored": score_rows,
        "scored_by_net_return": net_rows,
        "scored_by_drawdown": dd_rows,
    }
