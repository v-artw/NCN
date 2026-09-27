from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "Autobaostock_download.py"
SPEC = importlib.util.spec_from_file_location("autobaostock_download_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_download_summary_passes_below_failure_threshold() -> None:
    summary = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="2026-07-23",
        total=100,
        updated_count=10,
        failed_count=5,
        timeout_count=4,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )

    assert summary["status"] == "success"
    assert summary["failure_count"] == 9
    assert summary["failure_rate"] == pytest.approx(0.09)
    assert summary["incremental"] is True
    assert summary["clean_before_download"] is False


def test_download_summary_fails_above_threshold_and_on_zero_total() -> None:
    failed = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="2026-07-23",
        total=100,
        updated_count=0,
        failed_count=11,
        timeout_count=0,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )
    empty = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="",
        total=0,
        updated_count=0,
        failed_count=0,
        timeout_count=0,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )

    assert failed["status"] == "failed"
    assert empty["status"] == "failed"
    assert empty["failure_rate"] == 1.0


def test_write_summary_json_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "summary.json"
    module.write_summary_json(path, {"status": "success", "total": 10})

    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "success", "total": 10}
    assert not (path.parent / "summary.json.tmp").exists()


def test_parse_args_supports_stock_list_date_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--stock-list-date",
            "2026-07-23",
            "--max-failure-rate",
            "0.05",
            "--summary-json",
            str(tmp_path / "summary.json"),
            "--no-clean",
        ],
    )

    args = module.parse_args()

    assert args.stock_list_date == "2026-07-23"
    assert args.max_failure_rate == pytest.approx(0.05)
    assert args.summary_json.endswith("summary.json")
    assert args.no_clean is True
    assert args.clean is False


# ---------------------------------------------------------------------------
# 前复权自愈·重叠重写窗口（方案①）回归测试
# 背景：BaoStock 前复权是动态快照，除息后旧行被回补改写；纯追加增量永不重写历史，
# 造成机器间数据时点错位（600660 型差异）。窗口=每次重叠重下最近 N 行覆盖旧值。
# ---------------------------------------------------------------------------

def _consecutive_dates(n: int, start: str = "2026-01-01"):
    first = datetime.datetime.strptime(start, "%Y-%m-%d")
    return pd.Series(
        [(first + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]
    )


def test_overlap_self_heal_default_is_nonzero():
    # 默认窗口被清零 = 静默关闭自愈，回归门槛：必须保持默认开启
    assert module.DEFAULT_OVERLAP_BARS == 120
    assert module.DEFAULT_CONFIG["overlap_bars"] == module.DEFAULT_OVERLAP_BARS


def test_parse_args_overlap_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--overlap-bars", "0"])
    assert module.parse_args().overlap_bars == 0
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    # 未指定时保持 None，由配置文件/DEFAULT_CONFIG 决定
    assert module.parse_args().overlap_bars is None


def test_resolve_download_window_missing_data_falls_back_to_full_download() -> None:
    assert module.resolve_download_window(None, "2026-01-30", "2015-01-01", 120) == ("2015-01-01", False)
    empty = pd.Series([], dtype="datetime64[ns]")
    assert module.resolve_download_window(empty, "2026-01-30", "2015-01-01", 120) == ("2015-01-01", False)


def test_resolve_download_window_legacy_append_and_skip() -> None:
    dates = _consecutive_dates(12)  # 2026-01-01 .. 2026-01-12
    # overlap=0 旧行为：从最后日期+1 纯追加；已最新/超前则跳过
    assert module.resolve_download_window(dates, "2026-01-15", "2015-01-01", 0) == ("2026-01-13", True)
    assert module.resolve_download_window(dates, "2026-01-12", "2015-01-01", 0) == (None, False)
    assert module.resolve_download_window(dates, "2026-01-05", "2015-01-01", 0) == (None, False)


def test_resolve_download_window_overlap_rewrites_last_n_bars_and_appends() -> None:
    dates = _consecutive_dates(12)
    # 12 行、窗口 10 → 锚点为倒数第 11 行（2026-01-02），起点 2026-01-03：
    # 覆盖最近 10 行旧值 + 追加 01-13..01-15 新行
    assert module.resolve_download_window(dates, "2026-01-15", "2015-01-01", 10) == ("2026-01-03", True)


def test_resolve_download_window_current_file_still_self_heals() -> None:
    # 关键回归：last==end_date（无新行可追加）恰是除息后唯一可修复通道，不得跳过
    dates = _consecutive_dates(12)
    assert module.resolve_download_window(dates, "2026-01-12", "2015-01-01", 10) == ("2026-01-03", True)


def test_resolve_download_window_short_history_refetches_from_first_row() -> None:
    dates = _consecutive_dates(5)
    # 历史不足窗口 → 从最早已存行整体重写
    assert module.resolve_download_window(dates, "2026-01-05", "2015-01-01", 10) == ("2026-01-01", True)


def test_resolve_download_window_accepts_string_or_timestamp_dates() -> None:
    dates_str = _consecutive_dates(12)
    dates_ts = pd.to_datetime(dates_str)
    assert module.resolve_download_window(dates_str, "2026-01-12", "2015-01-01", 10) == ("2026-01-03", True)
    assert module.resolve_download_window(dates_ts, "2026-01-12", "2015-01-01", 10) == ("2026-01-03", True)


FIELDS = ["date", "code", "open", "high", "low", "close", "preclose", "volume",
          "amount", "adjustflag", "turn", "tradestatus", "pctChg", "isST"]


def _raw_row(date: str, code: str, close: float):
    value = str(close)
    return [date, code, value, value, value, value, value, "1000", "10000", "2", "1.0", "1", "0.0", "0"]


def _write_stock_parquet(path: Path, rows: list[list[str]]) -> None:
    df = pd.DataFrame(rows, columns=FIELDS)
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "preclose", "volume", "amount", "turn", "pctChg"]:
        df[col] = pd.to_numeric(df[col])
    df.to_parquet(path, engine="pyarrow", compression="snappy", index=False)


class _FakeRS:
    def __init__(self, rows):
        self.fields = FIELDS
        self.error_code = "0"
        self._rows = rows
        self._i = -1

    def next(self):
        self._i += 1
        return self._i < len(self._rows)

    def get_row_data(self):
        return self._rows[self._i]


class _FakeBS:
    """替身 baostock：按 [start_date, end_date] 返回服务端当前快照行并记录调用。"""

    def __init__(self, snapshot):
        self.snapshot = snapshot  # list[(date_str, close)]
        self.calls = []

    def query_history_k_data_plus(self, code, _fields, start_date=None, end_date=None, **kwargs):
        self.calls.append((code, start_date, end_date))
        return _FakeRS([_raw_row(d, code, c) for d, c in self.snapshot if start_date <= d <= end_date])


def _closes_by_date(path: Path) -> dict:
    df = pd.read_parquet(path)
    return dict(zip(df["date"].dt.strftime("%Y-%m-%d"), df["close"]))


def test_process_one_stock_overlap_overwrites_stale_dividend_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 600660 场景复刻：本地已存 01-01..01-25（除息前旧值），服务端快照里
    # 01-06..01-25 已按除息回补下调、01-26..01-30 为新行
    code = "sh.600660"
    path = tmp_path / f"{code}.parquet"
    old_dates = _consecutive_dates(25)
    _write_stock_parquet(path, [_raw_row(d, code, 54.0) for d in old_dates])
    snapshot = [(d, 54.0 if d <= "2026-01-05" else 53.0) for d in old_dates]
    snapshot += [(d, 55.0) for d in _consecutive_dates(5, "2026-01-26")]
    fake = _FakeBS(snapshot)
    monkeypatch.setattr(module, "bs", fake)

    result = module.process_one_stock(code, "2015-01-01", "2026-01-30", "2", str(tmp_path), overlap_bars=20)

    assert result == (code, True, True)
    assert fake.calls == [(code, "2026-01-06", "2026-01-30")]
    df = pd.read_parquet(path)
    assert len(df) == 30 and df["date"].is_unique
    closes = _closes_by_date(path)
    assert closes["2026-01-01"] == 54.0  # 窗口外保留
    assert closes["2026-01-05"] == 54.0
    assert closes["2026-01-06"] == 53.0  # 窗口内旧行被当前快照覆盖（自愈）
    assert closes["2026-01-25"] == 53.0
    assert closes["2026-01-26"] == 55.0  # 新行追加
    assert closes["2026-01-30"] == 55.0


def test_process_one_stock_refetches_window_even_when_already_current(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pi 场景复刻：数据日期已追平 end_date（无新行），纯追加会整只跳过；
    # 重叠窗口必须仍重写最近 N 行，把除息回补落进文件
    code = "sh.600660"
    path = tmp_path / f"{code}.parquet"
    _write_stock_parquet(path, [_raw_row(d, code, 10.0) for d in _consecutive_dates(10)])
    fake = _FakeBS([(d, 9.0) for d in _consecutive_dates(10)])
    monkeypatch.setattr(module, "bs", fake)

    result = module.process_one_stock(code, "2015-01-01", "2026-01-10", "2", str(tmp_path), overlap_bars=5)

    assert result == (code, True, True)
    assert fake.calls == [(code, "2026-01-06", "2026-01-10")]
    df = pd.read_parquet(path)
    assert len(df) == 10 and df["date"].is_unique
    closes = _closes_by_date(path)
    assert closes["2026-01-05"] == 10.0  # 窗口外保留
    assert closes["2026-01-06"] == 9.0   # 窗口内全部刷新
    assert closes["2026-01-10"] == 9.0


def test_process_one_stock_legacy_zero_overlap_skips_current_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # overlap_bars=0 必须精确复原旧行为：已最新则不发起任何请求
    code = "sh.600660"
    path = tmp_path / f"{code}.parquet"
    _write_stock_parquet(path, [_raw_row(d, code, 10.0) for d in _consecutive_dates(10)])
    fake = _FakeBS([])
    monkeypatch.setattr(module, "bs", fake)

    result = module.process_one_stock(code, "2015-01-01", "2026-01-10", "2", str(tmp_path), overlap_bars=0)

    assert result == (code, True, False)
    assert fake.calls == []


def test_process_one_stock_legacy_zero_overlap_appends_next_day(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 旧模式回归：有滞后时仍从 最后日期+1 纯追加，不动历史行
    code = "sh.600660"
    path = tmp_path / f"{code}.parquet"
    _write_stock_parquet(path, [_raw_row(d, code, 10.0) for d in _consecutive_dates(10)])
    snapshot = [(d, 8.0) for d in ("2026-01-11", "2026-01-12")]
    fake = _FakeBS(snapshot)
    monkeypatch.setattr(module, "bs", fake)

    result = module.process_one_stock(code, "2015-01-01", "2026-01-12", "2", str(tmp_path), overlap_bars=0)

    assert result == (code, True, True)
    assert fake.calls == [(code, "2026-01-11", "2026-01-12")]
    df = pd.read_parquet(path)
    assert len(df) == 12 and df["date"].is_unique
    closes = _closes_by_date(path)
    assert closes["2026-01-10"] == 10.0  # 历史行不被触碰
    assert closes["2026-01-12"] == 8.0
