"""Read-only A-class base-breakout stock selection from local daily bars."""

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
from .research_futu_ranking import tradable_indicator_values
from .research_precision70 import production_gate_mask
from .stock_selector import _range_position_pct, _return_pct, _safe_float

SCHEMA_VERSION = "ncn_a_class_selector_v1"
SELECTION_RULE = "a_class_base_breakout_v1_and_existing_hard_gates"


@dataclass(frozen=True)
class AClassSelectionRow:
    code: str
    signal_date: str
    research_close: float
    amount_cny: float
    turn_pct: float
    range_position_20d_pct: float
    range_position_60d_pct: float
    range_position_120d_pct: float
    prior_return_20d_pct: float
    current_return_20d_pct: float
    distance_to_high_60d_pct: float
    volume_ratio_20: float
    close_location: float
    upper_shadow_pct: float
    breakout_margin_pct: float
    a_class_reason: str
    selection_reason: str = "a_class_base_breakout_v1_and_hard_gates"
    research_only: bool = True


@dataclass(frozen=True)
class AClassSelectionResult:
    run_directory: Path
    candidates_path: Path
    timestamped_candidates_path: Path
    candidates_json_path: Path
    summary_path: Path
    manifest_path: Path
    signal_date: date
    candidate_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _a_class_metrics(data: pd.DataFrame, row_index: int) -> dict[str, Any]:
    tradable = data.loc[data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string").eq("1").fillna(False)].copy()
    history = tradable.loc[tradable.index <= row_index].copy()
    if history.empty:
        return {"eligible": False, "reject_reason": "limited_history"}

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
    breakout_margin = (close_t / prior_high20 - 1.0) * 100.0 if close_t > 0.0 and prior_high20 > 0.0 else 0.0

    candle = compute_candle_confirmation_features(
        open_=pd.to_numeric(history["open"], errors="coerce").fillna(0.0).tolist(),
        high=pd.to_numeric(history["high"], errors="coerce").fillna(0.0).tolist(),
        low=pd.to_numeric(history["low"], errors="coerce").fillna(0.0).tolist(),
        close=pd.to_numeric(history["close"], errors="coerce").fillna(0.0).tolist(),
        volume=pd.to_numeric(history["volume"], errors="coerce").fillna(0.0).tolist(),
    )
    volume_ratio20 = _safe_float(candle.get("candle_volume_ratio_20"), 0.0)
    close_location = _safe_float(candle.get("candle_close_location"), 0.0)
    upper_shadow_pct = _safe_float(candle.get("candle_upper_shadow_pct"), 1.0)
    box_breakout = bool(candle.get("candle_box_breakout")) or breakout_margin > 0.3
    long_upper_shadow = bool(candle.get("candle_long_upper_shadow_risk"))

    rejections: list[str] = []
    if range60 > 55.0:
        rejections.append("pos60_gt_55")
    if range120 > 65.0:
        rejections.append("pos120_gt_65")
    if range20 > 75.0:
        rejections.append("pos20_gt_75")
    if prior_return20 > 15.0:
        rejections.append("prior_ret20_gt_15")
    if not box_breakout:
        rejections.append("no_prior_box_breakout")
    if not 1.05 <= volume_ratio20 <= 2.80:
        rejections.append("volume_ratio_outside_1p05_2p80")
    if close_location < 0.55:
        rejections.append("close_location_lt_0p55")
    if long_upper_shadow:
        rejections.append("long_upper_shadow_risk")

    reason = "low_midlow_pos60|low_mid_pos120|controlled_ret20|prior_box_breakout|healthy_volume|strong_close|no_long_upper_shadow"
    return {
        "eligible": not rejections,
        "reject_reason": "|".join(rejections) if rejections else "",
        "range_position_20d_pct": range20,
        "range_position_60d_pct": range60,
        "range_position_120d_pct": range120,
        "prior_return_20d_pct": prior_return20,
        "current_return_20d_pct": current_return20,
        "distance_to_high_60d_pct": distance_to_high60,
        "volume_ratio_20": volume_ratio20,
        "close_location": close_location,
        "upper_shadow_pct": upper_shadow_pct,
        "breakout_margin_pct": breakout_margin,
        "a_class_reason": reason,
    }


def evaluate_a_class_stock(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    as_of: date,
) -> AClassSelectionRow | None:
    data = pd.DataFrame(records)
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
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

    metrics = _a_class_metrics(data, row_index)
    if not bool(metrics.pop("eligible")):
        return None
    metrics.pop("reject_reason", None)
    latest = data.loc[row_index]
    return AClassSelectionRow(
        code=code,
        signal_date=as_of.isoformat(),
        research_close=_safe_float(latest.get("close"), 0.0),
        amount_cny=_safe_float(latest.get("amount"), 0.0),
        turn_pct=_safe_float(latest.get("turn"), 0.0),
        **metrics,
    )


def _atomic_publish(
    output_root: Path,
    run_id: str,
    rows: Sequence[AClassSelectionRow],
    summary: Mapping[str, Any],
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    temporary = output_root / f".{run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"A-class selection run already exists: {destination}")
    temporary.mkdir()
    try:
        fieldnames = list(AClassSelectionRow.__dataclass_fields__)
        generated_at = datetime.now(timezone.utc)
        published_at = summary.get("published_at_utc")
        if published_at:
            try:
                generated_at = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            except ValueError:
                pass
        timestamped_csv_name = f"a_class_candidates_{generated_at.astimezone().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = temporary / "candidates.csv"
        timestamped_csv_path = temporary / timestamped_csv_name
        for output_path in (csv_path, timestamped_csv_path):
            with output_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(asdict(row))
        (temporary / "candidates.json").write_text(
            json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2, allow_nan=False) + "\n",
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
            "schema_version": SCHEMA_VERSION,
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


def run_a_class_selection(
    *,
    data_root: Path,
    config_path: Path,
    output_root: Path,
    as_of: date | None = None,
    run_id: str | None = None,
    progress: Callable[[int, int, int], None] | None = None,
) -> AClassSelectionResult:
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

    selected: list[AClassSelectionRow] = []
    failures: Counter[str] = Counter()
    evaluated_count = 0
    for code in codes:
        try:
            records = load_stock_records(code, data_root)
            row = evaluate_a_class_stock(code, records, config, as_of)
            evaluated_count += 1
            if row is not None:
                selected.append(row)
        except DataValidationError as exc:
            failures[exc.code] += 1
        except Exception:
            failures["unexpected_error"] += 1
        done = evaluated_count + sum(failures.values())
        if progress is not None and (done == len(codes) or done % 500 == 0):
            progress(done, len(codes), len(selected))

    selected.sort(key=lambda row: (
        row.range_position_60d_pct,
        abs(row.volume_ratio_20 - 1.8),
        -row.close_location,
        -row.amount_cny,
        row.code,
    ))
    actual_run_id = run_id or f"a-class-select-{as_of.isoformat()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "run_id": actual_run_id,
        "signal_date": as_of.isoformat(),
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_code_count": len(codes),
        "evaluated_code_count": evaluated_count,
        "rejected_data_count": int(sum(failures.values())),
        "candidate_count": len(selected),
        "error_counts": dict(sorted(failures.items())),
        "quantity_conservation_valid": evaluated_count + sum(failures.values()) == len(codes),
        "selection_rule": SELECTION_RULE,
        "review_order": "range_position_60d_asc_volume_ratio_near_1p8_close_location_desc_amount_cny_desc_code_asc",
        "validation_summary": {
            "historical_validation": "not_run_in_selection_command",
            "expected_validator": "scripts/evaluate_a_class_target_touch.py",
            "read_only": True,
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
            "first_version_thresholds_not_promoted_until_validation",
        ],
    }
    directory = _atomic_publish(output_root, actual_run_id, selected, summary)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return AClassSelectionResult(
        run_directory=directory,
        candidates_path=directory / "candidates.csv",
        timestamped_candidates_path=directory / manifest["timestamped_candidates_csv"],
        candidates_json_path=directory / "candidates.json",
        summary_path=directory / "summary.json",
        manifest_path=directory / "manifest.json",
        signal_date=as_of,
        candidate_count=len(selected),
    )
