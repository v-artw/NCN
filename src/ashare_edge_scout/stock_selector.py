"""Read-only SMC stock selection from validated local daily bars."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .signals.candle_confirm import compute_candle_confirmation_features
from .config import compute_config_sha256, load_config, validate_config
from .data.daily_bars import DataValidationError
from .data.data_sources import get_parquet_codes, get_parquet_latest_date_coverage, load_stock_records
from .research_nextday_validation import candlestick_masks, expanded_futu_masks_from_values
from .research_futu_ranking import tradable_indicator_values
from .research_precision70 import production_gate_mask


@dataclass(frozen=True)
class StockSelectionRow:
    code: str
    signal_date: str
    research_close: float
    amount_cny: float
    turn_pct: float
    smc_gap_pct: float
    ema20: float
    ema50: float
    risk_warning_count: int
    risk_warnings: tuple[str, ...]
    selection_reason: str = "smc_medium_buy_and_hard_gates"
    research_only: bool = True
    start_diagnostic_label: str = "未分类"
    start_diagnostic_type: str = "unclassified_start_diagnostic"
    start_diagnostic_reason: str = "insufficient_or_mixed_setup"
    range_position_20d_pct: float = 100.0
    range_position_60d_pct: float = 100.0
    range_position_120d_pct: float = 100.0
    prior_return_20d_pct: float = 0.0
    current_return_20d_pct: float = 0.0
    distance_to_high_60d_pct: float = 0.0
    recent_pullback_from_high_pct: float = 0.0
    volume_ratio_20: float = 0.0


@dataclass(frozen=True)
class StockSelectionResult:
    run_directory: Path
    candidates_path: Path
    timestamped_candidates_path: Path
    candidates_json_path: Path
    summary_path: Path
    manifest_path: Path
    signal_date: date
    candidate_count: int


def _finite_float(value: Any) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError("non-finite selector value")
    return result


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _range_position_pct(history: pd.DataFrame, window: int) -> float:
    sample = history.tail(window)
    if sample.empty:
        return 100.0
    close = _safe_float(sample.iloc[-1].get("close"), 0.0)
    high = _safe_float(pd.to_numeric(sample["high"], errors="coerce").max(), close)
    low = _safe_float(pd.to_numeric(sample["low"], errors="coerce").min(), close)
    if high <= low:
        return 100.0
    return float(np.clip((close - low) / (high - low) * 100.0, 0.0, 100.0))


def _return_pct(history: pd.DataFrame, current_offset: int, prior_offset: int) -> float:
    if len(history) <= max(current_offset, prior_offset):
        return 0.0
    current = _safe_float(history.iloc[-1 - current_offset].get("close"), 0.0)
    prior = _safe_float(history.iloc[-1 - prior_offset].get("close"), 0.0)
    if current <= 0.0 or prior <= 0.0:
        return 0.0
    return (current / prior - 1.0) * 100.0


def _compute_start_diagnostic(
    data: pd.DataFrame,
    values: pd.DataFrame,
    row_index: int,
    smc_gap_pct: float,
) -> dict[str, Any]:
    tradable = data.loc[values.index].copy()
    history = tradable.loc[tradable.index <= row_index].copy()
    if history.empty:
        return {
            "start_diagnostic_label": "未分类",
            "start_diagnostic_type": "unclassified_start_diagnostic",
            "start_diagnostic_reason": "limited_history",
            "range_position_20d_pct": 100.0,
            "range_position_60d_pct": 100.0,
            "range_position_120d_pct": 100.0,
            "prior_return_20d_pct": 0.0,
            "current_return_20d_pct": 0.0,
            "distance_to_high_60d_pct": 0.0,
            "recent_pullback_from_high_pct": 0.0,
            "volume_ratio_20": 0.0,
        }

    close_t = _safe_float(history.iloc[-1].get("close"), 0.0)
    range20 = _range_position_pct(history, 20)
    range60 = _range_position_pct(history, 60)
    range120 = _range_position_pct(history, 120)
    prior_return20 = _return_pct(history, 1, 21)
    current_return20 = _return_pct(history, 0, 20)
    high60 = _safe_float(pd.to_numeric(history.tail(60)["high"], errors="coerce").max(), close_t)
    distance_to_high60 = (close_t / high60 - 1.0) * 100.0 if close_t > 0.0 and high60 > 0.0 else 0.0

    prior_rows = history.iloc[:-1]
    prior_high20 = _safe_float(pd.to_numeric(prior_rows.tail(20)["high"], errors="coerce").max(), 0.0) if not prior_rows.empty else 0.0
    prior_high3 = _safe_float(pd.to_numeric(prior_rows.tail(3)["high"], errors="coerce").max(), 0.0) if not prior_rows.empty else 0.0
    recent_low5 = _safe_float(pd.to_numeric(prior_rows.tail(5)["low"], errors="coerce").min(), 0.0) if not prior_rows.empty else 0.0
    recent_pullback = (recent_low5 / prior_high20 - 1.0) * 100.0 if recent_low5 > 0.0 and prior_high20 > 0.0 else 0.0

    candle = compute_candle_confirmation_features(
        open_=pd.to_numeric(history["open"], errors="coerce").fillna(0.0).tolist(),
        high=pd.to_numeric(history["high"], errors="coerce").fillna(0.0).tolist(),
        low=pd.to_numeric(history["low"], errors="coerce").fillna(0.0).tolist(),
        close=pd.to_numeric(history["close"], errors="coerce").fillna(0.0).tolist(),
        volume=pd.to_numeric(history["volume"], errors="coerce").fillna(0.0).tolist(),
    )
    volume_ratio20 = _safe_float(candle.get("candle_volume_ratio_20"), 0.0)
    close_location = _safe_float(candle.get("candle_close_location"), 0.0)
    box_breakout = bool(candle.get("candle_box_breakout"))
    bullish_continuation = bool(candle.get("candle_bullish_continuation"))

    high_reasons: list[str] = []
    if range20 >= 95.0:
        high_reasons.append("pos20_ge_95")
    if range60 >= 90.0:
        high_reasons.append("pos60_ge_90")
    if distance_to_high60 >= -2.0:
        high_reasons.append("near_60d_high")
    if prior_return20 >= 25.0:
        high_reasons.append("prior_ret20_ge_25")
    if current_return20 >= 35.0:
        high_reasons.append("current_ret20_ge_35")

    if high_reasons:
        label = "高位追涨"
        diagnostic_type = "high_position_chase"
        reason = "|".join(high_reasons)
    elif (
        range60 <= 55.0
        and range20 <= 75.0
        and (box_breakout or (prior_high20 > 0.0 and close_t > prior_high20 * 1.003))
        and prior_return20 <= 15.0
        and 1.05 <= volume_ratio20 <= 2.80
        and close_location >= 0.55
    ):
        label = "A"
        diagnostic_type = "base_breakout_start"
        reason = "low_midlow_pos60|controlled_prior_ret20|prior_box_breakout|healthy_volume|strong_close"
    else:
        value_history = values.loc[values.index <= row_index]
        ema20_now = _safe_float(value_history["ema20"].iloc[-1], 0.0) if not value_history.empty else 0.0
        ema50_now = _safe_float(value_history["ema50"].iloc[-1], 0.0) if not value_history.empty else 0.0
        ema20_prior = _safe_float(value_history["ema20"].iloc[-6], ema20_now) if len(value_history) >= 6 else ema20_now
        reaccelerated = smc_gap_pct > 0.0 and ((prior_high3 > 0.0 and close_t > prior_high3) or bullish_continuation)
        if (
            ema20_now > ema50_now
            and ema20_now >= ema20_prior
            and -15.0 <= recent_pullback <= -3.0
            and reaccelerated
            and range60 <= 85.0
            and range20 <= 90.0
            and prior_return20 <= 25.0
            and 0.90 <= volume_ratio20 <= 3.20
        ):
            label = "B"
            diagnostic_type = "pullback_reacceleration"
            reason = "ema20_gt_ema50|ema20_rising|recent_pullback|smc_gap_reacceleration|not_too_high|acceptable_volume"
        else:
            label = "未分类"
            diagnostic_type = "unclassified_start_diagnostic"
            reason = "selected_by_smc_but_no_clean_start_pattern"

    return {
        "start_diagnostic_label": label,
        "start_diagnostic_type": diagnostic_type,
        "start_diagnostic_reason": reason,
        "range_position_20d_pct": range20,
        "range_position_60d_pct": range60,
        "range_position_120d_pct": range120,
        "prior_return_20d_pct": prior_return20,
        "current_return_20d_pct": current_return20,
        "distance_to_high_60d_pct": distance_to_high60,
        "recent_pullback_from_high_pct": recent_pullback,
        "volume_ratio_20": volume_ratio20,
    }


def evaluate_stock(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    as_of: date,
) -> StockSelectionRow | None:
    """Return one selected row using data visible through ``as_of`` only."""

    data = pd.DataFrame(records)
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = (
        data.dropna(subset=["date"])
        .sort_values("date", kind="stable")
        .drop_duplicates("date", keep="last")
    )
    cutoff = pd.Timestamp(as_of)
    data = data.loc[data["date"].le(cutoff)].copy().reset_index(drop=True)
    if data.empty or data.iloc[-1]["date"] != cutoff:
        return None

    row_index = data.index[-1]
    admitted = production_gate_mask(code, data, config)
    if not bool(admitted.loc[row_index]):
        return None

    values = tradable_indicator_values(data)
    if row_index not in values.index:
        return None
    masks = expanded_futu_masks_from_values(values)
    if not bool(masks["smc_medium_buy"].loc[row_index]):
        return None

    risk_warnings: list[str] = []
    for name in ("kdj_trend_pro_sell", "mkf_bearcluster"):
        if bool(masks[name].loc[row_index]):
            risk_warnings.append(name)
    candle = candlestick_masks(data)
    if bool(candle["candle_tweezer_top"].loc[row_index]):
        risk_warnings.append("candle_tweezer_top")

    latest = data.loc[row_index]
    high_t2 = _finite_float(values["high"].shift(2).loc[row_index])
    low_t = _finite_float(values["low"].loc[row_index])
    smc_gap_pct = (low_t / high_t2 - 1.0) * 100.0
    diagnostic = _compute_start_diagnostic(data, values, row_index, smc_gap_pct)
    return StockSelectionRow(
        code=code,
        signal_date=as_of.isoformat(),
        research_close=_finite_float(latest["close"]),
        amount_cny=_finite_float(latest["amount"]),
        turn_pct=_finite_float(latest["turn"]),
        smc_gap_pct=smc_gap_pct,
        ema20=_finite_float(values["ema20"].loc[row_index]),
        ema50=_finite_float(values["ema50"].loc[row_index]),
        risk_warning_count=len(risk_warnings),
        risk_warnings=tuple(risk_warnings),
        **diagnostic,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_publish(
    output_root: Path,
    run_id: str,
    rows: Sequence[StockSelectionRow],
    summary: Mapping[str, Any],
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    temporary = output_root / f".{run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"selection run already exists: {destination}")
    temporary.mkdir()
    try:
        fieldnames = list(StockSelectionRow.__dataclass_fields__)
        generated_at = datetime.now(timezone.utc)
        published_at = summary.get("published_at_utc")
        if published_at:
            try:
                generated_at = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            except ValueError:
                pass
        timestamped_csv_name = f"smc_candidates_{generated_at.astimezone().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = temporary / "candidates.csv"
        timestamped_csv_path = temporary / timestamped_csv_name
        for output_path in (csv_path, timestamped_csv_path):
            with output_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    values = asdict(row)
                    values["risk_warnings"] = "|".join(row.risk_warnings)
                    writer.writerow(values)
        json_rows = [asdict(row) for row in rows]
        (temporary / "candidates.json").write_text(
            json.dumps(json_rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (temporary / "summary.json").write_text(
            json.dumps(dict(summary), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        files = {
            name: {"sha256": _sha256(temporary / name)}
            for name in ("candidates.csv", timestamped_csv_name, "candidates.json", "summary.json")
        }
        manifest = {
            "schema_version": "ncn_smc_stock_selector_v4",
            "run_id": run_id,
            "timestamped_candidates_csv": timestamped_csv_name,
            "files": files,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    except Exception:
        import shutil

        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def run_stock_selection(
    *,
    data_root: Path,
    config_path: Path,
    output_root: Path,
    as_of: date | None = None,
    run_id: str | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> StockSelectionResult:
    """Evaluate the full local universe and publish an immutable selection run."""

    automatic_as_of = as_of is None
    config = load_config(config_path)
    validate_config(config, config_path)
    codes = get_parquet_codes(data_root)
    if not codes:
        raise ValueError(f"no parquet files under {data_root}")
    if as_of is None:
        observed_latest, _, _ = get_parquet_latest_date_coverage(data_root, codes)
        if observed_latest is None:
            raise ValueError("no readable parquet date")
        as_of = observed_latest

    selected: list[StockSelectionRow] = []
    failures: Counter[str] = Counter()
    evaluated_count = 0
    for code in codes:
        try:
            records = load_stock_records(code, data_root)
            row = evaluate_stock(code, records, config, as_of)
            evaluated_count += 1
            if row is not None:
                selected.append(row)
        except DataValidationError as exc:
            failures[exc.code] += 1
        except Exception:
            failures["unexpected_error"] += 1
        if progress is not None and (evaluated_count + sum(failures.values()) == len(codes) or (evaluated_count + sum(failures.values())) % 500 == 0):
            progress(evaluated_count + sum(failures.values()), len(codes), len(selected))

    selected.sort(key=lambda row: (row.risk_warning_count, -row.amount_cny, row.code))
    actual_run_id = run_id or f"select-{as_of.isoformat()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    summary = {
        "schema_version": "ncn_smc_stock_selector_v4",
        "status": "success",
        "run_id": actual_run_id,
        "signal_date": as_of.isoformat(),
        "intended_entry_reference_session": "next_trading_session_open",
        "later_target_contract": "entry_open_x_1.03_observed_on_entry_plus_1_through_entry_plus_5",
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_code_count": len(codes),
        "evaluated_code_count": evaluated_count,
        "rejected_data_count": int(sum(failures.values())),
        "candidate_count": len(selected),
        "error_counts": dict(sorted(failures.items())),
        "quantity_conservation_valid": evaluated_count + sum(failures.values()) == len(codes),
        "selection_rule": "smc_medium_buy_and_existing_hard_gates",
        "prospective_eligible": automatic_as_of,
        "prospective_eligibility_reason": "automatic_as_of" if automatic_as_of else "manual_as_of",
        "review_order": "risk_warning_count_asc_amount_cny_desc_code_asc",
        "diagnostic_annotation": {
            "name": "smc_start_diagnostic_v1",
            "read_only": True,
            "affects_selection": False,
            "affects_ranking": False,
        },
        "config_path": str(config_path),
        "config_sha256": compute_config_sha256(config_path),
        "data_root": str(data_root),
        "boundaries": {
            "read_only": True,
            "production_enabled": False,
            "broker_connected": False,
            "orders_submitted": False,
            "returns_calculated": False,
        },
        "limitations": [
            "adjusted_research_daily_bars",
            "current_file_survivorship",
            "no_fill_or_execution_evidence",
            "candidate_not_investment_advice",
        ],
    }
    directory = _atomic_publish(output_root, actual_run_id, selected, summary)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return StockSelectionResult(
        run_directory=directory,
        candidates_path=directory / "candidates.csv",
        timestamped_candidates_path=directory / manifest["timestamped_candidates_csv"],
        candidates_json_path=directory / "candidates.json",
        summary_path=directory / "summary.json",
        manifest_path=directory / "manifest.json",
        signal_date=as_of,
        candidate_count=len(selected),
    )
