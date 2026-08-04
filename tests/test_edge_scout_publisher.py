"""Edge Scout 发布模块测试。"""

import pytest
import tempfile
from pathlib import Path
import csv
import json

from ashare_edge_scout.publisher import publish_scan_results
from ashare_edge_scout.contracts import (
    EdgeScoutResult,
    EdgeScoutScanSummary,
    ReferencePricePublicationRow,
    Tier,
)
from ashare_edge_scout.reference_prices import ReferencePrices


def test_publish_scan_results():
    """测试扫描结果发布。"""

    run_directory = Path("test_run_output")
    if run_directory.exists():
        import shutil
        shutil.rmtree(run_directory)

    try:
        # 创建测试数据
        production = []

        summary = EdgeScoutScanSummary(
            schema_version="edge_scout_v1",
            status="success",
            run_id="test_run",
            as_of=__import__("datetime").date(2026, 7, 24),
            input_code_count=100,
            admitted_count=90,
            rejected_count=10,
            production_candidate_count=0,
            watchlist_count=5,
            near_miss_count=10,
            quality_error_counts={"missing_value": 10},
            boundaries={"read_only": True},
            inputs={"data_root": "test"},
            limitations=("research_only",),
        )

        # 发布结果
        publish_scan_results(
            run_directory=run_directory,
            run_id="test_run",
            results=[],
            production_candidates=production,
            watchlist_candidates=[],
            near_miss_candidates=[],
            summary=summary,
        )

        # 验证输出文件（新结构：run_directory/run_id/）
        run_target = run_directory / "test_run"
        assert (run_target / "candidates.csv").exists()
        assert (run_target / "watchlist.csv").exists()
        assert (run_target / "near_miss.csv").exists()
        assert (run_target / "summary.json").exists()
        assert (run_target / "report.md").exists()
        assert (run_target / "manifest.json").exists()

        # 验证 latest.json
        latest_path = run_directory / "latest.json"
        assert latest_path.exists()

        with open(latest_path) as f:
            latest = json.load(f)
            assert latest["status"] == "success"
            assert latest["candidate_count"] == 0

        # 测试 duplicate run_id 应报错（禁止覆盖已发布 run）
        with pytest.raises(FileExistsError, match="已存在"):
            publish_scan_results(
                run_directory=run_directory,
                run_id="test_run",  # 重复的 run_id
                results=[],
                production_candidates=[],
                watchlist_candidates=[],
                near_miss_candidates=[],
                summary=summary,
            )

    finally:
        # 清理
        run_target = run_directory / "test_run"
        if run_target.exists():
            import shutil
            shutil.rmtree(run_target)
        latest_path = run_directory / "latest.json"
        if latest_path.exists():
            latest_path.unlink()


def test_publish_rejects_production_candidates(tmp_path):
    scan_date = __import__("datetime").date(2026, 7, 24)
    production = [Tier("sh.600000", scan_date, "production", 75.0, 40.0, 25.0, 10.0)]
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="production-disabled",
        as_of=scan_date,
        input_code_count=1,
        admitted_count=1,
        rejected_count=0,
        production_candidate_count=1,
        watchlist_count=0,
        near_miss_count=0,
    )
    with pytest.raises(ValueError, match="production tier is disabled"):
        publish_scan_results(
            tmp_path,
            run_id="production-disabled",
            results=[],
            production_candidates=production,
            watchlist_candidates=[],
            near_miss_candidates=[],
            summary=summary,
        )


def test_publish_results_jsonl_preserves_error_detail():
    scan_date = __import__("datetime").date(2026, 7, 30)
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="audit_detail",
        as_of=scan_date,
        input_code_count=1,
        admitted_count=1,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=0,
        unexpected_error_count=1,
        limitations=("research_only",),
    )
    result = EdgeScoutResult(
        code="sh.600023",
        as_of=scan_date,
        status="rejected",
        admission_error_code="unexpected_error",
        admission_detail="boom",
        limitations=("unexpected_error: boom",),
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir) / "audit_output"
        publish_scan_results(
            run_directory=output_root,
            run_id="audit_detail",
            results=[result],
            production_candidates=[],
            watchlist_candidates=[],
            near_miss_candidates=[],
            summary=summary,
        )

        records = (output_root / "audit_detail" / "results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    payload = json.loads(records[0])
    assert payload["admission_error_code"] == "unexpected_error"
    assert payload["admission_detail"] == "boom"
    assert payload["limitations"] == ["unexpected_error: boom"]


def test_publish_results_jsonl_includes_reference_prices():
    """results.jsonl 应随单股审计明细一并输出研究参考价（research-only）。"""

    scan_date = __import__("datetime").date(2026, 7, 30)
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="audit_ref_price",
        as_of=scan_date,
        input_code_count=1,
        admitted_count=1,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=0,
        limitations=("research_only",),
    )
    tier = Tier(
        code="sh.600023",
        as_of=scan_date,
        tier="near_miss",
        edge_score=55.0,
        base_quality_score=30.0,
        timing_score=15.0,
        risk_score=10.0,
    )
    reference_prices = ReferencePrices(
        code="sh.600023",
        as_of=scan_date,
        close_now=13.5,
        signal_high=14.6,
        signal_low=13.2,
        atr14=0.45,
        buy_reference=14.6,
        stop_reference=13.925,
        partial_take_profit_reference=15.6125,
        take_profit_reference=16.0,
        risk_distance_pct=0.046,
    )
    result = EdgeScoutResult(
        code="sh.600023",
        as_of=scan_date,
        status="admitted",
        tier=tier,
        reference_prices=reference_prices,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir) / "audit_output"
        publish_scan_results(
            run_directory=output_root,
            run_id="audit_ref_price",
            results=[result],
            production_candidates=[],
            watchlist_candidates=[],
            near_miss_candidates=[],
            summary=summary,
        )

        records = (output_root / "audit_ref_price" / "results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    payload = json.loads(records[0])
    assert payload["code"] == "sh.600023"
    assert payload["tier"] == "near_miss"
    rp = payload["reference_prices"]
    assert rp["buy_reference"] == 14.6
    assert rp["stop_reference"] == 13.925
    assert rp["take_profit_reference"] == 16.0
    assert "methodology" in rp


def test_publish_reference_prices_csv_separates_setup_and_confirmation():
    """Reference output must distinguish observation from valid setup confirmation."""

    scan_date = __import__("datetime").date(2026, 7, 30)
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="ref_csv_t1",
        as_of=scan_date,
        input_code_count=1,
        admitted_count=1,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=0,
        limitations=("research_only",),
    )

    def _tier(code, confirmed):
        return Tier(
            code=code,
            as_of=scan_date,
            tier="near_miss",
            edge_score=40.0 if confirmed else 35.0,
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

    result_confirmed = EdgeScoutResult(
        code="sh.600030", as_of=scan_date, status="admitted",
        tier=_tier("sh.600030", True), reference_prices=_rp("sh.600030"),
        t1_confirmed=True,
    )
    result_unconfirmed = EdgeScoutResult(
        code="sh.600031", as_of=scan_date, status="admitted",
        tier=_tier("sh.600031", False), reference_prices=_rp("sh.600031"),
        t1_confirmed=False,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        output_root = Path(temp_dir) / "audit_output"
        publish_scan_results(
            run_directory=output_root,
            run_id="ref_csv_t1",
            results=[result_confirmed, result_unconfirmed],
            production_candidates=[],
            watchlist_candidates=[],
            near_miss_candidates=[],
            summary=summary,
            top_reference_prices=[
                ReferencePricePublicationRow(
                    result_confirmed.tier,
                    result_confirmed.reference_prices,
                    t_day_setup_valid=True,
                    price_volume_confirmed=True,
                    valid_setup_confirmed=True,
                ),
                ReferencePricePublicationRow(
                    result_unconfirmed.tier,
                    result_unconfirmed.reference_prices,
                    t_day_setup_valid=False,
                    price_volume_confirmed=True,
                    valid_setup_confirmed=False,
                ),
            ],
        )

        csv_text = (output_root / "ref_csv_t1" / "reference_prices.csv").read_text(encoding="utf-8")
        report_text = (output_root / "ref_csv_t1" / "report.md").read_text(encoding="utf-8")
    header = csv_text.splitlines()[0]
    assert "t_day_setup_valid" in header
    assert "price_volume_confirmed" in header
    assert "valid_setup_confirmed" in header
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows[0]["t_day_setup_valid"] == "True"
    assert rows[0]["price_volume_confirmed"] == "True"
    assert rows[0]["valid_setup_confirmed"] == "True"
    assert rows[1]["t_day_setup_valid"] == "False"
    assert rows[1]["price_volume_confirmed"] == "True"
    assert rows[1]["valid_setup_confirmed"] == "False"
    assert "有效确认" in report_text
    assert "可直接入场" not in report_text


def test_publish_discovery_csv_contains_rich_cnstock_style_evidence():
    scan_date = __import__("datetime").date(2026, 7, 30)
    tier = Tier("sh.600030", scan_date, "near_miss", 40.0, 20.0, 12.0, 8.0)
    result = EdgeScoutResult(
        code=tier.code,
        as_of=scan_date,
        status="admitted",
        tier=tier,
        industry="software",
        research_close=10.5,
        pct_chg=2.0,
        ret_5d=4.0,
        amount_cny=500_000_000.0,
        turn=3.2,
        volume_ratio_20=1.4,
        pmk_trend_confirmed=True,
        pmk_trend_reason="Trend+MACD",
        pmk_shape_score=82.0,
        pmk_shape_pattern="Steady Climber",
        pmk_rsi=58.0,
        pmk_feature_bonus=8.0,
        candle_position_zone="mid_low",
        candle_confirm_score=8.5,
        candle_confirm_reason="mid_low+strong_close+healthy_volume",
        start_signal_count=3,
        start_signals=("dxbd_up", "gding_up", "dingdi_safe_up"),
        start_signal_reasons=("DXBD_cross_zero", "GDing_or_BBUY_cross", "Dingdi_low_zone_rising(30.0)"),
        discovery_tier="profit_shadow",
        discovery_eligible=True,
        discovery_score=88.0,
        discovery_score_breakdown="edge=40;start=24",
        t_day_setup_valid=False,
        price_volume_confirmed=True,
        valid_setup_confirmed=False,
    )
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="discovery",
        as_of=scan_date,
        input_code_count=1,
        admitted_count=1,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=1,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        target = publish_scan_results(
            Path(temp_dir),
            run_id="discovery",
            results=[result],
            production_candidates=[],
            watchlist_candidates=[],
            near_miss_candidates=[tier],
            summary=summary,
        )
        rows = list(csv.DictReader((target / "discovery.csv").open(encoding="utf-8")))
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))

    assert rows[0]["discovery_tier"] == "profit_shadow"
    assert rows[0]["start_signal_count"] == "3"
    assert rows[0]["pmk_shape_pattern"] == "Steady Climber"
    assert rows[0]["candle_confirm_reason"] == "mid_low+strong_close+healthy_volume"
    assert rows[0]["price_volume_confirmed"] == "True"
    assert "discovery.csv" in manifest["files"]


def test_discovery_csv_sorts_eligible_then_start_count_then_score(tmp_path):
    scan_date = __import__("datetime").date(2026, 7, 30)

    def result(code, *, eligible, starts, score):
        tier = Tier(code, scan_date, "near_miss", 40.0, 20.0, 12.0, 8.0)
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="admitted",
            tier=tier,
            discovery_tier="profit_shadow",
            discovery_eligible=eligible,
            discovery_rejection_reasons=() if eligible else ("discovery_price_too_high",),
            discovery_score=score,
            start_signal_count=starts,
        )

    results = [
        result("sh.600001", eligible=False, starts=5, score=99.0),
        result("sh.600002", eligible=True, starts=2, score=90.0),
        result("sh.600003", eligible=True, starts=3, score=80.0),
        result("sh.600004", eligible=True, starts=3, score=85.0),
    ]
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="discovery-order",
        as_of=scan_date,
        input_code_count=4,
        admitted_count=4,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=4,
    )

    target = publish_scan_results(
        tmp_path,
        run_id="discovery-order",
        results=results,
        production_candidates=[],
        watchlist_candidates=[],
        near_miss_candidates=[item.tier for item in results],
        summary=summary,
    )
    rows = list(csv.DictReader((target / "discovery.csv").open(encoding="utf-8")))

    assert [row["code"] for row in rows] == [
        "sh.600004",
        "sh.600003",
        "sh.600002",
        "sh.600001",
    ]
    assert rows[-1]["discovery_rejection_reasons"] == "discovery_price_too_high"


def test_daily_research_watchlist_prioritizes_confirmed_then_setup_then_cnstock_pool(tmp_path):
    scan_date = __import__("datetime").date(2026, 7, 30)

    def result(code, *, confirmed=False, setup=False, pool=False, discovery=False, rank=0.0):
        tier = Tier(code, scan_date, "near_miss", 40.0, 20.0, 12.0, 8.0)
        return EdgeScoutResult(
            code=code,
            as_of=scan_date,
            status="admitted",
            tier=tier,
            discovery_score=40.0,
            valid_setup_confirmed=confirmed,
            t_day_setup_valid=setup,
            price_volume_confirmed=confirmed,
            cnstock_pool="profit_shadow" if pool else "not_in_cnstock_pool",
            cnstock_pool_eligible=pool,
            cnstock_discovery_rank=rank,
            cnstock_base_score=80.0,
            discovery_eligible=discovery,
            start_signal_count=3 if pool else 2 if discovery else 0,
        )

    results = [
        result("sh.600003", pool=True, rank=90.0),
        result("sh.600002", setup=True),
        result("sh.600001", confirmed=True, setup=True),
        result("sh.600004", discovery=True, rank=85.0),
    ]
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success",
        run_id="daily-watch",
        as_of=scan_date,
        input_code_count=4,
        admitted_count=4,
        rejected_count=0,
        production_candidate_count=0,
        watchlist_count=0,
        near_miss_count=4,
    )

    target = publish_scan_results(
        tmp_path,
        run_id="daily-watch",
        results=results,
        production_candidates=[],
        watchlist_candidates=[],
        near_miss_candidates=[item.tier for item in results],
        summary=summary,
    )
    rows = list(csv.DictReader((target / "daily_research_watchlist.csv").open(encoding="utf-8")))
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))

    assert [row["code"] for row in rows] == ["sh.600001", "sh.600002", "sh.600003", "sh.600004"]
    assert [row["watch_stage"] for row in rows] == [
        "confirmed_watch",
        "setup_watch",
        "cnstock_pool_watch",
        "discovery_watch",
    ]
    assert all(row["research_only"] == "True" for row in rows)
    assert "daily_research_watchlist.csv" in manifest["files"]
