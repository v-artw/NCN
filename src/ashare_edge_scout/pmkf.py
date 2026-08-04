"""PMKF 卡尔曼滤波器。

实现轻量 1D Kalman 平滑器，不使用 filterpy 依赖。
纯函数实现，接受 list/tuple/numpy array 输入。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def apply_pmkf(prices: Sequence[float], pseudo_constraint: float = 0.0) -> np.ndarray:
    """应用 PMKF 卡尔曼滤波。

    参数：
      prices: 价格序列
      pseudo_constraint: 伪约束值

    返回：
      平滑后的价格数组（numpy float64）

    注意：
      若价格序列长度 < 20，直接返回原序列。
    """

    prices_array = np.array(prices, dtype=np.float64)
    if len(prices_array) < 20:
        return prices_array

    # 初始化卡尔曼滤波器状态
    x = np.array([prices_array[0], 0.0])
    P = np.eye(2) * 100.0  # 初始协方差

    # 状态转移矩阵
    F = np.array([[1.0, 1.0], [0.0, 1.0]])

    # 观测矩阵
    H = np.array([[1.0, 0.0]])

    # 过程噪声
    Q = np.array([[0.01, 0.01], [0.01, 0.01]])

    # 观测噪声
    R = np.array([[1.0]])

    smoothed = np.zeros_like(prices_array)

    # 伪观测矩阵
    H_pseudo = np.array([[0.0, 1.0]])

    for i, z in enumerate(prices_array):
        # 预测
        x = F @ x
        P = F @ P @ F.T + Q

        # 伪观测更新（用于约束速度）
        innovation_cov = H_pseudo @ P @ H_pseudo.T + np.eye(1) * 1e-5
        K_pseudo = P @ H_pseudo.T @ np.linalg.inv(innovation_cov)
        x = x + K_pseudo.flatten() * (pseudo_constraint - H_pseudo @ x)

        # 真实观测更新
        innovation = z - H @ x
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        x = x + K.flatten() * innovation
        P = (np.eye(2) - K @ H) @ P

        smoothed[i] = x[0]

    return smoothed


def compute_pmkf_slope(pmkf_series: np.ndarray) -> float:
    """计算 PMKF 系列斜率。

    参数：
      pmkf_series: PMKF 平滑后的价格序列

    返回：
      斜率值（百分比）
    """

    if len(pmkf_series) < 20:
        return 0.0

    recent = pmkf_series[-20:]
    if recent[0] == 0:
        return 0.0

    # 计算最近 20 个点的斜率
    x = np.arange(len(recent), dtype=np.float64)
    slope = (recent[-1] - recent[0]) / len(recent)
    return float(slope / recent[0] * 100)
