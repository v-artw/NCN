"""Edge Scout 配置加载。

从 V1 配置加载器适配，支持新的 YAML 结构。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import yaml


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
    if config.get("mode") not in ("read_only_research", "read_only_paper"):
        raise ValueError(
            f"mode 必须是 'read_only_research' 或 'read_only_paper'，"
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
        "ma_slope_lookback": int(config["market_regime"]["ma_slope_lookback"]),
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
