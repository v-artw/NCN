"""Edge Scout 配置加载。

从 V1 配置加载器适配，支持新的 YAML 结构。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from .paper_risk import normalize_paper_risk

import yaml

ALLOWED_MODES = {"read_only_research", "phased_production_adjacent"}
DEFAULT_MKF_POST_CROSS_LAG_RANGE = "lag0-lag2"


def parse_mkf_post_cross_lag_range(value: Any | None = None) -> frozenset[int]:
    """Parse an inclusive ``lag0-lagX`` MKF selector range."""

    if value is None:
        value = DEFAULT_MKF_POST_CROSS_LAG_RANGE
    if not isinstance(value, str):
        raise ValueError("mkf.candidate_selector.post_cross_lag_range must be a string like 'lag0-lag2'")
    match = re.fullmatch(r"lag0-lag([0-9]+)", value.strip())
    if match is None:
        raise ValueError("mkf.candidate_selector.post_cross_lag_range must match 'lag0-lagX'")
    upper = int(match.group(1))
    return frozenset(range(upper + 1))


def _validate_mkf_config(config: Mapping[str, Any]) -> None:
    mkf = config.get("mkf")
    if mkf is None:
        return
    if not isinstance(mkf, Mapping):
        raise ValueError("mkf must be a mapping")
    selector = mkf.get("candidate_selector")
    if selector is None:
        return
    if not isinstance(selector, Mapping):
        raise ValueError("mkf.candidate_selector must be a mapping")
    parse_mkf_post_cross_lag_range(selector.get("post_cross_lag_range"))


def load_config(config_path: str | Path) -> dict[str, Any]:
    """加载 Edge Scout 配置文件。

    参数：
      config_path: 配置文件路径

    返回：
      已加载的配置字典

    异常：
      FileNotFoundError: 文件不存在
      yaml.YAMLError: YAML 格式错误
    """

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as f:
        content = yaml.safe_load(f)

    if not isinstance(content, dict):
        raise ValueError(f"配置文件 {path} 必须是 YAML 字典")

    return content


def validate_config(config: Mapping[str, Any], config_path: str | Path) -> None:
    """验证配置文件必需字段。

    必需字段：
      - schema_version
      - mode
      - paths
      - universe
      - features
      - hard_gates
      - ranking
      - risk
      - publication
    """

    required_keys = [
        "schema_version",
        "mode",
        "production_enabled",
        "paths",
        "universe",
        "features",
        "hard_gates",
        "ranking",
        "risk",
        "publication",
    ]

    missing = [key for key in required_keys if key not in config]
    if missing:
        raise ValueError(
            f"配置文件 {config_path} 缺少必需字段：{', '.join(missing)}"
        )

    # 验证 mode
    if config.get("mode") not in ALLOWED_MODES:
        raise ValueError(
            f"mode 必须是 {sorted(ALLOWED_MODES)!r} 之一，"
            f"当前为 {config.get('mode')!r}"
        )

    # 验证 allow_live_order_submission 必须为 false
    if config.get("allow_live_order_submission", False):
        raise ValueError(
            "禁止实盘下单：allow_live_order_submission 必须为 false"
        )

    if config.get("production_enabled") is not False:
        raise ValueError(
            "Edge Scout V1 production tier 必须显式关闭：production_enabled 必须为 false"
        )

    ranking = config.get("ranking", {})
    if "score_weights" in ranking:
        raise ValueError(
            "ranking.score_weights is unsupported: V1 score components are already contribution points"
        )

    if "market_regime" in config:
        raise ValueError(
            "market_regime is unsupported in V1: use setup.trend for stock trend and "
            "research_market_regime for non-enforcing benchmark study metadata"
        )

    research_regime = config.get("research_market_regime", {})
    if research_regime and research_regime.get("enforcement") != "none":
        raise ValueError(
            "research_market_regime.enforcement must be 'none' in Edge Scout V1"
        )

    _validate_mkf_config(config)
    _validate_demo_portfolio_config(config, config_path)
    _validate_paper_trading_config(config, config_path)
    normalize_paper_risk(config.get("paper_risk"))


def _validate_demo_portfolio_config(config: Mapping[str, Any], config_path: str | Path) -> None:
    demo = config.get("demo_portfolio", {})
    if not demo:
        return
    if not isinstance(demo, Mapping):
        raise ValueError("demo_portfolio must be a mapping")
    if demo.get("enabled") and config.get("allow_demo_portfolio") is not True:
        raise ValueError("demo_portfolio.enabled requires allow_demo_portfolio: true")
    if demo.get("allow_live_order_submission", False):
        raise ValueError("demo_portfolio must not allow live order submission")
    _validate_state_root(demo.get("state_root", ""), config_path, "demo_portfolio.state_root")
    _validate_state_root(demo.get("audit_root", ""), config_path, "demo_portfolio.audit_root")
    _validate_state_root(demo.get("factor_root", ""), config_path, "demo_portfolio.factor_root")
    if int(demo.get("max_portfolios", 0)) < 1:
        raise ValueError("demo_portfolio.max_portfolios must be >= 1")
    if int(demo.get("max_positions", 0)) < 1:
        raise ValueError("demo_portfolio.max_positions must be >= 1")
    if int(demo.get("max_import_positions", 0)) < 1:
        raise ValueError("demo_portfolio.max_import_positions must be >= 1")
    if int(demo.get("max_factor_bytes", 0)) < 1 or int(demo.get("max_factor_bytes", 0)) > 262144:
        raise ValueError("demo_portfolio.max_factor_bytes is invalid")
    if float(demo.get("initial_capital", 0.0)) <= 0:
        raise ValueError("demo_portfolio.initial_capital must be > 0")


def _validate_paper_trading_config(config: Mapping[str, Any], config_path: str | Path) -> None:
    paper = config.get("paper_trading", {})
    if not paper:
        return
    if not isinstance(paper, Mapping):
        raise ValueError("paper_trading must be a mapping")
    if paper.get("enabled") and config.get("allow_paper_trading") is not True:
        raise ValueError("paper_trading.enabled requires allow_paper_trading: true")
    if paper.get("allow_live_order_submission", False):
        raise ValueError("paper_trading.allow_live_order_submission must be false")
    _validate_state_root(paper.get("state_root", ""), config_path, "paper_trading.state_root")
    if int(paper.get("max_snapshot_codes", 0)) < 1:
        raise ValueError("paper_trading.max_snapshot_codes must be >= 1")
    if int(paper.get("max_evaluate_codes", 0)) < 1:
        raise ValueError("paper_trading.max_evaluate_codes must be >= 1")


def _validate_state_root(value: Any, config_path: str | Path, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must stay under output/edge_scout or .runtime")
    normalized = path.as_posix()
    if not (normalized == ".runtime" or normalized.startswith(".runtime/") or normalized == "output/edge_scout" or normalized.startswith("output/edge_scout/")):
        raise ValueError(f"{label} must stay under output/edge_scout or .runtime")


def compute_config_sha256(config_path: str | Path) -> str:
    """计算配置文件 SHA-256。"""

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"配置文件不存在：{path}")

    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_strategy_rule_set(config: Mapping[str, Any]) -> dict[str, Any]:
    """从配置构建策略规则集。

    返回：
      包含所有策略参数的字典
    """

    return {
        "fast_ma": int(config["setup"]["trend"]["fast_ma"]),
        "slow_ma": int(config["setup"]["trend"]["slow_ma"]),
        "ma_slope_lookback": int(config["setup"]["trend"]["ma_slope_lookback"]),
        "min_return_20d": float(config["setup"]["trend"]["min_return_20d"]),
        "max_return_20d": float(config["setup"]["trend"]["max_return_20d"]),
        "high_lookback": int(config["setup"]["pullback"]["high_lookback"]),
        "min_drawdown_from_high": float(
            config["setup"]["pullback"]["min_drawdown_from_high"]
        ),
        "max_drawdown_from_high": float(
            config["setup"]["pullback"]["max_drawdown_from_high"]
        ),
        "min_low_to_ma60_ratio": float(
            config["setup"]["pullback"]["min_low_to_ma60_ratio"]
        ),
        "atr_period": int(config["risk"]["atr_period"]),
        "volume_ma_window": 20,
        "min_volume_to_ma20": float(
            config["setup"]["confirmation"]["min_volume_to_ma20"]
        ),
    }
