from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_runtime_tree_has_no_legacy_project_dependency() -> None:
    forbidden = (
        "a_share_short_swing",
        "/Users/artx/Local/Git/Stock/CN",
        "/Users/artx/Local/Git/CNstock",
        "com.vartw.stock-cn.edge-scout",
    )
    paths = [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("scripts/*.py"),
        *ROOT.glob("scripts/*.sh"),
        *ROOT.glob("config/**/*.plist"),
        *ROOT.glob("config/**/*.json"),
    ]
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert not any(value in content for value in forbidden), path


def test_source_tree_contains_only_edge_scout_package() -> None:
    assert {path.name for path in (ROOT / "src").iterdir() if path.is_dir()} <= {
        "ashare_edge_scout",
        "ashare_edge_scout.egg-info",
    }


def test_data_and_signal_flat_modules_alias_new_implementations() -> None:
    import ashare_edge_scout.candle_timing as flat_candle_timing
    import ashare_edge_scout.contracts as flat_contracts
    import ashare_edge_scout.daily_bars as flat_daily_bars
    import ashare_edge_scout.data_sources as flat_data_sources
    import ashare_edge_scout.discovery as flat_discovery
    import ashare_edge_scout.reference_prices as flat_reference_prices
    import ashare_edge_scout.signal_scoring as flat_signal_scoring
    import ashare_edge_scout.publisher as flat_publisher
    import ashare_edge_scout.prospective_audit as flat_prospective_audit
    import ashare_edge_scout.scanner as flat_scanner
    import ashare_edge_scout.data.contracts as data_contracts
    import ashare_edge_scout.data.daily_bars as data_daily_bars
    import ashare_edge_scout.data.data_sources as data_sources
    import ashare_edge_scout.data.reference_prices as data_reference_prices
    import ashare_edge_scout.signals.candle_timing as signal_candle_timing
    import ashare_edge_scout.signals.discovery as signal_discovery
    import ashare_edge_scout.signals.signal_scoring as signal_scoring
    import ashare_edge_scout.publication.publisher as publication_publisher
    import ashare_edge_scout.audit.prospective as audit_prospective
    import ashare_edge_scout.scan.scanner as scan_scanner

    assert flat_daily_bars is data_daily_bars
    assert flat_data_sources is data_sources
    assert flat_contracts is data_contracts
    assert flat_reference_prices is data_reference_prices
    assert flat_candle_timing is signal_candle_timing
    assert flat_discovery is signal_discovery
    assert flat_signal_scoring is signal_scoring
    assert flat_publisher is publication_publisher
    assert flat_prospective_audit is audit_prospective
    assert flat_scanner is scan_scanner
    for name in (
        "EdgeScoutScanInput",
        "EdgeScoutScanResult",
        "run_edge_scout_scan",
        "_to_date",
        "_build_candle_rule_set",
        "_latest_minus_trading_days",
        "_truncated_records",
        "_evaluate_discovery_eligibility",
        "_scan_one_stock",
        "_write_manifest",
        "_write_latest",
    ):
        assert getattr(flat_scanner, name) is getattr(scan_scanner, name)


def test_root_contains_no_migrated_research_json_artifacts() -> None:
    artifact_names = (
        "bullish-engulfing-confirmation-stage1-2021-2026.json",
        "d-open-t1-barrier-quality-full-history.json",
        "excursion-5d-10d-full-history.json",
        "futu-indicator-full-universe-2021-2026.json",
        "futu-indicator-ranking-2021-2026.json",
        "joint-strategy-2021-2026.json",
        "mkf-green-exit-stage1-2021-2026.json",
        "next-trading-day-direction-full-history.json",
        "nextday-validation-2021-present.json",
        "pmkf-mkf-t5-quality-2021-2026.json",
        "pmkf-mkf-t5-quality-smoke.json",
        "precision70-stage1-2021-2026.json",
        "rising-three-methods-stage1-2021-2026.json",
        "risk-disclosure-stage1-2021-2026.json",
        "rsrs-mhpg-full-universe-2021-2026.json",
        "shengbei-kdj-full-universe-2021-2026.json",
        "signal-study-2018-2026.json",
        "t-open-plus3-five-day-win-rate-2021-present.json",
        "v2-support-reclaim-stage1-2021-2026.json",
        "walk-forward-strategy-2023-2026.json",
    )
    unexpected = [name for name in artifact_names if (ROOT / name).exists()]
    assert not unexpected, (
        "Research evidence belongs under docs/research/results or docs/research/archive; "
        f"found root artifacts: {unexpected}"
    )
