# MKF lag0..5 目标收益网格回测口径（target-zero-return，v3）

本文记录 MKF 红蓝线上穿后 lag0..lag7、T+1..T+20、目标收益 1%..20% 的研究型网格回测口径。2026-08-26 用户最终确认：窗口内触达目标则按目标收益计，未触达则按 `0%` 收益计；不使用 T+N 收盘兜底，不使用止损，不使用手续费/滑点/真实成交假设。

## 研究边界

- 只做离线研究回测，不修改 MKF 候选选择器、SMC 准入、watchlist、AI review、生产配置或任何 broker/order 路径。
- 结果是当前数据版本上的描述性研究证据，不代表真实收益承诺。
- 不建模手续费、印花税、滑点、涨跌停成交概率、部分成交、仓位、止损或真实撮合。

## 信号与买入

- 父信号：`mkf_red_blue_cross20_green_exit_under80_mask`。
- 比较 lag：从父信号开始的 stock-tradable lag0..lag7，非交易/停牌行不消耗 lag。
- 硬门槛：`production_gate_mask` 应用于每个 lag 信号行。
- 买入价：lag 信号收盘确认后的下一个股票可交易日开盘价 `entry_open`。

## 卖出窗口与目标触达

对每个组合 `(lag, T+N, target_pct)`：

```text
target_price = entry_open * (1 + target_pct / 100)
target_hit = any(high from T+1 through T+N) >= target_price
```

- `T` 是买入日。
- `T+1..T+N` 是买入后的可卖出股票交易日窗口。
- 买入日最高价不计入触达，因为 A 股新买仓位不能当日卖出。
- “T+1 到 T+20 的任意一天卖出”在本研究中表示：只要窗口内任意可卖日最高价触达目标，就视为以该目标收益卖出。

## 收益与排序（v3 口径）

每个样本的简化收益：

```text
sample_return = target_pct / 100 if target_hit else 0
```

每个格子的平均简化收益：

```text
mean_target_zero_return = target_pct / 100 * target_hit_rate
```

排序目标：

```text
最高 mean_target_zero_return
```

这正是用户确认的“未触达 = 0% 收益”口径。禁止混入：

- `T+N close / entry_open - 1` 超时收盘收益；
- 止损或固定亏损；
- 实盘手续费、滑点、税费、涨跌停可成交性；
- 任何生产 selector/watchlist/AI/config 改动。

## 输出

推荐输出到 `.runtime/`：

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src \
  .venv/bin/python scripts/evaluate_mkf_post_cross_lag_target_grid.py \
  --data-root PFrontStockData \
  --config yaml/edge_scout_v1.yaml \
  --start-date 2021-01-01 \
  --workers 8 \
  --output .runtime/mkf-post-cross-lag-target-grid.json \
  --summary-csv .runtime/mkf-post-cross-lag-target-grid.csv
```

CSV 是长表：每行一个 `lag × period × horizon × target_pct` 组合，包含 `n`、`target_hits`、`target_hit_rate`、Wilson 上下界、`mean_target_zero_return`、`entry_dates`、`codes`、`events`、`retention_vs_parent_crosses`。

JSON 中 `best_point_readout.best_by_mean_target_zero_return` 是 full-period 下按 `mean_target_zero_return` 排名的最高组合；`best_by_horizon` 和 `best_by_target_pct` 分别给出每个窗口/每个目标收益水平下的最高组合。

## 阅读注意

- 面板内部不保留 `future_close_tN`，成熟度与状态记账只依赖未来可卖日的日期和最高价。
- `mean_target_zero_return` 是用户指定的简化收益口径，不是实盘 P&L，也不是收益承诺。
- 高目标收益可能因为命中率太低而均值较低；低目标收益可能因为收益幅度太小而均值较低；最高组合由两者乘积决定。
- 任何结果都不得直接用于生产选择器或止盈规则；晋升需要独立的样本外与审计期验证。
