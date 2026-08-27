# MKF Post-Cross Target Grid — Friction + Per-Position Drawdown Study

**Date:** 2026-08-27
**Scope:** Research only — no production selector, watchlist, AI default, or broker path is touched
(`production_enabled: false`, `research_only: True`).
**Module:** `src/ashare_edge_scout/pmkf_mkf/mkf_friction_drawdown.py`
**CLI:** `scripts/evaluate_mkf_friction_drawdown.py`
**Output:** `.runtime/mkf-friction-drawdown.json` (full report) and `.runtime/mkf-friction-drawdown.csv`
(gated rows, best-first).
**Schema version:** `ncn_mkf_post_cross_lag_friction_drawdown_v1`

## 1. Goal

Take the already-validated post-cross lag/target panel (AGI-NCN-043, "口径 A" grid) and layer two
things the previous grid deliberately omitted:

1. **Realistic A-share trading friction** per trade, at a **fixed 3-lot (3手 = 300 shares)** position size.
2. **Per-position (single 3-lot trade) drawdown**, marked to daily closes.

Then rank cells by **`net_return − mean_drawdown` (a 1:1 risk penalty)** and report the optimal cell
under that penalty, plus the best-by-net and best-by-drawdown cells.

This is descriptive, in-sample research evidence. It is **not** executable P&L.

## 2. Universe & window

| Item | Value |
|---|---|
| Universe | 3 196 current main-board parquet files (prefix `sh.600/601/603/605`, `sz.000/001/002/003`) |
| Date window | `2021-01-01` → `2026-08-22` (`--start-date` / `--end-date`) |
| Cell grid | 8 lags (0–7) × 20 horizons (T+1..T+20) × 20 targets (1%..20%) = 3 200 cells |

## 3. Signal & production gates

A trade is a red/blue crossover of `mkf_red_blue_cross20_green_exit_under80_mask`, carrying the
usual `production_gate_mask` hard gate (no ST, no limit-up at entry, no limit-down at exit). A position
is opened one bar **after** the signal, at the post-cross **entry price**. Trades are backtested at every
post-cross lag 0–7 (so lag 0 = open on the same bar as the crossover).

## 4. Friction model

Fixed **3手 = 300 shares** per side (buy and sell). Per-share cost:

| Fee | Rate | Floor / note |
|---|---|---|
| Commission (佣金) | 万 2.5 (`0.00025`) | **5 元** minimum per side |
| Transfer fee (过户费) | 万 0.1 (`0.00001`) | both buy and sell |
| Stamp duty (印花税) | 0.05% (`0.0005`) | **sell side only** (halved Aug-2023) |

Per-share buy cost = `max(entry × 0.00025, 5 / 300) + entry × 0.00001`.
Per-share sell cost = `max(exit × 0.00025, 5 / 300) + exit × (0.0005 + 0.00001)`.

For low-priced stocks the 5 元 floor dominates: a 40 元 stock costs ~0.08% round trip in the rate
portion but the floor forces ~0.5–0.8% round trip before price even moves. Friction therefore bites
hardest on the tiny edge cells this study is trying to isolate — which is the point.

## 5. Hit / exit / drawdown definition

For a `(lag, horizon=T+n, target_pct)` cell on one position (entry `e`, future closes `c`, future highs
`h`, window length `n`):

- **Hit** if the running max high reaches `e × (1 + target_pct)` anywhere in the window. On the first
  such day the position is **sold at the target price** (realistic exit — you take profit at the level
  you set, not blindly at close).
- **No hit:** sold at the horizon close `c[n-1]`.
- **Net return** = `(exit − sell_fee) / (entry + buy_fee) − 1`.
- **Drawdown** = peak-to-trough of the per-share equity curve marked to daily closes. Day 0 = invested
  base; day `k` = close, replaced by the **net sell value from the exit day onward** (the position is
  sold on the exit day, so its mark is the proceeds that day and flat after). Drawdown is measured over
  this marked curve.

## 6. Scoring & ranking

- **net_return** = population mean of per-position net returns (sum over positions / number of positions).
- **mean_drawdown** = population mean of per-position drawdown magnitudes.
- **max_drawdown** = maximum single-position drawdown observed in the cell.
- **score** = `net_return − mean_drawdown` (the 1:1 risk penalty the user requested).

Three rankings are reported:

| Ranking | Sort order |
|---|---|
| `scored` (optimal) | by `net_return − mean_drawdown`, descending |
| `scored_by_net_return` | by `net_return`, descending |
| `scored_by_drawdown` | by `mean_drawdown`, ascending |

## 7. Stability gate

To defeat the small-n (single-stock) overfitting trap, a `(lag, horizon)` cohort is only counted if:

| Gate | Value |
|---|---|
| `min_n` (positions) | ≥ 300 |
| `min_codes` (distinct stocks) | ≥ 50 |
| `min_entry_dates` (distinct dates) | ≥ 120 |

Because all per-target cells in a `(lag, horizon)` cohort share the same position count and the cohort
must clear all three gates, all cells in a passing cohort pass together. **Result: 3 200 / 3 200 cells
gated** (n_gated = n_total), with cohort sizes of 2 368–2 524 codes and 1 158–1 175 entry dates, so
the numbers are statistically meaningful rather than n=2 artifacts. `sample_codes = 3 196`.

## 8. Results

All numbers are population means over gated positions (see CSV for full ranking; key cells below).

### 8.1 Optimal under the 1:1 penalty — `scored[0]`

| lag | horizon | target | n | hit_rate | net_return | mean_dd | max_dd | score |
|---|---|---|---|---|---|---|---|---|
| 0 | T+1 | 17% | 20 130 | 0.4% | **−0.05%** | **1.31%** | 17.8% | **−0.0136** |

The 1:1-optimal is **near break-even at best** (−0.05% net) and sits at the lowest-drawdown horizon
(T+1, ~1.3% mean drawdown). At T+1 the ~17% target is the sweet spot: a rare (~0.4%) single-day
up-g impulse that occasionally pays, offset against the common small loss when next-day close is below
entry.

### 8.2 Best net return — `scored_by_net_return[0]`

| lag | horizon | target | n | hit_rate | net_return | mean_dd | max_dd | score |
|---|---|---|---|---|---|---|---|---|
| 5 | T+19 | 20% | 18 838 | 15.5% | **+1.13%** | 9.34% | **54.6%** | −0.082 |

The only cells with **positive** net return are long-horizon, high-target, high-lag — e.g. lag 5,
T+19, 20% target. But they carry a **9.3% average drawdown and a 54.6% maximum single-position
drawdown**. They are positive net only because a 20% target is rarely blocked: the position keeps holding
until the stock eventually rallies 20%, giving a mean net of ~+1.1%.

### 8.3 Best drawdown — `scored_by_drawdown[0]`

| lag | horizon | target | n | hit_rate | net_return | mean_dd | max_dd | score |
|---|---|---|---|---|---|---|---|---|
| 0 | T+1 | 1% | 20 130 | 56.4% | **−0.78%** | **1.16%** | 17.8% | −0.0194 |

The lowest-drawdown cell (1.16% mean) is the 1% target at T+1, but it is **net negative** (−0.78%):
at a 1% target you almost always miss the day's impulse and sell at next-day close, which is typically
below entry plus friction.

### 8.4 Distribution

- Of 3 200 cells, **1 615 have a positive mean net return** (all long-horizon / high-target).
- The top 20 cells under the 1:1 score are all in the **−0.05% to −0.16%** net band — the short-horizon
  cells where drawdown stays minimal but net is dominated by friction and next-day mean-reversion.

## 9. Interpretation

- **Friction nearly erases the short-term edge.** At the natural short-horizon picks the 1:1-optimal is
  essentially break-even (−0.05% net, −1.3% drawdown); the marginal edge that "口径 A" saw pre-friction
  does not survive realistic 3手 fees.
- **The only positive-net cells are high-drawdown bets.** They profit by *waiting* for a 20% pop over a
  long window — 9% average / 55% max drawdown — which is a poor risk/reward under a 1:1 penalty and is
  closer to holding a call option than to a mean-reversion/edge play.
- **The requested 1:1-optimal (lag0 / T+1 / 17% target) is not actionable** as a standalone rule: it is
  marginally net-negative and would need a tighter entry/exit or lower friction to become positive.
- The methodology holds the drawdown penalty fixed at 1:1 as requested. Sensitivity to the penalty
  weight (e.g. 2:1 downside) or to position sizing (3手 is volume-deterministic, so fee-per-capital varies
  strongly with price) is a natural follow-up.

## 10. Caveats

- **In-sample, path-dependent hits** are detected with `argmax` over the high series; first-hit day is
  used for the exit mark, so intraday fill slippage within the hit day is ignored.
- **3手 is a fixed share count**, so fee-as-a-fraction-of-capital depends on the stock price; the 5 元
  floor is the binding constraint for sub-~20 元 names. A size scaled to portfolio value would change the
  friction drag and shift the optimum.
- **No limit-up / limit-down exec friction** beyond the entry gate; the exit assumes the target is reachable
  (it is reachable only when the daily high covers the target, which is exactly the hit condition).
- Data window ends 2026-08-22; results shift with the end date.