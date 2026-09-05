#!/usr/bin/env python3
"""Export scanner candidate CSV rows into a Markdown prompt pack for web AI review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import select as select_module
import shutil
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_ROOT = Path(".runtime/web-ai-prompts")
MKF_SELECTION_SCHEMA_PREFIX = "ncn_mkf_candidate_selector"

IDENTITY_FIELDS = (
    "code",
    "name",
    "stock_name",
    "signal_date",
    "cross_date",
    "post_cross_lag",
    "rank",
)

PRIORITY_FIELDS = (
    "research_close",
    "amount_cny",
    "turn_pct",
    "smc_gap_pct",
    "ema20",
    "ema50",
    "mkf_momentum",
    "mkf_inter",
    "mkf_near",
    "mkf_red_cross_up_20",
    "mkf_blue_cross_up_20",
    "mkf_red_blue_cross_up_20_under_80",
    "selection_reason",
    "risk_warning_count",
    "risk_warnings",
    "start_diagnostic_label",
    "start_diagnostic_reason",
    "range_position_20d_pct",
    "range_position_60d_pct",
    "range_position_120d_pct",
    "prior_return_20d_pct",
    "current_return_20d_pct",
    "distance_to_high_60d_pct",
    "recent_pullback_from_high_pct",
    "volume_ratio_20",
    "watch_stage",
    "cnstock_pool",
    "start_signal_count",
    "discovery_score",
    "pct_chg",
    "ret_5d",
    "start_signals",
    "pmk_trend_reason",
    "pmk_shape_pattern",
    "candle_confirm_reason",
)

DEFAULT_MAX_MARKDOWN_BYTES = 4000



@dataclass(frozen=True)
class CsvChoice:
    path: Path
    run_directory: Path
    label: str
    candidate_count: int | None = None
    is_default: bool = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an NCN scanner candidate CSV into a Markdown pack for manual upload to web AI tools."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        help="Scanner candidate CSV path, for example candidates.csv or mkf_candidates_*.csv",
    )
    parser.add_argument("--output", type=Path, help="Exact Markdown output path")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Markdown output directory when --output is not set")
    parser.add_argument("--mkf-selection-root", type=Path, help="MKF candidate selection root containing mkf-select-* runs")
    parser.add_argument("--latest", action="store_true", help="Use the latest MKF candidate CSV from --mkf-selection-root")
    parser.add_argument("--select", action="store_true", help="Interactively select an MKF candidate CSV from --mkf-selection-root")
    parser.add_argument("--top", type=int, default=None, help="Only include the first N CSV rows")
    parser.add_argument("--title", default="A股候选短线决策表", help="Markdown title")
    parser.add_argument("--as-of", default=None, help="Optional analysis date label, YYYY-MM-DD or free text")
    parser.add_argument("--max-field-chars", type=int, default=500, help="Maximum characters kept for any single CSV field")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_MARKDOWN_BYTES, help="Maximum UTF-8 bytes for the generated Markdown")
    args = parser.parse_args(argv)
    if args.top is not None and args.top < 1:
        parser.error("--top must be at least 1")
    if args.max_field_chars < 40:
        parser.error("--max-field-chars must be at least 40")
    if args.max_bytes < 1000:
        parser.error("--max-bytes must be at least 1000")
    if args.csv_path is None and args.mkf_selection_root is None:
        parser.error("csv_path or --mkf-selection-root is required")
    if args.csv_path is not None and (args.latest or args.select):
        parser.error("--latest/--select cannot be used with an explicit csv_path")
    return args


def read_rows(path: Path, top: int | None = None) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({key: value or "" for key, value in row.items() if key is not None})
            if top is not None and len(rows) >= top:
                break
    return list(reader.fieldnames), rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def is_valid_mkf_run(run_directory: Path) -> bool:
    if not run_directory.is_dir():
        return False
    if not (run_directory / "manifest.json").is_file():
        return False
    if not (run_directory / "candidates.json").is_file():
        return False
    manifest = load_json_if_exists(run_directory / "manifest.json")
    schema = str(manifest.get("schema_version", ""))
    return schema == "" or schema.startswith(MKF_SELECTION_SCHEMA_PREFIX)


def discover_mkf_csv_choices(selection_root: Path) -> list[CsvChoice]:
    runs = sorted(
        (path for path in selection_root.glob("mkf-select-*") if is_valid_mkf_run(path)),
        key=lambda path: path.name,
        reverse=True,
    )
    if not runs:
        return []

    choices: list[CsvChoice] = []
    seen: set[Path] = set()
    default_path: Path | None = None
    latest_run = runs[0]

    for run in runs:
        manifest = load_json_if_exists(run / "manifest.json")
        summary = load_json_if_exists(run / "summary.json")
        candidate_count = parse_int(summary.get("candidate_count"))
        csv_paths: list[Path] = []
        timestamped_name = manifest.get("timestamped_candidates_csv")
        if isinstance(timestamped_name, str) and "/" not in timestamped_name and "\\" not in timestamped_name:
            timestamped_path = run / timestamped_name
            if timestamped_path.is_file():
                csv_paths.append(timestamped_path)
        candidates_path = run / "candidates.csv"
        if candidates_path.is_file():
            csv_paths.append(candidates_path)
        csv_paths.extend(sorted(path for path in run.glob("*.csv") if path.is_file()))

        if run == latest_run:
            default_path = csv_paths[0] if csv_paths else None

        for csv_path in csv_paths:
            resolved = csv_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            count_label = f" 候选数={candidate_count}" if candidate_count is not None else ""
            marker = "[最新默认] " if csv_path == default_path else ""
            choices.append(CsvChoice(
                path=csv_path,
                run_directory=run,
                label=f"{marker}{run.name} / {csv_path.name}{count_label}",
                candidate_count=candidate_count,
                is_default=csv_path == default_path,
            ))

    return choices


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def default_choice_index(choices: list[CsvChoice]) -> int:
    for index, choice in enumerate(choices):
        if choice.is_default:
            return index
    return 0


def select_csv_interactively(choices: list[CsvChoice]) -> Path | None:
    if not choices:
        raise FileNotFoundError("no MKF candidate CSV files were found")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return choices[default_choice_index(choices)].path

    selected = default_choice_index(choices)
    input_fd = sys.stdin.fileno()
    original_attrs = termios.tcgetattr(input_fd)
    try:
        tty.setraw(input_fd)
        while True:
            render_csv_choices(choices, selected)
            key = read_key(input_fd)
            if key == "ctrl_c":
                raise KeyboardInterrupt
            if key in ("up", "shift_tab"):
                selected = (selected - 1) % len(choices)
                continue
            if key in ("down", "tab"):
                selected = (selected + 1) % len(choices)
                continue
            if key == "enter":
                return choices[selected].path
            if key in ("q", "Q", "esc"):
                return None
    finally:
        termios.tcsetattr(input_fd, termios.TCSADRAIN, original_attrs)
        write_tty("\033[2J\033[H")


def read_key(input_fd: int) -> str:
    first = os.read(input_fd, 1)
    if first == b"\x03":
        return "ctrl_c"
    if first in (b"\r", b"\n"):
        return "enter"
    if first == b"\t":
        return "tab"
    if first in (b"q", b"Q"):
        return first.decode("ascii")
    if first != b"\x1b":
        try:
            return first.decode("utf-8")
        except UnicodeDecodeError:
            return "unknown"

    sequence = read_escape_sequence(input_fd)
    if sequence in (b"[A", b"OA"):
        return "up"
    if sequence in (b"[B", b"OB"):
        return "down"
    if sequence == b"[Z":
        return "shift_tab"
    if sequence:
        return "unknown"
    return "esc"


def read_escape_sequence(input_fd: int) -> bytes:
    sequence = b""
    for _ in range(2):
        ready, _, _ = select_module.select([input_fd], [], [], 0.2)
        if not ready:
            break
        try:
            sequence += os.read(input_fd, 1)
        except OSError:
            break
    return sequence


def render_csv_choices(choices: list[CsvChoice], selected: int) -> None:
    terminal_size = shutil.get_terminal_size(fallback=(100, 24))
    visible_rows = max(5, terminal_size.lines - 5)
    start = max(0, min(selected - visible_rows // 2, len(choices) - visible_rows))
    end = min(len(choices), start + visible_rows)
    width = max(40, terminal_size.columns)

    write_tty("\033[2J\033[H")
    write_tty("选择要导出的 CSV\r\n")
    write_tty("使用 ↑/↓ 选择，回车导出，q/Esc 取消\r\n")
    write_tty(f"共 {len(choices)} 个文件，当前 {selected + 1}/{len(choices)}\r\n\r\n")
    for index in range(start, end):
        choice = choices[index]
        prefix = "  > " if index == selected else "    "
        line = truncate_display_line(f"{prefix}{choice.label}", width)
        if index == selected:
            write_tty(f"\033[7m{line}\033[0m\r\n")
        else:
            write_tty(f"{line}\r\n")


def truncate_display_line(line: str, width: int) -> str:
    if len(line) <= width - 1:
        return line
    return line[: max(1, width - 2)] + "…"


def write_tty(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def resolve_input_csv(args: argparse.Namespace) -> Path | None:
    if args.csv_path is not None:
        return args.csv_path
    assert args.mkf_selection_root is not None
    choices = discover_mkf_csv_choices(args.mkf_selection_root)
    if not choices:
        raise FileNotFoundError(f"no valid MKF candidate CSV found under {args.mkf_selection_root}")
    if args.select:
        return select_csv_interactively(choices)
    return choices[default_choice_index(choices)].path


def sanitize_output_stem(stem: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", stem.strip())
    value = value.strip("._")
    return value or "scan_csv"


def unique_timestamped_output_path(csv_path: Path, output_root: Path, stamp: str | None = None) -> Path:
    actual_stamp = stamp or datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    base = f"{sanitize_output_stem(csv_path.stem)}_web_ai_prompt_{actual_stamp}"
    candidate = output_root / f"{base}.md"
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = output_root / f"{base}_{index:02d}.md"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many output filename conflicts under {output_root}: {base}_NN.md")


def output_path_for(csv_path: Path, output: Path | None, output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    if output is not None:
        return output
    return unique_timestamped_output_path(csv_path, output_root)


def ordered_fields(fieldnames: list[str]) -> list[str]:
    selected: list[str] = []
    for field in (*IDENTITY_FIELDS, *PRIORITY_FIELDS):
        if field in fieldnames and field not in selected:
            selected.append(field)
    for field in fieldnames:
        if field not in selected:
            selected.append(field)
    return selected


def truncate_value(value: Any, max_chars: int) -> str:
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def row_label(row: dict[str, str], index: int) -> str:
    code = row.get("code", "").strip()
    name = (row.get("name") or row.get("stock_name") or "").strip()
    if code and name:
        return f"{index}. {code} {name}"
    if code:
        return f"{index}. {code}"
    return f"{index}. CSV第{index}行"


def markdown_table(rows: list[dict[str, str]], fields: list[str], max_field_chars: int) -> str:
    if not rows:
        return "无候选行。\n"
    header = "| " + " | ".join(fields) + " |"
    separator = "| " + " | ".join("---" for _ in fields) + " |"
    body = []
    for row in rows:
        values = [escape_table_cell(truncate_value(row.get(field, ""), max_field_chars)) for field in fields]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body]) + "\n"


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def build_markdown(
    *,
    title: str,
    csv_path: Path,
    source_sha256: str,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    as_of: str | None,
    max_field_chars: int,
    max_bytes: int = DEFAULT_MAX_MARKDOWN_BYTES,
) -> str:
    del csv_path, source_sha256, fieldnames, as_of, max_field_chars
    return build_hold_observation_markdown(title=title, rows=rows, max_bytes=max_bytes)


def build_hold_observation_markdown(*, title: str, rows: list[dict[str, str]], max_bytes: int) -> str:
    candidates = candidate_labels(rows)
    prefix = "\n".join([
        f"# {title}",
        "",
        "你是一名A股短线/波段交易分析员，任务是为未来1-10个交易日生成直接可比较的交易决策表。",
        "请通过互联网检索并交叉核验每只股票的最新公开信息后再下结论，不要只凭股票代码、简称或模型记忆判断。",
        "每只股票必须给明确结论，且只能从：买入 / 继续持有 / 减仓观察 / 卖出或回避 中选择；不要把任务改成长线价值投资或公司基本面长篇介绍。",
        "",
        "重点查：公告/财报/业绩预告、监管处罚、ST/退市风险、减持/解禁、重大诉讼、异常波动、行业景气度、题材持续性、近期价格和成交量。",
        "我的交易计划是止盈约4%、止损约3%；目标价按最新可查价格上方约4%测算，止损价按下方约3%测算。不适合该盈亏比、短线空间不足或风险事件过重的股票，请降级为减仓观察或卖出/回避。",
        "关键判断必须附可访问来源链接和信息发布日期；查不到可靠信息时写“信息不足”，不要编造公告、链接、日期或价格。",
        "",
        "候选股票：",
    ])
    suffix = "\n输出表格：|代码|简称|最新价/日期|结论|目标价|止损价|仓位|核心驱动|否决风险|来源链接|\n最后按优先级分组：更值得买入 / 继续持有 / 减仓观察 / 卖出或回避；每组给一句理由。\n"
    kept: list[str] = []
    for candidate_label in candidates:
        candidate = "\n".join([*kept, candidate_label])
        if utf8_len(prefix + "\n" + candidate + "\n" + suffix) > max_bytes:
            break
        kept.append(candidate_label)
    return prefix + "\n" + "\n".join(kept) + "\n" + suffix


def candidate_labels(rows: list[dict[str, str]]) -> list[str]:
    labels: list[str] = []
    for row in rows:
        code = row.get("code", "").strip()
        if not code:
            continue
        name = (row.get("name") or row.get("stock_name") or "").strip()
        labels.append(f"{code} {name}" if name else code)
    return labels


def utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def infer_analysis_date(rows: list[dict[str, str]]) -> str | None:
    for key in ("signal_date", "date", "trade_date", "as_of", "cross_date"):
        values = sorted({row.get(key, "").strip() for row in rows if row.get(key, "").strip()})
        if len(values) == 1:
            return values[0]
    return None


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        csv_path = resolve_input_csv(args)
        if csv_path is None:
            print("status=cancelled")
            return 0
        fieldnames, rows = read_rows(csv_path, args.top)
        destination = output_path_for(csv_path, args.output, args.output_root)
        content = build_markdown(
            title=args.title,
            csv_path=csv_path,
            source_sha256=sha256_file(csv_path),
            fieldnames=fieldnames,
            rows=rows,
            as_of=args.as_of,
            max_field_chars=args.max_field_chars,
            max_bytes=args.max_bytes,
        )
        write_markdown(destination, content)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"source_csv={csv_path}")
    print(f"web_ai_prompt_md={destination}")
    print(f"candidate_rows={len(rows)}")
    print("research_only=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
