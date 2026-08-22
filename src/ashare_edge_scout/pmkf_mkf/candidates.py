"""Read-only MKF red/blue cross candidate-source experiment."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import compute_config_sha256, load_config, validate_config
from ..data.daily_bars import DataValidationError
from ..data.data_sources import get_parquet_codes, get_parquet_latest_date_coverage, load_stock_records
from .research import mkf_red_blue_cross20_lines, mkf_red_blue_cross20_under80_mask
from ..research_precision70 import production_gate_mask
from ..stock_selector import _safe_float

SCHEMA_VERSION = "ncn_mkf_candidate_selector_v1"
SELECTION_RULE = "mkf_red_blue_cross20_under80_v1_and_existing_hard_gates"


@dataclass(frozen=True)
class MkfCandidateRow:
    code: str
    signal_date: str
    research_close: float
    amount_cny: float
    turn_pct: float
    mkf_momentum: float
    mkf_inter: float
    mkf_near: float
    mkf_red_cross_up_20: bool
    mkf_blue_cross_up_20: bool
    mkf_red_blue_cross_up_20_under_80: bool
    source_path: str
    selection_reason: str = SELECTION_RULE
    research_only: bool = True


@dataclass(frozen=True)
class MkfSelectionResult:
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


def _normalise_frame(records: Sequence[Mapping[str, Any]], as_of: date) -> pd.DataFrame:
    data = pd.DataFrame(records)
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
    return data.loc[data["date"].le(pd.Timestamp(as_of))].copy().reset_index(drop=True)


def _cross_components(lines: pd.DataFrame, frame: pd.DataFrame, row_index: int) -> tuple[bool, bool]:
    trading = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    tradable_indexes = list(frame.index[trading])
    if row_index not in tradable_indexes:
        return False, False
    position = tradable_indexes.index(row_index)
    if position == 0:
        return False, False
    prior_index = tradable_indexes[position - 1]
    prior = lines.loc[prior_index]
    current = lines.loc[row_index]
    red = bool(pd.notna(prior.get("momentum")) and pd.notna(current.get("momentum")) and prior.get("momentum") < 20.0 <= current.get("momentum"))
    blue = bool(pd.notna(prior.get("near")) and pd.notna(current.get("near")) and prior.get("near") < 20.0 <= current.get("near"))
    return red, blue


def _config_with_min_adv20(config: Mapping[str, Any], min_adv20_cny: float | None) -> Mapping[str, Any]:
    if min_adv20_cny is None:
        return config
    adjusted = copy.deepcopy(dict(config))
    universe = dict(adjusted.get("universe", {}))
    universe["min_adv20_cny"] = float(min_adv20_cny)
    adjusted["universe"] = universe
    return adjusted


def evaluate_mkf_candidate_stock(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    as_of: date,
    *,
    source_path: Path | None = None,
    min_adv20_cny: float | None = None,
) -> MkfCandidateRow | None:
    data = _normalise_frame(records, as_of)
    if data.empty or data.iloc[-1]["date"] != pd.Timestamp(as_of):
        return None

    row_index = data.index[-1]
    gate_config = _config_with_min_adv20(config, min_adv20_cny)
    admitted = production_gate_mask(code, data, gate_config)
    if row_index not in admitted.index or not bool(admitted.loc[row_index]):
        return None

    signal = mkf_red_blue_cross20_under80_mask(data)
    if row_index not in signal.index or not bool(signal.loc[row_index]):
        return None

    lines = mkf_red_blue_cross20_lines(data)
    current = lines.loc[row_index]
    red_cross, blue_cross = _cross_components(lines, data, row_index)
    latest = data.loc[row_index]
    return MkfCandidateRow(
        code=code,
        signal_date=as_of.isoformat(),
        research_close=_safe_float(latest.get("close"), 0.0),
        amount_cny=_safe_float(latest.get("amount"), 0.0),
        turn_pct=_safe_float(latest.get("turn"), 0.0),
        mkf_momentum=_safe_float(current.get("momentum"), 0.0),
        mkf_inter=_safe_float(current.get("inter"), 0.0),
        mkf_near=_safe_float(current.get("near"), 0.0),
        mkf_red_cross_up_20=red_cross,
        mkf_blue_cross_up_20=blue_cross,
        mkf_red_blue_cross_up_20_under_80=True,
        source_path=str(source_path or ""),
    )


def _atomic_publish(
    output_root: Path,
    run_id: str,
    rows: Sequence[MkfCandidateRow],
    summary: Mapping[str, Any],
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    temporary = output_root / f".{run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"MKF candidate selection run already exists: {destination}")
    temporary.mkdir()
    try:
        generated_at = datetime.now(timezone.utc)
        published_at = summary.get("published_at_utc")
        if published_at:
            try:
                generated_at = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            except ValueError:
                pass
        timestamped_csv_name = f"mkf_candidates_{generated_at.astimezone().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = temporary / "candidates.csv"
        timestamped_csv_path = temporary / timestamped_csv_name
        fieldnames = list(MkfCandidateRow.__dataclass_fields__)
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
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def run_mkf_candidate_selection(
    *,
    data_root: Path,
    config_path: Path,
    output_root: Path,
    as_of: date | None = None,
    run_id: str | None = None,
    min_adv20_cny: float | None = None,
    selection_profile: str = "standard",
    progress: Callable[[int, int, int], None] | None = None,
) -> MkfSelectionResult:
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

    selected: list[MkfCandidateRow] = []
    failures: Counter[str] = Counter()
    evaluated_count = 0
    for code in codes:
        try:
            records = load_stock_records(code, data_root)
            row = evaluate_mkf_candidate_stock(
                code,
                records,
                config,
                as_of,
                source_path=data_root / f"{code}.parquet",
                min_adv20_cny=min_adv20_cny,
            )
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

    selected.sort(key=lambda row: (-row.amount_cny, row.code))
    actual_run_id = run_id or f"mkf-select-{as_of.isoformat()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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
        "selection_profile": selection_profile,
        "effective_min_adv20_cny": float(min_adv20_cny) if min_adv20_cny is not None else float((config.get("universe") or {}).get("min_adv20_cny", 0.0)),
        "review_order": "amount_cny_desc_code_asc",
        "validation_summary": {
            "historical_validation": "not_run_in_selection_command",
            "read_only": True,
            "expected_future_validator": "separate_pre_registered_mkf_candidate_source_validation_required",
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
            "smc_admission_modified": False,
            "smc_ranking_modified": False,
            "watchlist_modified": False,
            "prospective_archive_modified": False,
        },
        "limitations": [
            "adjusted_research_daily_bars",
            "current_file_survivorship",
            "no_fill_or_execution_evidence",
            "candidate_not_investment_advice",
            "mkf_candidate_source_not_promoted_until_separate_validation",
        ],
    }
    directory = _atomic_publish(output_root, actual_run_id, selected, summary)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    return MkfSelectionResult(
        run_directory=directory,
        candidates_path=directory / "candidates.csv",
        timestamped_candidates_path=directory / manifest["timestamped_candidates_csv"],
        candidates_json_path=directory / "candidates.json",
        summary_path=directory / "summary.json",
        manifest_path=directory / "manifest.json",
        signal_date=as_of,
        candidate_count=len(selected),
    )
