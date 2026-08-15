"""Edge Scout 扫描器测试。"""

import pytest
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

from ashare_edge_scout.contracts import EdgeScoutResult, Tier
from ashare_edge_scout.reference_prices import ReferencePrices
from ashare_edge_scout.scanner import (
    run_edge_scout_scan,
    EdgeScoutScanInput,
    _build_candle_rule_set,
    _latest_minus_trading_days,
    _evaluate_discovery_eligibility,
    _scan_one_stock,
)


def test_latest_minus_trading_days_auto_selects_t():
    """无 --as-of 时应自动回退 2 个交易日到 T，使 T+1 确认可计算、T+2=latest 可入场。"""

    dates = [date(2026, 7, 24), date(2026, 7, 27), date(2026, 7, 28), date(2026, 7, 29), date(2026, 7, 30)]
    features = {
        "sh.600000": MagicMock(records=[{"date": d} for d in dates]),
        "sh.600001": MagicMock(records=[{"date": d} for d in dates]),
    }
    latest = dates[-1]
    assert _latest_minus_trading_days(features, latest, days=2) == date(2026, 7, 28)

    # 停牌股（最后一条非 latest）不应参与，避免拉低全局 T
    features_with_suspended = dict(features)
    features_with_suspended["sz.000001"] = MagicMock(records=[{"date": d} for d in dates[:3]])
    assert _latest_minus_trading_days(features_with_suspended, latest, days=2) == date(2026, 7, 28)

    records_with_halt = [
        {"date": d, "tradestatus": "0" if d == date(2026, 7, 29) else "1"}
        for d in dates
    ]
    assert _latest_minus_trading_days(
        {"sh.600000": MagicMock(records=records_with_halt)}, latest, days=2
    ) == date(2026, 7, 27)


def test_truncated_records_skips_suspension_when_finding_t1():
    from ashare_edge_scout.scanner import _truncated_records

    records = [
        {"date": date(2026, 7, 28), "tradestatus": "1"},
        {"date": date(2026, 7, 29), "tradestatus": "0"},
        {"date": date(2026, 7, 30), "tradestatus": "1"},
        {"date": date(2026, 7, 31), "tradestatus": "1"},
    ]

    truncated, post_t = _truncated_records(records, date(2026, 7, 28))

    assert [row["date"] for row in truncated] == [date(2026, 7, 28)]
    assert [row["date"] for row in post_t] == [date(2026, 7, 30), date(2026, 7, 31)]


def test_run_edge_scout_scan():
    """测试 Edge Scout 扫描运行。"""

    # 创建临时配置
    config_path = Path("yaml/edge_scout_v1.yaml")
    if not config_path.exists():
        pytest.skip("配置文件不存在")

    # 模拟数据目录
    data_root = Path("test_data")

    input_ = EdgeScoutScanInput(
        data_root=data_root,
        config_path=config_path,
        output_root=Path("test_output"),
        as_of=None,
        top=10,
    )

    # 由于数据目录不存在，应该抛出异常
    with pytest.raises((FileNotFoundError, ValueError)):
        run_edge_scout_scan(input_)


def test_build_candle_rule_set():
    """测试 CandleRuleSet 构建。"""

    config = {
        "setup": {
            "candle": {
                "enabled": ["hammer", "bullish_engulfing", "piercing", "morning_star"],
                "hammer": {
                    "max_body_to_range": 0.40,
                    "min_lower_shadow_to_body": 2.0,
                    "max_upper_shadow_to_body": 0.50,
                    "min_close_location": 0.65,
                },
            },
        },
    }

    rule_set = _build_candle_rule_set(config)
    assert rule_set.enabled_patterns == ("hammer", "bullish_engulfing", "piercing", "morning_star")
    assert rule_set.hammer.max_body_to_range == 0.40
    assert rule_set.hammer.min_lower_shadow_to_body == 2.0


def test_build_candle_rule_set_no_hammer():
    """测试无 hammer 子节时回退默认值。"""

    config = {
        "setup": {
            "candle": {
                "enabled": ["hammer"],
            },
        },
    }

    rule_set = _build_candle_rule_set(config)
    assert rule_set.hammer.max_body_to_range == 0.40


def test_discovery_eligibility_reports_all_research_filter_failures():
    eligible, reasons = _evaluate_discovery_eligibility(
        close=21.0,
        amount_cny=14_999_999.0,
        pct_chg=7.1,
        ret_5d=12.1,
        turn=35.1,
        volume_ratio_20=5.1,
        config={"discovery": {"enabled": True}},
    )

    assert eligible is False
    assert reasons == (
        "discovery_price_too_high",
        "discovery_amount_too_low",
        "discovery_daily_move_too_high",
        "discovery_ret_5d_too_high",
        "discovery_turn_too_high",
        "discovery_volume_ratio_too_high",
    )


def test_discovery_eligibility_honors_disabled_switch():
    eligible, reasons = _evaluate_discovery_eligibility(
        close=10.0,
        amount_cny=100_000_000.0,
        pct_chg=1.0,
        ret_5d=2.0,
        turn=3.0,
        volume_ratio_20=1.2,
        config={"discovery": {"enabled": False}},
    )

    assert eligible is False
    assert reasons == ("discovery_disabled",)


def test_summary_counts_unexpected_error_separately():
    captured = {}
    scan_date = date(2026, 7, 30)
    scored_tier = Tier(
        code="sh.600001",
        as_of=scan_date,
        tier="near_miss",
        edge_score=12.0,
        base_quality_score=3.0,
        timing_score=4.0,
        risk_score=5.0,
    )

    def fake_admission_universe(codes, data_root, research_window_admission=False):
        return (
            {
                "sh.600001": MagicMock(records=({"date": scan_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},)),
                "sh.600002": MagicMock(records=({"date": scan_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},)),
            },
            {"sh.600003": "missing_value"},
        )

    def fake_scan_one_stock(code, **kwargs):
        if code == "sh.600001":
            return EdgeScoutResult(code=code, as_of=scan_date, status="admitted", tier=scored_tier)
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="rejected",
            admission_error_code="unexpected_error",
            admission_detail="boom",
            limitations=("unexpected_error: boom",),
        )

    def fake_publish_scan_results(**kwargs):
        captured["summary"] = kwargs["summary"]

    with tempfile.TemporaryDirectory() as temp_dir, \
        patch("ashare_edge_scout.scanner.load_config", return_value={"ranking": {}}), \
        patch("ashare_edge_scout.scanner.validate_config"), \
        patch("ashare_edge_scout.scanner.compute_config_sha256", return_value="sha"), \
        patch("ashare_edge_scout.scanner._build_candle_rule_set", return_value=MagicMock()), \
        patch("ashare_edge_scout.scanner.get_parquet_codes", return_value=["sh.600001", "sh.600002", "sh.600003"]), \
        patch("ashare_edge_scout.scanner.load_industry_map", return_value={}), \
        patch("ashare_edge_scout.scanner.admission_universe", side_effect=fake_admission_universe), \
        patch("ashare_edge_scout.scanner._truncated_records", return_value=([{"date": scan_date}], [])), \
        patch("ashare_edge_scout.scanner._scan_one_stock", side_effect=fake_scan_one_stock), \
        patch("ashare_edge_scout.publisher.publish_scan_results", side_effect=fake_publish_scan_results):
        root = Path(temp_dir)
        run_edge_scout_scan(
            EdgeScoutScanInput(
                data_root=root,
                config_path=root / "edge_scout.yaml",
                output_root=root / "out",
                as_of=scan_date,
                run_id="summary-counts",
            )
        )

    summary = captured["summary"]
    assert summary.scored_count == 1
    assert summary.unexpected_error_count == 1
    assert summary.no_tier_reason_counts == {"missing_value": 1}


def test_top_reference_prices_excludes_out_of_v1_risk_range():
    """TOP 参考价列表应过滤参考风险距超出 V1 范围 [2.5%, 6.0%] 的样本。"""

    captured = {}
    scan_date = date(2026, 7, 30)

    def _tier(code, edge):
        return Tier(
            code=code,
            as_of=scan_date,
            tier="near_miss",
            edge_score=edge,
            base_quality_score=3.0,
            timing_score=4.0,
            risk_score=5.0,
        )

    def _rp(code, risk):
        return ReferencePrices(
            code=code,
            as_of=scan_date,
            close_now=20.0,
            signal_high=21.0,
            signal_low=19.5,
            atr14=0.5,
            buy_reference=21.0,
            stop_reference=19.8,
            partial_take_profit_reference=22.8,
            take_profit_reference=23.4,
            risk_distance_pct=risk,
        )

    def fake_admission_universe(codes, data_root, research_window_admission=False):
        return (
            {code: MagicMock(records=({"date": scan_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},)) for code in codes},
            {},
        )

    def fake_scan_one_stock(code, **kwargs):
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="admitted",
            tier=_tier(code, edge=30.0),
            reference_prices=_rp(code, risk=risk_map[code]),
        )

    risk_map = {
        "sh.600001": 0.030,  # 范围内
        "sh.600002": 0.095,  # 超出 6%
        "sh.600003": 0.020,  # 低于 2.5%
    }

    def fake_publish_scan_results(**kwargs):
        captured["top_reference_prices"] = kwargs["top_reference_prices"]

    with tempfile.TemporaryDirectory() as temp_dir, \
        patch("ashare_edge_scout.scanner.load_config", return_value={"ranking": {}}), \
        patch("ashare_edge_scout.scanner.validate_config"), \
        patch("ashare_edge_scout.scanner.compute_config_sha256", return_value="sha"), \
        patch("ashare_edge_scout.scanner._build_candle_rule_set", return_value=MagicMock()), \
        patch("ashare_edge_scout.scanner.get_parquet_codes", return_value=list(risk_map)), \
        patch("ashare_edge_scout.scanner.load_industry_map", return_value={}), \
        patch("ashare_edge_scout.scanner.admission_universe", side_effect=fake_admission_universe), \
        patch("ashare_edge_scout.scanner._truncated_records", return_value=([{"date": scan_date}], [])), \
        patch("ashare_edge_scout.scanner._scan_one_stock", side_effect=fake_scan_one_stock), \
        patch("ashare_edge_scout.publisher.publish_scan_results", side_effect=fake_publish_scan_results):
        root = Path(temp_dir)
        run_edge_scout_scan(
            EdgeScoutScanInput(
                data_root=root,
                config_path=root / "edge_scout.yaml",
                output_root=root / "out",
                as_of=scan_date,
                run_id="top-ref-price",
            )
        )

    top = captured["top_reference_prices"]
    assert [row.tier.code for row in top] == ["sh.600001"]


def test_top_reference_prices_sorts_confirmed_first():
    """TOP 参考价应把 T+1 已确认样本排在未确认之前，再按层级与 edge_score 排序。"""

    captured = {}
    scan_date = date(2026, 7, 30)

    def _tier(code, edge, tier="near_miss"):
        return Tier(
            code=code,
            as_of=scan_date,
            tier=tier,
            edge_score=edge,
            base_quality_score=3.0,
            timing_score=4.0,
            risk_score=5.0,
        )

    def _rp(code):
        return ReferencePrices(
            code=code,
            as_of=scan_date,
            close_now=20.0,
            signal_high=21.0,
            signal_low=19.5,
            atr14=0.5,
            buy_reference=21.0,
            stop_reference=19.8,
            partial_take_profit_reference=22.8,
            take_profit_reference=23.4,
            risk_distance_pct=0.040,
        )

    def fake_admission_universe(codes, data_root, research_window_admission=False):
        return (
            {code: MagicMock(records=({"date": scan_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},)) for code in codes},
            {},
        )

    cases = {
        # code: (tier, edge, t1_confirmed)
        "sh.600001": ("near_miss", 30.0, False),
        "sh.600002": ("watchlist", 55.0, False),
        "sh.600003": ("near_miss", 20.0, True),
        "sh.600004": ("watchlist", 50.0, True),
    }

    def fake_scan_one_stock(code, **kwargs):
        tier, edge, confirmed = cases[code]
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="admitted",
            tier=_tier(code, edge=edge, tier=tier),
            reference_prices=_rp(code),
            t1_confirmed=confirmed,
            price_volume_confirmed=confirmed,
            t_day_setup_valid=confirmed,
            valid_setup_confirmed=confirmed,
        )

    def fake_publish_scan_results(**kwargs):
        captured["top_reference_prices"] = kwargs["top_reference_prices"]

    with tempfile.TemporaryDirectory() as temp_dir, \
        patch("ashare_edge_scout.scanner.load_config", return_value={"ranking": {}}), \
        patch("ashare_edge_scout.scanner.validate_config"), \
        patch("ashare_edge_scout.scanner.compute_config_sha256", return_value="sha"), \
        patch("ashare_edge_scout.scanner._build_candle_rule_set", return_value=MagicMock()), \
        patch("ashare_edge_scout.scanner.get_parquet_codes", return_value=list(cases)), \
        patch("ashare_edge_scout.scanner.load_industry_map", return_value={}), \
        patch("ashare_edge_scout.scanner.admission_universe", side_effect=fake_admission_universe), \
        patch("ashare_edge_scout.scanner._truncated_records", return_value=([{"date": scan_date}], [])), \
        patch("ashare_edge_scout.scanner._scan_one_stock", side_effect=fake_scan_one_stock), \
        patch("ashare_edge_scout.publisher.publish_scan_results", side_effect=fake_publish_scan_results):
        root = Path(temp_dir)
        run_edge_scout_scan(
            EdgeScoutScanInput(
                data_root=root,
                config_path=root / "edge_scout.yaml",
                output_root=root / "out",
                as_of=scan_date,
                run_id="top-ref-order",
            )
        )

    top = captured["top_reference_prices"]
    assert [row.tier.code for row in top] == [
        "sh.600004",  # watchlist 已确认（已确认优先于任何未确认）
        "sh.600003",  # near_miss 已确认
        "sh.600002",  # watchlist 未确认
        "sh.600001",  # near_miss 未确认
    ]


def test_summary_uses_structured_hard_gate_details_and_full_conservation():
    captured = {}
    scan_date = date(2026, 7, 30)

    def fake_admission_universe(codes, data_root, research_window_admission=False):
        return (
            {
                code: MagicMock(records=({"date": scan_date},))
                for code in ("sh.600001", "sh.600002")
            },
            {"sh.600003": "missing_value"},
        )

    scored = Tier(
        code="sh.600001",
        as_of=scan_date,
        tier="near_miss",
        edge_score=12.0,
        base_quality_score=3.0,
        timing_score=4.0,
        risk_score=5.0,
    )

    def fake_scan_one_stock(code, **kwargs):
        if code == "sh.600001":
            return EdgeScoutResult(code=code, as_of=scan_date, status="admitted", tier=scored)
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="rejected",
            admission_error_code="hard_gate_failure",
            hard_gate_details=("insufficient_listing_days", "close_too_low"),
        )

    def fake_publish_scan_results(**kwargs):
        captured["summary"] = kwargs["summary"]

    with tempfile.TemporaryDirectory() as temp_dir, \
        patch("ashare_edge_scout.scanner.load_config", return_value={"ranking": {}}), \
        patch("ashare_edge_scout.scanner.validate_config"), \
        patch("ashare_edge_scout.scanner.compute_config_sha256", return_value="sha"), \
        patch("ashare_edge_scout.scanner._build_candle_rule_set", return_value=MagicMock()), \
        patch("ashare_edge_scout.scanner.get_parquet_codes", return_value=["sh.600001", "sh.600002", "sh.600003"]), \
        patch("ashare_edge_scout.scanner.load_industry_map", return_value={}), \
        patch("ashare_edge_scout.scanner.admission_universe", side_effect=fake_admission_universe), \
        patch("ashare_edge_scout.scanner._truncated_records", return_value=([{"date": scan_date}], [])), \
        patch("ashare_edge_scout.scanner._scan_one_stock", side_effect=fake_scan_one_stock), \
        patch("ashare_edge_scout.publisher.publish_scan_results", side_effect=fake_publish_scan_results):
        root = Path(temp_dir)
        run_edge_scout_scan(EdgeScoutScanInput(
            data_root=root,
            config_path=root / "edge_scout.yaml",
            output_root=root / "out",
            as_of=scan_date,
            run_id="structured-audit",
        ))

    summary = captured["summary"]
    assert summary.hard_gate_rejected_count == 1
    assert summary.hard_gate_rejection_counts == {
        "close_too_low": 1,
        "insufficient_listing_days": 1,
    }
    assert summary.data_rejected_count == 1
    assert summary.scored_count == 1
    assert summary.unclassified_count == 0
    assert summary.admission_quantity_conservation_valid is True
    assert summary.scan_quantity_conservation_valid is True
    assert summary.tier_quantity_conservation_valid is True
    assert summary.quantity_conservation_valid is True


def test_scan_one_stock_exception_sets_admission_detail(monkeypatch):
    scan_date = date(2026, 7, 30)
    records = [
        {"date": date(2026, 7, day), "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5, "volume": 1000.0}
        for day in range(1, 25)
    ]

    monkeypatch.setattr("ashare_edge_scout.scanner.apply_hard_gates", lambda *args, **kwargs: (True, []))

    def raise_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("ashare_edge_scout.scanner.detect_candle_patterns", raise_boom)

    result = _scan_one_stock(
        code="sh.600001",
        records=records,
        t1_records=[],
        config={},
        candle_rule_set=MagicMock(),
        as_of=scan_date,
    )

    assert result.status == "rejected"
    assert result.admission_error_code == "unexpected_error"
    assert result.admission_detail == "boom"
    assert result.limitations == ("unexpected_error: boom",)
