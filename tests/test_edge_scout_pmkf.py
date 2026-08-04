"""Edge Scout PMKF 测试。"""

import pytest
import numpy as np

from ashare_edge_scout.pmkf import apply_pmkf, compute_pmkf_slope


def test_apply_pmkf_short_series():
    """测试短序列直接返回。"""

    prices = [10.0, 11.0, 12.0]
    result = apply_pmkf(prices)

    assert len(result) == 3
    assert np.allclose(result, prices)


def test_apply_pmkf_normal():
    """测试正常序列处理。"""

    # 生成上升序列
    prices = [10.0 + i * 0.1 for i in range(50)]
    result = apply_pmkf(prices)

    assert len(result) == 50
    # 平滑后应该接近原始序列
    assert np.allclose(result, prices, atol=0.5)


def test_compute_pmkf_slope():
    """测试 PMKF 斜率计算。"""

    # 上升序列
    prices = np.array([10.0 + i * 0.1 for i in range(30)], dtype=np.float64)
    slope = compute_pmkf_slope(prices)

    assert slope > 0  # 上升序列斜率为正

    # 下降序列
    prices = np.array([10.0 - i * 0.1 for i in range(30)], dtype=np.float64)
    slope = compute_pmkf_slope(prices)

    assert slope < 0  # 下降序列斜率为负
