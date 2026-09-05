from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_scan_csv_for_web_ai.py"
SPEC = importlib.util.spec_from_file_location("export_scan_csv_for_web_ai", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_csv(path: Path, code: str = "sh.600001") -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "code",
                "signal_date",
                "cross_date",
                "post_cross_lag",
                "research_close",
                "amount_cny",
                "mkf_momentum",
                "mkf_inter",
                "mkf_near",
                "selection_reason",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "code": code,
            "signal_date": "2026-08-28",
            "cross_date": "2026-08-26",
            "post_cross_lag": "2",
            "research_close": "10.25",
            "amount_cny": "200000000",
            "mkf_momentum": "35.0",
            "mkf_inter": "30.0",
            "mkf_near": "40.0",
            "selection_reason": "mkf_red_blue_cross20_post_lag0_lag1_lag2_v5_and_existing_hard_gates",
        })


def _mkf_run(root: Path, run_id: str, *, timestamped_name: str, candidate_count: int = 1) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    _write_csv(run / "candidates.csv")
    _write_csv(run / timestamped_name)
    (run / "candidates.json").write_text("[]\n", encoding="utf-8")
    (run / "summary.json").write_text(json.dumps({"candidate_count": candidate_count}), encoding="utf-8")
    (run / "manifest.json").write_text(
        json.dumps({
            "schema_version": "ncn_mkf_candidate_selector_v5",
            "timestamped_candidates_csv": timestamped_name,
        }),
        encoding="utf-8",
    )
    return run


def test_builds_web_ai_markdown_prompt_from_scanner_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "candidates.csv"
    output_path = tmp_path / "web-ai.md"
    _write_csv(csv_path)

    exit_code = MODULE.main([str(csv_path), "--output", str(output_path), "--top", "1"])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "# A股候选短线决策表" in content
    assert "A股短线/波段交易分析员" in content
    assert "生成直接可比较的交易决策表" in content
    assert "通过互联网检索并交叉核验" in content
    assert "不要只凭股票代码、简称或模型记忆判断" in content
    assert "不要把任务改成长线价值投资" in content
    assert "买入 / 继续持有 / 减仓观察 / 卖出或回避" in content
    assert "止盈约4%、止损约3%" in content
    assert "目标价按最新可查价格上方约4%测算" in content
    assert "止损价按下方约3%测算" in content
    assert "不适合该盈亏比、短线空间不足或风险事件过重" in content
    assert "关键判断必须附可访问来源链接和信息发布日期" in content
    assert "输出表格：|代码|简称|最新价/日期|结论|目标价|止损价|仓位|核心驱动|否决风险|来源链接|" in content
    assert "sh.600001" in content
    assert "NCN" not in content
    assert "MKF" not in content
    assert "扫描日期" not in content
    assert "cross" not in content
    assert "lag" not in content
    assert "mom" not in content
    assert "源 CSV SHA256" not in content
    assert "source_path" not in content
    assert "```json" not in content
    assert len(content.encode("utf-8")) <= 4000



def test_candidate_stock_list_includes_names_when_available(tmp_path: Path) -> None:
    csv_path = tmp_path / "named_candidates.csv"
    output_path = tmp_path / "web-ai.md"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["code", "name", "stock_name"])
        writer.writeheader()
        writer.writerow({"code": "sh.600600", "name": "青岛啤酒", "stock_name": ""})
        writer.writerow({"code": "sz.001289", "name": "", "stock_name": "龙源电力"})

    exit_code = MODULE.main([str(csv_path), "--output", str(output_path)])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert "sh.600600 青岛啤酒" in content
    assert "sz.001289 龙源电力" in content


def test_default_markdown_stays_under_4000_bytes_for_mkf_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "mkf_candidates.csv"
    output_path = tmp_path / "web-ai.md"
    fieldnames = [
        "code",
        "signal_date",
        "cross_date",
        "post_cross_lag",
        "research_close",
        "amount_cny",
        "turn_pct",
        "mkf_momentum",
        "mkf_inter",
        "mkf_near",
        "source_path",
        "research_only",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(16):
            writer.writerow({
                "code": f"sh.605{index:03d}",
                "signal_date": "2026-09-01",
                "cross_date": "2026-08-31",
                "post_cross_lag": str(index % 6),
                "research_close": "8.29",
                "amount_cny": "60958630.69",
                "turn_pct": "1.3148",
                "mkf_momentum": "52.307692307692186",
                "mkf_inter": "13.374881714750988",
                "mkf_near": "30.116199589883742",
                "source_path": f"/private/project/PFrontStockData/sh.605{index:03d}.parquet",
                "research_only": "True",
            })

    exit_code = MODULE.main([str(csv_path), "--output", str(output_path)])

    assert exit_code == 0
    content = output_path.read_text(encoding="utf-8")
    assert len(content.encode("utf-8")) <= 4000
    assert "sh.605000" in content
    assert "sh.605015" in content
    assert "source_path" not in content
    assert "PFrontStockData" not in content
    assert "signal_date" not in content
    assert "cross_date" not in content
    assert "post_cross_lag" not in content
    assert "mkf_momentum" not in content
    assert "```json" not in content



def test_top_limit_keeps_only_requested_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "candidates.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["code", "signal_date", "research_close"])
        writer.writeheader()
        writer.writerow({"code": "sh.600001", "signal_date": "2026-08-28", "research_close": "10.25"})
        writer.writerow({"code": "sz.000001", "signal_date": "2026-08-28", "research_close": "12.50"})

    rows = MODULE.read_rows(csv_path, top=1)[1]
    markdown = MODULE.build_markdown(
        title="测试",
        csv_path=csv_path,
        source_sha256=MODULE.sha256_file(csv_path),
        fieldnames=["code", "signal_date", "research_close"],
        rows=rows,
        as_of=None,
        max_field_chars=500,
    )

    assert "sh.600001" in markdown
    assert "sz.000001" not in markdown
    assert "未来1-10个交易日" in markdown
    assert "目标价" in markdown
    assert "止损价" in markdown
    assert "仓位" in markdown
    assert "扫描日期" not in markdown


def test_output_root_uses_csv_name_and_creation_time(tmp_path: Path) -> None:
    csv_path = tmp_path / "mkf_candidates_20260901_210326.csv"
    output_root = tmp_path / "mdfile"
    _write_csv(csv_path)

    output_path = MODULE.output_path_for(csv_path, None, output_root)

    assert output_path.parent == output_root
    assert output_path.name.startswith("mkf_candidates_20260901_210326_web_ai_prompt_")
    assert output_path.suffix == ".md"


def test_unique_output_path_avoids_overwrite(tmp_path: Path) -> None:
    csv_path = tmp_path / "candidates.csv"
    output_root = tmp_path / "mdfile"
    output_root.mkdir()
    first = output_root / "candidates_web_ai_prompt_20260901_210000.md"
    first.write_text("exists", encoding="utf-8")

    second = MODULE.unique_timestamped_output_path(csv_path, output_root, stamp="20260901_210000")

    assert second.name == "candidates_web_ai_prompt_20260901_210000_01.md"


def test_discovers_mkf_csv_choices_with_latest_timestamped_default(tmp_path: Path) -> None:
    root = tmp_path / "mkf_candidate_selections"
    _mkf_run(root, "mkf-select-20260831_100000", timestamped_name="mkf_candidates_20260831_100000.csv", candidate_count=2)
    latest = _mkf_run(root, "mkf-select-20260901_210147", timestamped_name="mkf_candidates_20260901_210326.csv", candidate_count=16)

    choices = MODULE.discover_mkf_csv_choices(root)

    assert choices[0].path == latest / "mkf_candidates_20260901_210326.csv"
    assert choices[0].is_default is True
    assert choices[0].candidate_count == 16
    assert any(choice.path.name == "candidates.csv" and choice.run_directory == latest for choice in choices)


def test_latest_mkf_selection_generates_markdown_under_output_root(tmp_path: Path) -> None:
    root = tmp_path / "mkf_candidate_selections"
    output_root = tmp_path / "mdfile"
    _mkf_run(root, "mkf-select-20260901_210147", timestamped_name="mkf_candidates_20260901_210326.csv")

    exit_code = MODULE.main(["--mkf-selection-root", str(root), "--latest", "--output-root", str(output_root), "--top", "1"])

    assert exit_code == 0
    outputs = list(output_root.glob("mkf_candidates_20260901_210326_web_ai_prompt_*.md"))
    assert len(outputs) == 1
    assert "sh.600001" in outputs[0].read_text(encoding="utf-8")


def test_read_key_maps_arrow_bytes_without_treating_them_as_escape() -> None:
    read_fd, write_fd = MODULE.os.pipe()
    try:
        MODULE.os.write(write_fd, b"\x1b[B")
        assert MODULE.read_key(read_fd) == "down"
        MODULE.os.write(write_fd, b"\x1b[A")
        assert MODULE.read_key(read_fd) == "up"
        MODULE.os.write(write_fd, b"\r")
        assert MODULE.read_key(read_fd) == "enter"
    finally:
        MODULE.os.close(read_fd)
        MODULE.os.close(write_fd)



def test_csv_choice_renderer_uses_crlf_and_limits_visible_rows() -> None:
    choices = [
        MODULE.CsvChoice(
            path=Path(f"/tmp/run-{index}/candidates.csv"),
            run_directory=Path(f"/tmp/run-{index}"),
            label=f"mkf-select-20260901_{index:06d} / candidates.csv 候选数=49",
        )
        for index in range(30)
    ]
    rendered: list[str] = []

    with mock.patch.object(MODULE.shutil, "get_terminal_size", return_value=MODULE.shutil.os.terminal_size((80, 10))):
        with mock.patch.object(MODULE, "write_tty", side_effect=rendered.append):
            MODULE.render_csv_choices(choices, selected=15)

    text = "".join(rendered)
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")
    assert "当前 16/30" in text
    assert "mkf-select-20260901_000015" in text
    assert "mkf-select-20260901_000000" not in text



def test_latest_mkf_selection_returns_error_when_no_valid_run(tmp_path: Path) -> None:
    exit_code = MODULE.main(["--mkf-selection-root", str(tmp_path), "--latest", "--output-root", str(tmp_path / "mdfile")])

    assert exit_code == 2
