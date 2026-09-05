#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from itertools import product
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ashare_edge_scout.ai_providers import build_ai_client as build_shared_ai_client, load_ai_provider_config
from ashare_edge_scout.config import compute_config_sha256, load_config, validate_config
from ashare_edge_scout.mkf_ai_review import (
    OpenAICompatibleClient,
    _local_score,
    _mkf_technical_context,
)
from ashare_edge_scout.mkf_news_context import NO_NEWS_TEXT
from ashare_edge_scout.pmkf_mkf.candidates import (
    MkfCandidateRow,
    _cross_components,
    _latest_cross_context,
    mkf_allowed_lags,
    mkf_selection_rule,
)
from ashare_edge_scout.pmkf_mkf.quality import normalise_stock_frame
from ashare_edge_scout.pmkf_mkf.research import mkf_red_blue_cross20_lines, mkf_red_blue_cross20_post_lag_mask
from ashare_edge_scout.research_precision70 import production_gate_mask
from ashare_edge_scout.stock_selector import _safe_float

SCHEMA_VERSION = "ncn_mkf_ai_score_rotation_backtest_v1"
DETERMINISTIC_LANE = "deterministic_local_score_x10"
TS_LLM_LANE = "ts_local_finance_llm_no_news"
POSITIVE_AI_STATES = {"priority_research", "standard_research"}
NEGATIVE_AI_SCORE = 50.0
_SIM_WORKER_CONTEXT: dict[str, Any] = {}


@dataclass(frozen=True)
class ScoreRecord:
    date: str
    code: str
    lane: str
    score: float
    review_state: str
    confidence: float
    local_score: float
    is_buy_candidate: bool
    components: Mapping[str, Any]
    next_open_date: str | None
    next_open_price: float | None


@dataclass
class Position:
    code: str
    shares: int
    entry_date: str
    entry_price: float
    entry_score: float
    cost_basis: float


@dataclass(frozen=True)
class PendingOrder:
    decision_date: str
    side: str
    code: str
    reason: str
    score_at_decision: float
    replacement_gap: float
    replace_code: str | None = None


@dataclass
class ComboState:
    combo_id: str
    lane: str
    max_positions: int
    replacement_gap: float
    cost_mode: str
    entry_threshold: float
    hold_threshold: float
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    pending_orders: list[PendingOrder] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    daily: list[dict[str, Any]] = field(default_factory=list)
    counters: Counter[str] = field(default_factory=Counter)
    peak_equity: float = 0.0
    cost_paid: float = 0.0


def _parse_csv_values(value: str, cast: Any = str) -> list[Any]:
    return [cast(item.strip()) for item in value.split(",") if item.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()[:10] if not isinstance(value, datetime) else value.isoformat()
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def _write_csv(path: Path, rows: list[Mapping[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, float):
        return round(value, 8) if math.isfinite(value) else ""
    if value is None:
        return ""
    return value


def ashare_fees(gross: float, side: str, cost_mode: str) -> float:
    if cost_mode == "none" or gross <= 0:
        return 0.0
    commission = max(gross * 0.00025, 5.0)
    transfer = gross * 0.00001
    stamp = gross * 0.0005 if side == "sell" else 0.0
    return commission + transfer + stamp


def llm_score_from_state(review_state: str, confidence: float) -> float:
    if review_state in POSITIVE_AI_STATES:
        return round(max(0.0, min(100.0, confidence * 100.0)), 4)
    return NEGATIVE_AI_SCORE


def next_tradable_open(frame: pd.DataFrame, as_of: str) -> tuple[str | None, float | None]:
    data = normalise_stock_frame(frame)
    dates = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string").eq("1").fillna(False)
    open_ = pd.to_numeric(data.get("open"), errors="coerce")
    after = dates.gt(pd.Timestamp(as_of)) & trade & open_.gt(0) & open_.notna()
    if not bool(after.any()):
        return None, None
    index = int(after.idxmax())
    return dates.loc[index].date().isoformat(), float(open_.loc[index])


def _candidate_from_frame(code: str, data: pd.DataFrame, config: Mapping[str, Any], as_of: str, source_path: Path, allowed_lags: frozenset[int]) -> MkfCandidateRow | None:
    signal_day = pd.Timestamp(as_of)
    current = data.loc[data["date"].le(signal_day)].copy().reset_index(drop=True)
    if current.empty or current.iloc[-1]["date"] != signal_day:
        return None
    row_index = int(current.index[-1])
    admitted = production_gate_mask(code, current, config).reindex(current.index, fill_value=False).astype(bool)
    if not bool(admitted.loc[row_index]):
        return None
    signal = mkf_red_blue_cross20_post_lag_mask(current, allowed_lags=allowed_lags).reindex(current.index, fill_value=False).astype(bool)
    if not bool(signal.loc[row_index]):
        return None
    cross_context = _latest_cross_context(current, row_index, allowed_lags)
    if cross_context is None:
        return None
    cross_index, lag = cross_context
    lines = mkf_red_blue_cross20_lines(current)
    line = lines.loc[row_index]
    red_cross, blue_cross = _cross_components(lines, current, cross_index)
    latest = current.loc[row_index]
    cross_row = current.loc[cross_index]
    return MkfCandidateRow(
        code=code,
        signal_date=as_of,
        cross_date=pd.Timestamp(cross_row["date"]).date().isoformat(),
        post_cross_lag=int(lag),
        research_close=_safe_float(latest.get("close"), 0.0),
        amount_cny=_safe_float(latest.get("amount"), 0.0),
        turn_pct=_safe_float(latest.get("turn"), 0.0),
        mkf_momentum=_safe_float(line.get("momentum"), 0.0),
        mkf_inter=_safe_float(line.get("inter"), 0.0),
        mkf_near=_safe_float(line.get("near"), 0.0),
        mkf_red_cross_up_20=red_cross,
        mkf_blue_cross_up_20=blue_cross,
        mkf_red_blue_cross_up_20_under_80=True,
        source_path=str(source_path),
        selection_reason=mkf_selection_rule(allowed_lags),
    )


def _holding_candidate(code: str, data: pd.DataFrame, config: Mapping[str, Any], as_of: str, source_path: Path) -> MkfCandidateRow | None:
    signal_day = pd.Timestamp(as_of)
    current = data.loc[data["date"].le(signal_day)].copy().reset_index(drop=True)
    if current.empty or current.iloc[-1]["date"] != signal_day:
        return None
    row_index = int(current.index[-1])
    gate = production_gate_mask(code, current, config).reindex(current.index, fill_value=False).astype(bool)
    lines = mkf_red_blue_cross20_lines(current)
    line = lines.loc[row_index]
    latest = current.loc[row_index]
    return MkfCandidateRow(
        code=code,
        signal_date=as_of,
        cross_date=as_of,
        post_cross_lag=-1,
        research_close=_safe_float(latest.get("close"), 0.0),
        amount_cny=_safe_float(latest.get("amount"), 0.0),
        turn_pct=_safe_float(latest.get("turn"), 0.0),
        mkf_momentum=_safe_float(line.get("momentum"), 0.0),
        mkf_inter=_safe_float(line.get("inter"), 0.0),
        mkf_near=_safe_float(line.get("near"), 0.0),
        mkf_red_cross_up_20=False,
        mkf_blue_cross_up_20=False,
        mkf_red_blue_cross_up_20_under_80=bool(gate.loc[row_index]),
        source_path=str(source_path),
        selection_reason="holding_daily_rescore_without_new_candidate_requirement",
    )


def _disabled_news_context() -> dict[str, Any]:
    return {
        "status": "disabled",
        "cache_status": "disabled",
        "news_txt": NO_NEWS_TEXT,
        "fatal_risks": [],
        "attn_risks": [],
        "public_config": {"ENABLED": False},
    }


def _score_record(
    *,
    candidate: MkfCandidateRow,
    lane: str,
    data_root: Path,
    config: Mapping[str, Any],
    client: OpenAICompatibleClient | None,
    next_open: tuple[str | None, float | None],
    llm_cache: dict[tuple[str, str], dict[str, Any]],
    is_buy_candidate: bool,
) -> ScoreRecord:
    candidate_dict = asdict(candidate)
    context = _mkf_technical_context(candidate_dict, data_root, config)
    local_score, observations, risks = _local_score(candidate_dict, context)
    components: dict[str, Any] = {
        "local_score": local_score,
        "technical_context_status": context.get("status"),
        "observations": list(observations),
        "risks": list(risks),
        "news_context_used": False,
        "archived_ai_review_used": False,
    }
    review_state = "local_score_baseline"
    confidence = round(local_score / 10.0, 4)
    score = round(local_score * 10.0, 4)
    if lane == TS_LLM_LANE:
        key = (candidate.code, candidate.signal_date)
        if key not in llm_cache:
            if client is None:
                llm_cache[key] = {"review_state": "ai_unavailable", "confidence": 0.0, "error": "client_unavailable"}
            else:
                try:
                    ai_result, model = client.analyze(candidate_dict, context, _disabled_news_context())
                    llm_cache[key] = {**ai_result, "model": model}
                except Exception as exc:
                    llm_cache[key] = {"review_state": "ai_unavailable", "confidence": 0.0, "error": f"{type(exc).__name__}:{exc}"}
        result = llm_cache[key]
        review_state = str(result.get("review_state") or "ai_unavailable")
        confidence = float(result.get("confidence") or 0.0)
        score = llm_score_from_state(review_state, confidence)
        components.update({
            "llm_review_state": review_state,
            "llm_confidence": confidence,
            "model": result.get("model"),
            "llm_error": result.get("error"),
            "score_mapping": "positive_state_confidence_x100_else_50",
        })
    return ScoreRecord(
        date=candidate.signal_date,
        code=candidate.code,
        lane=lane,
        score=score,
        review_state=review_state,
        confidence=confidence,
        local_score=local_score,
        is_buy_candidate=is_buy_candidate,
        components=_json_safe(components),
        next_open_date=next_open[0],
        next_open_price=next_open[1],
    )


def _candidate_cache_for_code(
    *,
    code: str,
    data: pd.DataFrame,
    source_path: Path,
    config: Mapping[str, Any],
    data_root: Path,
    dates: list[str],
    allowed_lags: frozenset[int],
) -> list[tuple[str, MkfCandidateRow, tuple[str | None, float | None], float]]:
    rows: list[tuple[str, MkfCandidateRow, tuple[str | None, float | None], float]] = []
    date_set = set(pd.to_datetime(data["date"], errors="coerce").dt.date.astype(str))
    for as_of in dates:
        if as_of not in date_set:
            continue
        candidate = _candidate_from_frame(code, data, config, as_of, source_path, allowed_lags)
        if candidate is None:
            continue
        context = _mkf_technical_context(asdict(candidate), data_root, config)
        local_score, _, _ = _local_score(asdict(candidate), context)
        rows.append((as_of, candidate, next_tradable_open(data, as_of), local_score))
    return rows


def build_daily_scores(
    *,
    frames: dict[str, pd.DataFrame],
    source_paths: dict[str, Path],
    config: Mapping[str, Any],
    data_root: Path,
    dates: list[str],
    lanes: list[str],
    client: OpenAICompatibleClient | None,
    progress_every: int,
    llm_top_per_day: int,
    workers: int,
) -> tuple[dict[str, dict[str, dict[str, ScoreRecord]]], list[dict[str, Any]], Counter[str]]:
    allowed_lags = mkf_allowed_lags(config)
    by_lane_date: dict[str, dict[str, dict[str, ScoreRecord]]] = {lane: defaultdict(dict) for lane in lanes}
    score_rows: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    llm_cache: dict[tuple[str, str], dict[str, Any]] = {}
    all_codes = sorted(frames)
    candidate_cache: dict[str, list[tuple[MkfCandidateRow, tuple[str | None, float | None], float]]] = defaultdict(list)
    worker_count = max(1, int(workers))
    completed = 0
    if worker_count == 1:
        for code in all_codes:
            rows = _candidate_cache_for_code(
                code=code,
                data=frames[code],
                source_path=source_paths[code],
                config=config,
                data_root=data_root,
                dates=dates,
                allowed_lags=allowed_lags,
            )
            for as_of, candidate, next_open, local_score in rows:
                candidate_cache[as_of].append((candidate, next_open, local_score))
                diagnostics["buy_candidates"] += 1
            completed += 1
            if progress_every > 0 and completed % progress_every == 0:
                print(f"processed {completed}/{len(all_codes)} codes", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    _candidate_cache_for_code,
                    code=code,
                    data=frames[code],
                    source_path=source_paths[code],
                    config=config,
                    data_root=data_root,
                    dates=dates,
                    allowed_lags=allowed_lags,
                )
                for code in all_codes
            ]
            for future in as_completed(futures):
                for as_of, candidate, next_open, local_score in future.result():
                    candidate_cache[as_of].append((candidate, next_open, local_score))
                    diagnostics["buy_candidates"] += 1
                completed += 1
                if progress_every > 0 and completed % progress_every == 0:
                    print(f"processed {completed}/{len(all_codes)} codes", flush=True)

    for as_of in dates:
        candidates = sorted(candidate_cache.get(as_of, ()), key=lambda item: (-item[2], item[0].code))
        llm_allowed = {item[0].code for item in candidates[:llm_top_per_day]} if llm_top_per_day > 0 else {item[0].code for item in candidates}
        for candidate, next_open, _ in candidates:
            for lane in lanes:
                if lane == TS_LLM_LANE and candidate.code not in llm_allowed:
                    diagnostics["llm_candidate_skipped_by_top_limit"] += 1
                    record = _score_record(
                        candidate=candidate,
                        lane=DETERMINISTIC_LANE,
                        data_root=data_root,
                        config=config,
                        client=None,
                        next_open=next_open,
                        llm_cache=llm_cache,
                        is_buy_candidate=True,
                    )
                    record = ScoreRecord(
                        date=record.date,
                        code=record.code,
                        lane=TS_LLM_LANE,
                        score=NEGATIVE_AI_SCORE,
                        review_state="llm_skipped_by_top_limit",
                        confidence=0.0,
                        local_score=record.local_score,
                        is_buy_candidate=True,
                        components={**dict(record.components), "llm_top_per_day": llm_top_per_day},
                        next_open_date=record.next_open_date,
                        next_open_price=record.next_open_price,
                    )
                else:
                    record = _score_record(
                        candidate=candidate,
                        lane=lane,
                        data_root=data_root,
                        config=config,
                        client=client if lane == TS_LLM_LANE else None,
                        next_open=next_open,
                        llm_cache=llm_cache,
                        is_buy_candidate=True,
                    )
                by_lane_date[lane][as_of][candidate.code] = record
                if record.score >= 55 or record.review_state == "llm_skipped_by_top_limit":
                    score_rows.append(_score_row(record, rank=None))
    for lane in lanes:
        for as_of, records in by_lane_date[lane].items():
            ranked = sorted(records.values(), key=lambda row: (-row.score, row.code))
            for rank, record in enumerate(ranked[:50], start=1):
                score_rows.append(_score_row(record, rank=rank))
    return by_lane_date, score_rows, diagnostics


def _score_row(record: ScoreRecord, rank: int | None) -> dict[str, Any]:
    return {
        "date": record.date,
        "lane": record.lane,
        "code": record.code,
        "score": record.score,
        "review_state": record.review_state,
        "confidence": record.confidence,
        "local_score": record.local_score,
        "is_buy_candidate": record.is_buy_candidate,
        "is_current_holding": False,
        "rank": rank,
        "components_json": record.components,
        "next_open_date": record.next_open_date,
        "next_open_price": record.next_open_price,
    }


def close_on_or_before(frame: pd.DataFrame, as_of: str) -> float | None:
    data = frame.loc[frame["date"].le(pd.Timestamp(as_of))]
    if data.empty:
        return None
    close = pd.to_numeric(data.iloc[-1:].get("close"), errors="coerce").iloc[0]
    return float(close) if math.isfinite(float(close)) and float(close) > 0 else None


def execute_sell(state: ComboState, order: PendingOrder, frames: Mapping[str, pd.DataFrame], fill_date: str) -> None:
    position = state.positions.get(order.code)
    if position is None:
        state.counters["sell_missing_position"] += 1
        return
    date_, price = next_tradable_open(frames[order.code], order.decision_date)
    if date_ != fill_date or price is None:
        state.pending_orders.append(order)
        state.counters["sell_pending"] += 1
        return
    gross = position.shares * price
    fees = ashare_fees(gross, "sell", state.cost_mode)
    state.cash += gross - fees
    state.cost_paid += fees
    pnl = gross - fees - position.cost_basis
    ret = pnl / position.cost_basis if position.cost_basis > 0 else None
    state.trades.append({
        "combo_id": state.combo_id,
        "decision_date": order.decision_date,
        "fill_date": fill_date,
        "side": "sell",
        "code": order.code,
        "reason": order.reason,
        "score_at_decision": order.score_at_decision,
        "replacement_gap": order.replacement_gap,
        "entry_threshold": state.entry_threshold,
        "hold_threshold": state.hold_threshold,
        "max_positions": state.max_positions,
        "cost_mode": state.cost_mode,
        "open_price": price,
        "shares": position.shares,
        "gross_amount": gross,
        "fees": fees,
        "cash_after": state.cash,
        "entry_date": position.entry_date,
        "entry_price": position.entry_price,
        "exit_date": fill_date,
        "exit_price": price,
        "realized_pnl": pnl,
        "realized_return_pct": ret * 100 if ret is not None else None,
        "holding_days": (pd.Timestamp(fill_date) - pd.Timestamp(position.entry_date)).days,
    })
    del state.positions[order.code]
    state.counters["sell_count"] += 1
    if order.reason == "score_exit":
        state.counters["score_exit_count"] += 1
    elif order.reason == "replacement_exit":
        state.counters["replacement_count"] += 1


def execute_buy(state: ComboState, order: PendingOrder, frames: Mapping[str, pd.DataFrame], fill_date: str, initial_capital: float, lot_size: int) -> None:
    if order.code in state.positions:
        state.counters["buy_already_held"] += 1
        return
    if len(state.positions) >= state.max_positions:
        state.counters["buy_no_slot"] += 1
        return
    date_, price = next_tradable_open(frames[order.code], order.decision_date)
    if date_ != fill_date or price is None:
        state.pending_orders.append(order)
        state.counters["buy_pending"] += 1
        return
    target_value = initial_capital / max(state.max_positions, 1)
    budget = min(target_value, state.cash)
    shares = int(budget // (price * lot_size)) * lot_size
    if shares <= 0:
        state.counters["lot_skip_count"] += 1
        return
    gross = shares * price
    fees = ashare_fees(gross, "buy", state.cost_mode)
    total = gross + fees
    if total > state.cash:
        shares = int((state.cash - ashare_fees(price * lot_size, "buy", state.cost_mode)) // (price * lot_size)) * lot_size
        if shares <= 0:
            state.counters["cash_skip_count"] += 1
            return
        gross = shares * price
        fees = ashare_fees(gross, "buy", state.cost_mode)
        total = gross + fees
    if total > state.cash:
        state.counters["cash_skip_count"] += 1
        return
    state.cash -= total
    state.cost_paid += fees
    state.positions[order.code] = Position(order.code, shares, fill_date, price, order.score_at_decision, total)
    state.trades.append({
        "combo_id": state.combo_id,
        "decision_date": order.decision_date,
        "fill_date": fill_date,
        "side": "buy",
        "code": order.code,
        "reason": order.reason,
        "score_at_decision": order.score_at_decision,
        "replacement_gap": order.replacement_gap,
        "entry_threshold": state.entry_threshold,
        "hold_threshold": state.hold_threshold,
        "max_positions": state.max_positions,
        "cost_mode": state.cost_mode,
        "open_price": price,
        "shares": shares,
        "gross_amount": gross,
        "fees": fees,
        "cash_after": state.cash,
        "entry_date": fill_date,
        "entry_price": price,
        "exit_date": None,
        "exit_price": None,
        "realized_pnl": None,
        "realized_return_pct": None,
        "holding_days": None,
    })
    state.counters["buy_count"] += 1


def rescore_holding(code: str, as_of: str, lane: str, frames: Mapping[str, pd.DataFrame], source_paths: Mapping[str, Path], config: Mapping[str, Any], data_root: Path, client: OpenAICompatibleClient | None, llm_cache: dict[tuple[str, str], dict[str, Any]]) -> ScoreRecord | None:
    candidate = _holding_candidate(code, frames[code], config, as_of, source_paths[code])
    if candidate is None:
        return None
    return _score_record(
        candidate=candidate,
        lane=lane,
        data_root=data_root,
        config=config,
        client=client if lane == TS_LLM_LANE else None,
        next_open=next_tradable_open(frames[code], as_of),
        llm_cache=llm_cache,
        is_buy_candidate=False,
    )


def mark_equity(state: ComboState, frames: Mapping[str, pd.DataFrame], as_of: str) -> tuple[float, float]:
    market_value = 0.0
    for position in state.positions.values():
        close = close_on_or_before(frames[position.code], as_of)
        if close is not None:
            market_value += position.shares * close
    total = state.cash + market_value
    state.peak_equity = max(state.peak_equity, total)
    return market_value, total


def simulate_combo(
    *,
    lane: str,
    max_positions: int,
    replacement_gap: float,
    cost_mode: str,
    initial_capital: float,
    lot_size: int,
    dates: list[str],
    frames: Mapping[str, pd.DataFrame],
    source_paths: Mapping[str, Path],
    daily_candidates: Mapping[str, Mapping[str, ScoreRecord]],
    config: Mapping[str, Any],
    data_root: Path,
    client: OpenAICompatibleClient | None,
    entry_threshold: float,
    hold_threshold: float,
) -> ComboState:
    combo_id = f"{lane}|entry{entry_threshold:g}|hold{hold_threshold:g}|pos{max_positions}|gap{replacement_gap:g}|{cost_mode}"
    state = ComboState(combo_id, lane, max_positions, replacement_gap, cost_mode, entry_threshold, hold_threshold, initial_capital, peak_equity=initial_capital)
    llm_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for as_of in dates:
        orders = state.pending_orders
        state.pending_orders = []
        sells = [order for order in orders if order.side == "sell"]
        buys = [order for order in orders if order.side == "buy"]
        for order in sells:
            execute_sell(state, order, frames, as_of)
        for order in buys:
            execute_buy(state, order, frames, as_of, initial_capital, lot_size)

        holding_scores: dict[str, ScoreRecord] = {}
        for code in list(state.positions):
            record = rescore_holding(code, as_of, lane, frames, source_paths, config, data_root, client, llm_cache)
            if record is not None:
                holding_scores[code] = record
                if record.score < hold_threshold:
                    state.pending_orders.append(PendingOrder(as_of, "sell", code, "score_exit", record.score, replacement_gap))
            else:
                state.counters["holding_score_unavailable"] += 1

        available = [record for record in daily_candidates.get(as_of, {}).values() if record.score >= entry_threshold and record.code not in state.positions]
        available.sort(key=lambda row: (-row.score, row.code))
        queued_sell_codes = {order.code for order in state.pending_orders if order.side == "sell"}
        projected_positions = len([code for code in state.positions if code not in queued_sell_codes])
        for record in available:
            if projected_positions < max_positions:
                state.pending_orders.append(PendingOrder(as_of, "buy", record.code, "entry_threshold", record.score, replacement_gap))
                projected_positions += 1
                continue
            replaceable = [score for code, score in holding_scores.items() if code not in queued_sell_codes and score.score >= hold_threshold]
            if not replaceable:
                continue
            lowest = min(replaceable, key=lambda row: (row.score, row.code))
            if record.score >= lowest.score + replacement_gap:
                state.pending_orders.append(PendingOrder(as_of, "sell", lowest.code, "replacement_exit", lowest.score, replacement_gap, replace_code=record.code))
                state.pending_orders.append(PendingOrder(as_of, "buy", record.code, "replacement_entry", record.score, replacement_gap, replace_code=lowest.code))
                queued_sell_codes.add(lowest.code)
                state.counters["replacement_signal_count"] += 1

        market_value, total = mark_equity(state, frames, as_of)
        drawdown = (total / state.peak_equity - 1.0) * 100.0 if state.peak_equity > 0 else 0.0
        state.daily.append({
            "combo_id": combo_id,
            "date": as_of,
            "cash": state.cash,
            "entry_threshold": state.entry_threshold,
            "hold_threshold": state.hold_threshold,
            "market_value": market_value,
            "total_equity": total,
            "daily_return_pct": None,
            "drawdown_pct": drawdown,
            "position_count": len(state.positions),
            "holdings": sorted(state.positions),
            "scores": {code: record.score for code, record in holding_scores.items()},
            "pending_orders": [asdict(order) for order in state.pending_orders],
        })
    return state


def _init_sim_worker(
    dates: list[str],
    frames: Mapping[str, pd.DataFrame],
    source_paths: Mapping[str, Path],
    daily_scores: Mapping[str, Mapping[str, Mapping[str, ScoreRecord]]],
    config: Mapping[str, Any],
    data_root: Path,
    initial_capital: float,
    lot_size: int,
) -> None:
    _SIM_WORKER_CONTEXT.clear()
    _SIM_WORKER_CONTEXT.update({
        "dates": dates,
        "frames": frames,
        "source_paths": source_paths,
        "daily_scores": daily_scores,
        "config": config,
        "data_root": data_root,
        "initial_capital": initial_capital,
        "lot_size": lot_size,
    })


def _simulate_combo_task(task: tuple[str, float, float, int, float, str]) -> ComboState:
    lane, entry_threshold, hold_threshold, max_positions, replacement_gap, cost_mode = task
    ctx = _SIM_WORKER_CONTEXT
    return simulate_combo(
        lane=lane,
        max_positions=max_positions,
        replacement_gap=replacement_gap,
        cost_mode=cost_mode,
        initial_capital=ctx["initial_capital"],
        lot_size=ctx["lot_size"],
        dates=ctx["dates"],
        frames=ctx["frames"],
        source_paths=ctx["source_paths"],
        daily_candidates=ctx["daily_scores"][lane],
        config=ctx["config"],
        data_root=ctx["data_root"],
        client=None,
        entry_threshold=entry_threshold,
        hold_threshold=hold_threshold,
    )


def summarize_combo(state: ComboState, initial_capital: float) -> dict[str, Any]:
    final_equity = state.daily[-1]["total_equity"] if state.daily else initial_capital
    returns = []
    previous = None
    for row in state.daily:
        total = float(row["total_equity"])
        if previous and previous > 0:
            value = total / previous - 1.0
            row["daily_return_pct"] = value * 100.0
            returns.append(value)
        previous = total
    closed = [trade for trade in state.trades if trade.get("side") == "sell" and trade.get("realized_return_pct") is not None]
    closed_returns = [float(trade["realized_return_pct"]) for trade in closed]
    return {
        "combo_id": state.combo_id,
        "lane": state.lane,
        "max_positions": state.max_positions,
        "replacement_gap": state.replacement_gap,
        "entry_threshold": state.entry_threshold,
        "hold_threshold": state.hold_threshold,
        "cost_mode": state.cost_mode,
        "final_equity": final_equity,
        "total_return_pct": (final_equity / initial_capital - 1.0) * 100.0 if initial_capital > 0 else None,
        "annualized_return_pct": None,
        "max_drawdown_pct": min((float(row["drawdown_pct"]) for row in state.daily), default=0.0),
        "daily_volatility_pct": float(pd.Series(returns).std(ddof=0) * 100.0) if returns else 0.0,
        "sharpe_like": (float(pd.Series(returns).mean() / pd.Series(returns).std(ddof=0) * math.sqrt(252)) if len(returns) > 1 and float(pd.Series(returns).std(ddof=0)) > 0 else None),
        "exposure_days": sum(1 for row in state.daily if int(row["position_count"]) > 0),
        "avg_exposure_pct": sum((float(row["market_value"]) / float(row["total_equity"]) * 100.0) for row in state.daily if float(row["total_equity"]) > 0) / len(state.daily) if state.daily else 0.0,
        "trade_count": len(state.trades),
        "buy_count": state.counters["buy_count"],
        "sell_count": state.counters["sell_count"],
        "replacement_count": state.counters["replacement_count"],
        "score_exit_count": state.counters["score_exit_count"],
        "cash_skip_count": state.counters["cash_skip_count"],
        "lot_skip_count": state.counters["lot_skip_count"],
        "cost_paid": state.cost_paid,
        "closed_trade_win_rate": sum(1 for ret in closed_returns if ret > 0) / len(closed_returns) if closed_returns else None,
        "avg_closed_trade_return_pct": sum(closed_returns) / len(closed_returns) if closed_returns else None,
        "median_closed_trade_return_pct": float(pd.Series(closed_returns).median()) if closed_returns else None,
        "avg_hold_days": sum(float(trade["holding_days"]) for trade in closed if trade.get("holding_days") is not None) / len(closed) if closed else None,
        "turnover_ratio": sum(abs(float(trade.get("gross_amount") or 0.0)) for trade in state.trades) / initial_capital if initial_capital > 0 else None,
        "open_positions_end": len(state.positions),
        "pending_orders_end": len(state.pending_orders),
        **{key: value for key, value in sorted(state.counters.items())},
    }


def load_frames(data_root: Path, start_date: str, end_date: str | None) -> tuple[dict[str, pd.DataFrame], dict[str, Path], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    source_paths: dict[str, Path] = {}
    all_dates: set[str] = set()
    for path in sorted(data_root.glob("*.parquet")):
        try:
            data = pd.read_parquet(path)
        except Exception:
            continue
        data = normalise_stock_frame(data)
        if data.empty:
            continue
        if end_date is not None:
            data = data.loc[data["date"].le(pd.Timestamp(end_date))].copy()
        if data.empty or data["date"].max() < pd.Timestamp(start_date):
            continue
        code = path.stem
        frames[code] = data.reset_index(drop=True)
        source_paths[code] = path
        trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string").eq("1").fillna(False)
        dates = pd.to_datetime(data.loc[trade, "date"], errors="coerce").dt.date.astype(str)
        all_dates.update(item for item in dates if item >= start_date and (end_date is None or item <= end_date))
    return frames, source_paths, sorted(all_dates)


def build_client(ai_config_path: Path) -> tuple[OpenAICompatibleClient | None, dict[str, Any]]:
    provider_config = load_ai_provider_config(ai_config_path, project_root=ROOT)
    meta = provider_config.as_mapping()
    shared = build_shared_ai_client(provider_config)
    if shared is None:
        return None, meta
    client = OpenAICompatibleClient(
        provider=shared.provider,
        base_url=shared.base_url,
        api_key=shared.api_key,
        model=shared.model,
        timeout_seconds=shared.timeout_seconds,
        temperature=shared.temperature,
        seed=shared.seed,
        response_format=shared.response_format,
        extra_options=shared.extra_options,
    )
    return client, meta


def write_stage_note(path: Path, summary_rows: list[dict[str, Any]], args: argparse.Namespace, provider_meta: Mapping[str, Any]) -> None:
    best_cost = sorted((row for row in summary_rows if row["cost_mode"] == "ashare"), key=lambda row: float(row["final_equity"]), reverse=True)[:5]
    best_none = sorted((row for row in summary_rows if row["cost_mode"] == "none"), key=lambda row: float(row["final_equity"]), reverse=True)[:5]
    def table(rows: list[dict[str, Any]]) -> str:
        lines = ["| lane | entry | hold | max_positions | gap | cost | final_equity | total_return_pct | max_drawdown_pct | trades |", "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |"]
        for row in rows:
            lines.append(f"| {row['lane']} | {row['entry_threshold']} | {row['hold_threshold']} | {row['max_positions']} | {row['replacement_gap']} | {row['cost_mode']} | {float(row['final_equity']):.2f} | {float(row['total_return_pct']):.2f}% | {float(row['max_drawdown_pct']):.2f}% | {row['trade_count']} |")
        return "\n".join(lines)
    content = f"""# MKF AI 分数动态轮换无消息面回测

## 阶段状态

本阶段完成离线 research/paper 回测：从 {args.start_date} 起每日扫描 MKF 候选，使用 AI 分数入选阈值和持仓退出阈值做动态轮换，并测试阈值网格、`max_positions`、`replacement_gap`、无成本/含 A 股成本组合。

## 关键边界

- 消息面：禁用。当前历史消息面不可 point-in-time 确认，本轮不抓取、不读取新闻缓存。
- Provider：`{provider_meta.get('provider')}`；LLM lane 使用 `yaml/ai_providers.yaml` 当前默认 provider，未在回测脚本内强制切换。
- 执行：下一股票可交易日 open；不是当日 close。
- 模式：paper/research only；没有券商连接、没有真实下单、不是收益承诺。
- 数据：`PFrontStockData` 当前文件集合，存在幸存者偏差风险。

## 含成本最佳行 Top 5

{table(best_cost)}

## 无成本最佳行 Top 5

{table(best_none)}

## 文件清单

- `summary.json`
- `grid_summary.csv`
- `trades.csv`
- `daily_equity.csv`
- `daily_scores_top.csv`
- `manifest.json`
- `阶段项目说明.md`

## 后续边界

优先看含成本结果。不得因为单个最高收益组合而直接改 scanner 或用于实盘；若继续，应固定本轮最佳少数组合做年度分层、样本外和成交可得性压力测试。
"""
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest MKF AI score dynamic rotation without news.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--ai-config", type=Path, default=Path("yaml/ai_providers.yaml"))
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date")
    parser.add_argument("--initial-capital", type=float, default=10000.0)
    parser.add_argument("--entry-threshold", type=float, default=65.0)
    parser.add_argument("--hold-threshold", type=float, default=60.0)
    parser.add_argument("--entry-threshold-grid", default=None)
    parser.add_argument("--hold-threshold-grid", default=None)
    parser.add_argument("--score-lanes", default=DETERMINISTIC_LANE)
    parser.add_argument("--max-positions-grid", default="1,2,3")
    parser.add_argument("--replacement-gap-grid", default="0,3,5")
    parser.add_argument("--cost-modes", default="none,ashare")
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--llm-top-per-day", type=int, default=5)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--progress-every", type=int, default=250)
    args = parser.parse_args()

    lanes = _parse_csv_values(args.score_lanes)
    for lane in lanes:
        if lane not in {DETERMINISTIC_LANE, TS_LLM_LANE}:
            raise ValueError(f"unknown score lane: {lane}")
    entry_threshold_grid = _parse_csv_values(args.entry_threshold_grid, float) if args.entry_threshold_grid else [args.entry_threshold]
    hold_threshold_grid = _parse_csv_values(args.hold_threshold_grid, float) if args.hold_threshold_grid else [args.hold_threshold]
    threshold_grid = [(entry, hold) for entry in entry_threshold_grid for hold in hold_threshold_grid if hold <= entry]
    if not threshold_grid:
        raise ValueError("threshold grid is empty; require hold_threshold <= entry_threshold")
    max_positions_grid = _parse_csv_values(args.max_positions_grid, int)
    replacement_gap_grid = _parse_csv_values(args.replacement_gap_grid, float)
    cost_modes = _parse_csv_values(args.cost_modes)
    for cost_mode in cost_modes:
        if cost_mode not in {"none", "ashare"}:
            raise ValueError(f"unknown cost mode: {cost_mode}")

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    ai_config_path = args.ai_config if args.ai_config.is_absolute() else ROOT / args.ai_config
    data_root = args.data_root if args.data_root.is_absolute() else ROOT / args.data_root
    output_root = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    config = load_config(config_path)
    validate_config(config, config_path)
    provider_client = None
    provider_meta: dict[str, Any] = {"provider": None, "enabled": False}
    if TS_LLM_LANE in lanes:
        provider_client, provider_meta = build_client(ai_config_path)
    else:
        provider_meta = load_ai_provider_config(ai_config_path, project_root=ROOT).as_mapping()

    frames, source_paths, dates = load_frames(data_root, args.start_date, args.end_date)
    if not frames:
        raise ValueError("no parquet frames loaded")
    if not dates:
        raise ValueError("no trading dates in requested range")

    run_id = args.run_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_mkf_ai_score_rotation"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    daily_scores, score_rows, diagnostics = build_daily_scores(
        frames=frames,
        source_paths=source_paths,
        config=config,
        data_root=data_root,
        dates=dates,
        lanes=lanes,
        client=provider_client,
        progress_every=args.progress_every,
        llm_top_per_day=args.llm_top_per_day,
        workers=args.workers,
    )

    combo_tasks = [
        (lane, entry_threshold, hold_threshold, max_positions, replacement_gap, cost_mode)
        for lane, (entry_threshold, hold_threshold), max_positions, replacement_gap, cost_mode in product(
            lanes,
            threshold_grid,
            max_positions_grid,
            replacement_gap_grid,
            cost_modes,
        )
    ]
    all_states: list[ComboState] = []
    combo_worker_count = max(1, min(int(args.workers), len(combo_tasks)))
    if TS_LLM_LANE in lanes or combo_worker_count == 1:
        _init_sim_worker(dates, frames, source_paths, daily_scores, config, data_root, args.initial_capital, args.lot_size)
        for task in combo_tasks:
            all_states.append(_simulate_combo_task(task))
    else:
        completed = 0
        with ProcessPoolExecutor(
            max_workers=combo_worker_count,
            initializer=_init_sim_worker,
            initargs=(dates, frames, source_paths, daily_scores, config, data_root, args.initial_capital, args.lot_size),
        ) as executor:
            futures = [executor.submit(_simulate_combo_task, task) for task in combo_tasks]
            for future in as_completed(futures):
                all_states.append(future.result())
                completed += 1
                if args.progress_every > 0 and completed % args.progress_every == 0:
                    print(f"simulated {completed}/{len(combo_tasks)} combos", flush=True)

    summary_rows = [summarize_combo(state, args.initial_capital) for state in all_states]
    trade_rows = [trade for state in all_states for trade in state.trades]
    daily_rows = [row for state in all_states for row in state.daily]

    summary_csv_fields = [
        "combo_id", "lane", "entry_threshold", "hold_threshold", "max_positions", "replacement_gap", "cost_mode", "final_equity", "total_return_pct",
        "annualized_return_pct", "max_drawdown_pct", "daily_volatility_pct", "sharpe_like", "exposure_days",
        "avg_exposure_pct", "trade_count", "buy_count", "sell_count", "replacement_count", "score_exit_count",
        "cash_skip_count", "lot_skip_count", "cost_paid", "closed_trade_win_rate", "avg_closed_trade_return_pct",
        "median_closed_trade_return_pct", "avg_hold_days", "turnover_ratio", "open_positions_end", "pending_orders_end",
    ]
    trade_fields = [
        "combo_id", "decision_date", "fill_date", "side", "code", "reason", "score_at_decision", "replacement_gap",
        "entry_threshold", "hold_threshold", "max_positions", "cost_mode", "open_price", "shares", "gross_amount", "fees", "cash_after", "entry_date",
        "entry_price", "exit_date", "exit_price", "realized_pnl", "realized_return_pct", "holding_days",
    ]
    daily_fields = ["combo_id", "date", "cash", "entry_threshold", "hold_threshold", "market_value", "total_equity", "daily_return_pct", "drawdown_pct", "position_count", "holdings", "scores", "pending_orders"]
    score_fields = ["date", "lane", "code", "score", "review_state", "confidence", "local_score", "is_buy_candidate", "is_current_holding", "rank", "components_json", "next_open_date", "next_open_price"]

    _write_csv(run_dir / "grid_summary.csv", summary_rows, summary_csv_fields)
    _write_csv(run_dir / "trades.csv", trade_rows, trade_fields)
    _write_csv(run_dir / "daily_equity.csv", daily_rows, daily_fields)
    _write_csv(run_dir / "daily_scores_top.csv", score_rows, score_fields)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_ai_score_dynamic_rotation_no_news",
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_date": args.start_date,
        "end_date": dates[-1],
        "initial_capital": args.initial_capital,
        "entry_threshold": args.entry_threshold,
        "hold_threshold": args.hold_threshold,
        "entry_threshold_grid": entry_threshold_grid,
        "hold_threshold_grid": hold_threshold_grid,
        "threshold_grid_size": len(threshold_grid),
        "max_positions_grid": max_positions_grid,
        "replacement_gap_grid": replacement_gap_grid,
        "cost_modes": cost_modes,
        "score_lanes": lanes,
        "llm_top_per_day": args.llm_top_per_day,
        "execution_price": "next_stock_tradable_open",
        "lot_size": args.lot_size,
        "candidate_set": "mkf_red_blue_cross20_post_configured_lags_and_production_gate_mask",
        "config_path": str(config_path),
        "config_sha256": compute_config_sha256(config_path),
        "ai_config_path": str(ai_config_path),
        "ai_config_sha256": _sha256(ai_config_path),
        "ai_provider": provider_meta.get("provider"),
        "data_root": str(data_root),
        "data_file_count": len(frames),
        "data_observed_latest": max(dates),
        "workers_requested": args.workers,
        "combo_tasks": len(combo_tasks),
        "combo_workers_used": combo_worker_count if TS_LLM_LANE not in lanes else 1,
        "combo_parallel": TS_LLM_LANE not in lanes and combo_worker_count > 1,
        "news_context_used": False,
        "archived_ai_review_used": False,
        "boundaries": {
            "research_only": True,
            "paper_simulation_only": True,
            "broker_connected": False,
            "orders_submitted": False,
            "live_trading_enabled": False,
        },
        "limitations": [
            "current_parquet_file_survivorship_bias_possible",
            "adjusted_daily_bars_not_live_execution_feed",
            "no_historical_news_point_in_time_replay",
            "limit_up_down_fillability_not_fully_modeled",
            "not_investment_advice_or_return_promise",
        ],
        "diagnostics": dict(diagnostics),
    }
    (run_dir / "summary.json").write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    write_stage_note(run_dir / "阶段项目说明.md", summary_rows, args, provider_meta)

    files = {}
    for path in sorted(run_dir.iterdir()):
        if path.name == "manifest.json" or not path.is_file():
            continue
        files[path.name] = {"sha256": _sha256(path), "bytes": path.stat().st_size}
    manifest = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "files": files}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
