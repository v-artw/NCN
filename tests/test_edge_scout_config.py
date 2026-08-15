"""Edge Scout 配置测试。"""

import pytest
from pathlib import Path

from ashare_edge_scout.config import load_config, validate_config, compute_config_sha256, build_strategy_rule_set


def test_load_config():
    """测试配置加载。"""

    config_path = Path("yaml/edge_scout_v1.yaml")
    if config_path.exists():
        config = load_config(config_path)
        assert isinstance(config, dict)
        assert "schema_version" in config
        assert "mode" in config
        assert "market_regime" not in config
        assert config["research_market_regime"]["enforcement"] == "none"
        assert "score_weights" not in config["ranking"]
    else:
        with pytest.raises(FileNotFoundError):
            load_config(Path("nonexistent.yaml"))


def test_validate_config():
    """测试配置验证。"""

    valid_config = {
        "schema_version": "edge_scout_v1",
        "mode": "read_only_research",
        "production_enabled": False,
        "paths": {},
        "universe": {},
        "features": {},
        "hard_gates": {},
        "ranking": {},
        "risk": {},
        "publication": {},
    }

    validate_config(valid_config, Path("test.yaml"))

    # 缺少必需字段
    invalid_config = {"schema_version": "edge_scout_v1"}
    with pytest.raises(ValueError):
        validate_config(invalid_config, Path("test.yaml"))

    # mode 无效
    invalid_config["mode"] = "live_trading"
    with pytest.raises(ValueError):
        validate_config(invalid_config, Path("test.yaml"))

    # allow_live_order_submission 必须为 false
    invalid_config["mode"] = "read_only_research"
    invalid_config["allow_live_order_submission"] = True
    with pytest.raises(ValueError):
        validate_config(invalid_config, Path("test.yaml"))

    invalid_config = dict(valid_config, production_enabled=True)
    with pytest.raises(ValueError, match="production_enabled"):
        validate_config(invalid_config, Path("test.yaml"))

    invalid_config = {**valid_config, "ranking": {"score_weights": {"timing": 0.35}}}
    with pytest.raises(ValueError, match="score_weights is unsupported"):
        validate_config(invalid_config, Path("test.yaml"))

    invalid_config = {**valid_config, "market_regime": {"ma_slope_lookback": 5}}
    with pytest.raises(ValueError, match="market_regime is unsupported"):
        validate_config(invalid_config, Path("test.yaml"))

    invalid_config = {**valid_config, "mode": "read_only_paper"}
    with pytest.raises(ValueError, match="read_only_research"):
        validate_config(invalid_config, Path("test.yaml"))

    invalid_config = {
        **valid_config,
        "research_market_regime": {"enforcement": "hard_gate"},
    }
    with pytest.raises(ValueError, match="enforcement must be 'none'"):
        validate_config(invalid_config, Path("test.yaml"))


def test_compute_config_sha256():
    """测试配置 SHA-256 计算。"""

    config_path = Path("yaml/edge_scout_v1.yaml")
    if config_path.exists():
        sha256 = compute_config_sha256(config_path)
        assert isinstance(sha256, str)
        assert len(sha256) == 64  # SHA-256 是 64 个十六进制字符

        with pytest.raises(FileNotFoundError):
            compute_config_sha256(Path("nonexistent.yaml"))


def test_build_strategy_rule_set():
    """测试策略规则集构建。"""

    config = {
        "setup": {
            "trend": {
                "fast_ma": 20,
                "slow_ma": 60,
                "ma_slope_lookback": 5,
                "min_return_20d": 0.03,
                "max_return_20d": 0.30,
            },
            "pullback": {
                "high_lookback": 10,
                "min_drawdown_from_high": 0.03,
                "max_drawdown_from_high": 0.10,
                "min_low_to_ma60_ratio": 0.98,
            },
            "candle": {
                "enabled": ["hammer", "bullish_engulfing", "piercing", "morning_star"],
            },
            "confirmation": {
                "require_close_above_signal_high": True,
                "min_volume_to_ma20": 1.05,
                "execution_delay_trading_days": 2,
            },
        },
        "research_market_regime": {
            "enforcement": "none",
            "close_above_ma": 20,
            "max_5d_benchmark_drawdown": -0.03,
        },
        "risk": {
            "atr_period": 14,
        },
    }

    rules = build_strategy_rule_set(config)
    assert rules["fast_ma"] == 20
    assert rules["slow_ma"] == 60
    assert rules["ma_slope_lookback"] == 5
    assert rules["min_return_20d"] == 0.03
