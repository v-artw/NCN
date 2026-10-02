#!/usr/bin/env python3
"""Compare MKF-arm vs SMC-arm lag-grid reports (same method, same window, targets 3/4)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

GATE_N, GATE_DATES, GATE_CODES = 300, 120, 50
LAGS = range(0, 6)
HORIZONS = range(1, 21)
TARGETS = ("target_3pct", "target_4pct")


def cell(report: dict[str, Any], variant: str, lag: int, period: str, horizon: int, target: str) -> dict[str, Any]:
    return report["variant_metrics"][variant]["grid_metrics"][str(lag)][period][f"T+{horizon}"][target]


def gated(c: dict[str, Any]) -> bool:
    return c["n"] >= GATE_N and c["entry_dates"] >= GATE_DATES and c["codes"] >= GATE_CODES


def best_gated(report: dict[str, Any], variant: str, period: str, target: str) -> tuple[int, int, dict[str, Any]] | None:
    best = None
    for lag in LAGS:
        for horizon in HORIZONS:
            c = cell(report, variant, lag, period, horizon, target)
            if c["n"] and gated(c) and (best is None or c["target_hit_wilson_lower_95"] > best[2]["target_hit_wilson_lower_95"]):
                best = (lag, horizon, c)
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mkf", type=Path, required=True)
    parser.add_argument("--smc", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    mkf = json.loads(args.mkf.read_text(encoding="utf-8"))
    smc = json.loads(args.smc.read_text(encoding="utf-8"))

    # full cell-level diff table (baseline, full_period)
    rows: list[dict[str, Any]] = []
    smc_wins = smc_loses = ties = gated_smc_wins = gated_total = 0
    for lag in LAGS:
        for horizon in HORIZONS:
            for target in TARGETS:
                cm = cell(mkf, "baseline", lag, "full_period", horizon, target)
                cs = cell(smc, "baseline", lag, "full_period", horizon, target)
                if not cm["n"] or not cs["n"]:
                    continue
                delta = (cs["target_hit_rate"] - cm["target_hit_rate"]) * 100
                rows.append(
                    {
                        "lag": lag,
                        "horizon": f"T+{horizon}",
                        "target": target,
                        "mkf_n": cm["n"],
                        "mkf_rate_pct": round(cm["target_hit_rate"] * 100, 4),
                        "mkf_wilson_low_pct": round(cm["target_hit_wilson_lower_95"] * 100, 4),
                        "smc_n": cs["n"],
                        "smc_rate_pct": round(cs["target_hit_rate"] * 100, 4),
                        "smc_wilson_low_pct": round(cs["target_hit_wilson_lower_95"] * 100, 4),
                        "smc_minus_mkf_pp": round(delta, 4),
                        "smc_gated": gated(cs),
                        "mkf_gated": gated(cm),
                    }
                )
                if abs(delta) < 1e-12:
                    ties += 1
                elif delta > 0:
                    smc_wins += 1
                else:
                    smc_loses += 1
                if gated(cs) and gated(cm):
                    gated_total += 1
                    if delta > 0:
                        gated_smc_wins += 1
    with args.out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def fmt(name: str, best: tuple[int, int, dict[str, Any]] | None) -> str:
        if best is None:
            return f"{name}: 无门槛内单元格"
        lag, horizon, c = best
        return (
            f"{name}: lag{lag} T+{horizon} n={c['n']} rate={c['target_hit_rate'] * 100:.2f}% "
            f"wilson_low={c['target_hit_wilson_lower_95'] * 100:.2f}% dates={c['entry_dates']} codes={c['codes']}"
        )

    lines: list[str] = []
    lines.append("# MKF vs SMC 同方法对比（2015-01-01 → 2026-09-22，全主板，lag0–5，目标3%/4%，T+1..T+20）\n")
    sm = mkf["sample"]
    ss = smc["sample"]
    lines.append(f"- MKF：父信号 {sm.get('parent_crosses', sm.get('parent_smc_signals'))}，事件 {sm['lag_events']}，状态 {sm['status_counts']}")
    lines.append(f"- SMC：父信号 {ss['parent_smc_signals']}，事件 {ss['lag_events']}，状态 {ss['status_counts']}")
    lines.append(f"- 单元格对比（baseline 全期，全部 {len(rows)} 格）：SMC 更高 {smc_wins} 格 / 更低 {smc_loses} 格 / 持平 {ties} 格")
    lines.append(f"- 双臂均过门槛的 {gated_total} 格中，SMC 更高 {gated_smc_wins} 格")
    lines.append("\n## 门槛内最优单元格（full_period）\n")
    for variant in ("baseline", "exclude_chop_ge_4"):
        for period in ("full_period", "audit_2024_present"):
            for target in TARGETS:
                lines.append(f"- {variant} | {period} | 3% ".replace("3%", target) + fmt("MKF", best_gated(mkf, variant, period, target)))
                lines.append(f"  {' ' * len(variant + ' | ' + period + ' | ' + target)}  SMC " + fmt("", best_gated(smc, variant, period, target)).lstrip(": "))
    lines.append("\n## 年度对比（lag0，T+10/T+20，3%，baseline）\n")
    years = sorted(k for k in mkf["variant_metrics"]["baseline"]["grid_metrics"]["0"] if k.startswith("year_"))
    lines.append("| 年度 | MKF T+10 | SMC T+10 | MKF T+20 | SMC T+20 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for y in years:
        m10 = cell(mkf, "baseline", 0, y, 10, "target_3pct")
        s10 = cell(smc, "baseline", 0, y, 10, "target_3pct")
        m20 = cell(mkf, "baseline", 0, y, 20, "target_3pct")
        s20 = cell(smc, "baseline", 0, y, 20, "target_3pct")
        f = lambda c: f"{c['target_hit_rate'] * 100:.1f}%(n={c['n']})" if c["n"] else "-"
        lines.append(f"| {y[5:]} | {f(m10)} | {f(s10)} | {f(m20)} | {f(s20)} |")
    lines.append("\n## 关键固定格（baseline 全期，lag0）\n")
    lines.append("| 格 | MKF | SMC | Δpp |")
    lines.append("| --- | --- | --- | --- |")
    for horizon in (1, 3, 5, 10, 15, 20):
        for target in TARGETS:
            cm = cell(mkf, "baseline", 0, "full_period", horizon, target)
            cs = cell(smc, "baseline", 0, "full_period", horizon, target)
            pct = "3%" if target == "target_3pct" else "4%"
            lines.append(
                f"| T+{horizon} {pct} | {cm['target_hit_rate'] * 100:.2f}% (n={cm['n']}) | {cs['target_hit_rate'] * 100:.2f}% (n={cs['n']}) | {(cs['target_hit_rate'] - cm['target_hit_rate']) * 100:+.2f} |"
            )
    lines.append("\n边界：只读研究对比；触及目标口径≠已实现收益；未建模费用/滑点/成交性；当前代码表存在幸存者偏差。")
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"compare=ok cells={len(rows)} md={args.out_md} csv={args.out_csv}")


if __name__ == "__main__":
    main()
