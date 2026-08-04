"""Edge Scout PMK 特征测试。"""

import pytest
import numpy as np

from ashare_edge_scout.pmk_features import compute_pmk_features, sma, rsi, atr, macd


def test_sma():
    """测试移动平均计算。"""

    values = [10.0, 11.0, 12.0, 13.0, 14.0]
    result = sma(values, 3)

    assert len(result) == 5
    assert np.isnan(result[0])
    assert np.isnan(result[1])
    # 从第 3 个元素开始有值
    assert not np.isnan(result[2])
    assert abs(result[2] - 11.0) < 0.01


def test_rsi():
    """测试 RSI 计算（修复后，前 period-1 个值为 NaN）。"""

    # 生成波动序列
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(100) * 0.5)

    result = rsi(close, 14)

    assert len(result) == 100
    # 前 14 个值（索引 0-13）应为 NaN（不足以计算 RSI）
    assert np.all(np.isnan(result[:14]))
    # 第 15 个值（索引 14）开始有有效值
    assert not np.isnan(result[14])
    # 有效值应在 0-100 之间
    valid = result[14:]
    assert np.all(valid >= 0) and np.all(valid <= 100)


def test_atr():
    """测试 ATR 计算。"""

    # 生成 OHLC 序列
    np.random.seed(42)
    n = 50
    high = 100.0 + np.cumsum(np.abs(np.random.randn(n)) * 0.5)
    low = high - np.abs(np.random.randn(n)) * 0.3
    close = low + np.random.randn(n) * 0.2

    result = atr(high, low, close, 14)

    assert len(result) == n
    # 前 13 个元素应该是 0.0（不truncated前值的逻辑）
    assert (result[:13] == 0.0).all()
    # 第 14 个元素开始有值（>= 0）
    assert result[13] >= 0


def test_macd():
    """测试 MACD 计算。"""

    # 生成序列
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(100) * 0.5)

    dif, dea, hist = macd(close, 12, 26, 9)

    assert len(dif) == 100
    assert len(dea) == 100
    assert len(hist) == 100


def test_compute_pmk_features():
    """测试 PMK 特征计算。"""

    # 生成序列（确保 close 全为正数）
    np.random.seed(42)
    n = 60
    base = 100.0
    open_ = base + np.cumsum(np.random.randn(n) * 0.3)
    high = open_ + np.abs(np.random.randn(n)) * 0.2
    low = open_ - np.abs(np.random.randn(n)) * 0.2
    close = low + np.abs(np.random.randn(n)) * 0.1
    # 确保全部为正
    close = np.maximum(close, base * 0.5)
    volume = np.abs(np.random.randn(n) * 1000) + 500

    result = compute_pmk_features(open_, high, low, close, volume)

    assert "pmk_trend_confirmed" in result
    assert "pmk_shape_score" in result
    assert "pmk_shape_pattern" in result
    assert "pmk_rsi" in result
    assert "pmk_atr_squeeze" in result
    assert "pmk_atr14" in result  # P0-5 修复：新增真实 ATR14 字段
    assert "pmk_macd_confirm" in result
    assert "pmk_volume_breakout" in result
