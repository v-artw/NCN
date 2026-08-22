"""PMKF/MKF route payloads for the NCN Web console."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from ...pmkf_mkf.core import apply_pmkf, compute_pmkf_slope
from ...pmkf_mkf.research import mkf_red_blue_cross20_lines

if TYPE_CHECKING:
    from ..app import ResearchWebContext, ResearchWebError


def pmkf_mkf_reports_payload(
    context: "ResearchWebContext",
    *,
    boundary_payload: Mapping[str, Any],
    read_json_object: Callable[[Path, str], dict[str, Any]],
    web_error: type["ResearchWebError"],
) -> dict[str, Any]:
    roots = [context.output_root / "mkf_candidate_selections", context.output_root / "mkf_ai_reviews"]
    reports: list[dict[str, Any]] = []
    for root in roots:
        for summary_path in sorted(root.glob("*/summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:5]:
            try:
                summary = read_json_object(summary_path, "PMKF/MKF summary")
            except web_error:
                continue
            reports.append({
                "run_id": summary.get("run_id") or summary_path.parent.name,
                "kind": root.name,
                "path": str(summary_path),
                "status": summary.get("status"),
                "candidate_count": summary.get("candidate_count") or summary.get("reviewed_count"),
                "signal_date": summary.get("signal_date"),
            })
    return {"schema_version": "ncn_pmkf_mkf_reports_v1", "reports": reports, **dict(boundary_payload)}


def pmkf_mkf_summary_payload(
    context: "ResearchWebContext",
    *,
    boundary_payload: Mapping[str, Any],
    read_json_object: Callable[[Path, str], dict[str, Any]],
    web_error: type["ResearchWebError"],
) -> dict[str, Any]:
    reports = pmkf_mkf_reports_payload(
        context,
        boundary_payload=boundary_payload,
        read_json_object=read_json_object,
        web_error=web_error,
    )["reports"]
    return {
        "schema_version": "ncn_pmkf_mkf_summary_v1",
        "report_count": len(reports),
        "latest_reports": reports[:5],
        "warnings": ["precomputed_reports_only", "no_all_universe_scan_in_web_request"],
        **dict(boundary_payload),
    }


def pmkf_mkf_code_payload(
    context: "ResearchWebContext",
    code: str,
    *,
    boundary_payload: Mapping[str, Any],
    normalize_code: Callable[[str], str],
    load_candle_payload: Callable[..., dict[str, Any]],
    web_error: type["ResearchWebError"],
) -> dict[str, Any]:
    normalized = normalize_code(code)
    records = load_local_ohlcv_records(context.data_root, normalized, limit=120, web_error=web_error)
    if len(records) < 30:
        raise web_error("insufficient_data", "PMKF/MKF 单代码分析至少需要 30 根日线")
    closes = [float(record["close"]) for record in records]
    pmkf_series = apply_pmkf(closes)
    frame = pd.DataFrame(records)
    lines = mkf_red_blue_cross20_lines(frame).tail(1)
    latest_lines = lines.iloc[-1].to_dict() if not lines.empty else {}
    warnings = ["bounded_single_code_only", "adjusted_research_data_only"]
    try:
        candle = load_candle_payload(context, normalized, limit=min(120, len(records)), period="1d")
        latest_alert = candle.get("research_alert")
    except web_error as exc:
        warnings.append(f"strict_candle_payload_unavailable:{exc.code}")
        latest_alert = {
            "state": "unavailable",
            "title": "严格蜡烛载荷不可用",
            "detail": "PMKF/MKF 单代码面板仍可读取 OHLCV；完整蜡烛研究需修复本地日线字段质量",
            "evidence": [exc.code],
            "research_only": True,
        }
    return {
        "schema_version": "ncn_pmkf_mkf_code_v1",
        "code": normalized,
        "bar_count": len(records),
        "pmkf_slope": compute_pmkf_slope(pmkf_series),
        "mkf_lines": {key: (None if pd.isna(value) else float(value)) for key, value in latest_lines.items()},
        "latest_research_alert": latest_alert,
        "provenance": {
            "provider": "local_baostock_parquet",
            "bar_limit": 120,
            "warnings": warnings,
        },
        **dict(boundary_payload),
    }


def load_local_ohlcv_records(
    data_root: Path,
    code: str,
    *,
    limit: int,
    web_error: type["ResearchWebError"],
) -> list[dict[str, Any]]:
    data_file = data_root / f"{code}.parquet"
    if data_file.is_symlink() or not data_file.is_file():
        raise web_error("data_file_missing", f"本地研究数据不存在: {data_file}")
    try:
        frame = pd.read_parquet(data_file, columns=["code", "date", "open", "high", "low", "close", "volume"])
    except Exception as exc:
        raise web_error("unreadable_parquet", f"无法读取本地研究数据: {data_file}") from exc
    if frame.empty:
        raise web_error("empty_daily_bars", "本地研究数据为空")
    frame = frame.loc[frame["code"].astype(str).eq(code)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date", kind="stable").drop_duplicates("date", keep="last").tail(limit)
    if frame.empty:
        raise web_error("empty_daily_bars", "本地研究 OHLCV 数据为空")
    frame["tradestatus"] = "1"
    return frame.to_dict("records")


__all__ = [
    "load_local_ohlcv_records",
    "pmkf_mkf_code_payload",
    "pmkf_mkf_reports_payload",
    "pmkf_mkf_summary_payload",
]
