# Reviewer Handoff

## Current Task: GitHub checkpoint upload and milestone

### Changed Files
- `HANDOFF.md`: added this checkpoint publication handoff entry.
- All current modified and untracked project files are intended to be committed and pushed per user instruction.

### Behavior / Logic Changes
- No additional code behavior was intentionally changed during the GitHub upload step.
- Existing local changes include MKF/PMKF research tooling, target-grid/friction result artifacts, AI review/config updates, SMC/news updates, docs, and tests from prior work in this working tree.

### Validation
- `git diff --check`: passed before staging.
- Secret-like string scan excluded `.git`, `.venv`, `output`, `.runtime`, and `PFrontStockData`; hits were code fields, documentation, or test fake values, with no real credential identified.
- GitHub remote inspection found `origin` at `https://github.com/v-artw/NCN.git`; `gh repo view` returned `v-artw/NCN` with default branch `main`.
- Checkpoint commit pushed: `81e256c` on branch `chore/ncn-structured-research-checkpoint`.
- GitHub milestone created: `Structured MKF Research Checkpoint` (#1), `https://github.com/v-artw/NCN/milestone/1`.
- Final `git status --short --branch` after push showed the branch tracking `origin/chore/ncn-structured-research-checkpoint` with no pending file changes before this handoff update.

### Risks / Review Notes
- User explicitly chose to include **all current working tree changes** and to create a **GitHub Milestone**.
- Do not delete, reset, clean, force-push, or alter production/live-trading boundaries as part of this upload.
- User initially thought the repository might not exist, then corrected that NCN already exists; no repository creation was needed.

## Current Task: MKF lag range YAML configuration and verification

### Changed Files
- `src/ashare_edge_scout/config.py`: strict parser for inclusive `lag0-lagX`; optional `mkf.candidate_selector` validation.
- `yaml/edge_scout_v1.yaml`: default `mkf.candidate_selector.post_cross_lag_range: lag0-lag2`.
- `src/ashare_edge_scout/pmkf_mkf/candidates.py`: existing selector reads configured lags, passes them to the post-lag mask/context lookup, and publishes selector/range metadata.
- `scripts/select_mkf_candidates.py`: dynamic configured-range output instead of hard-coded lag wording.
- `tests/test_edge_scout_config.py`, `tests/test_mkf_candidate_selector.py`: parser, default, invalid syntax, lag5, summary, and CLI coverage.
- `docs/2026-08-23-mkf-ai-review-parameter-reference.md`: documented YAML syntax.
- `HANDOFF.md`: compressed historical handoff and recorded verification.

### Behavior / Logic Changes
- `lag0-lagX` means the inclusive range `{0, ..., X}`; it is not a fixed alias table.
- `lag0-lag2` means lag0/lag1/lag2; `lag0-lag5` means lag0 through lag5.
- Checked-in default remains `lag0-lag2`; no default production expansion occurred.
- Changing only `yaml/edge_scout_v1.yaml` to `lag0-lag5` expands the existing MKF selector.
- Existing hard gates, causal handling, suspension handling, watchlist, AI, SMC, broker/order, and production boundaries remain unchanged.
- The previously attempted independent lag research CLI was fully rolled back and must not be reintroduced.

### Verification
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_edge_scout_config.py tests/test_mkf_candidate_selector.py tests/test_research_mkf.py tests/test_mkf_ai_review.py tests/test_main_script.py -q`: **69 passed**.
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mkf_candidate_selector.py -q`: **12 passed**.
- Python compilation passed for `config.py`, `candidates.py`, and `scripts/select_mkf_candidates.py`.
- `git diff --check` passed after removing the extra EOF blank line.
- Default-vs-legacy comparison used current local `PFrontStockData` and temporary output directories:
  - current YAML: range `lag0-lag2`, 16 candidates;
  - temporary config with new `mkf` section removed: fallback range `lag0-lag2`, 16 candidates;
  - selector IDs identical: `mkf_red_blue_cross20_post_lag0_lag1_lag2_v5`;
  - parsed candidate rows identical: `rows_identical=True`.
- Main entrypoint smoke passed:
  - command: `./main.sh select-mkf-local --top 1`;
  - signal date: `2026-08-25`;
  - scanned 7361 codes, selected 16;
  - output: `status=success`, `post_cross_lag_range=lag0-lag2`.
- `mkf-review` and `mkf-small` AI-inclusive flows were not run in the last check because they invoke AI review; the selector they call was verified.
- No backtest or remote environment run was needed for this configuration-only change.

### Exact Next Action
- If requested, manually change `mkf.candidate_selector.post_cross_lag_range` in `yaml/edge_scout_v1.yaml` to `lag0-lag5`, then run `./main.sh select-mkf-local --top 20` and verify the printed selector/range and candidate lag distribution.
- Do not alter production behavior, watchlists, AI defaults, or trading paths without an explicit request and separate validation.

## Relevant Historical Research Conclusions

### MKF selector rule
- Current v3 chart-matched MKF rule uses the MFK4 green-zone right edge:
  - prior tradable row is `momentum <= 20`, `inter <= 20`, `near <= 20`;
  - current red `momentum` and blue `near` cross from `<20` to `>=20`;
  - current red/blue remain `<80`;
  - existing hard gates remain applied.
- Older candidate runs generated before the v3 correction are not chart-matched evidence.

### Complete收益/回测口径（压缩保存）
- 研究范围：`lag0-lag7 × T+1..T+20 × target 1%..20%`；lag 是股票可交易日序列，停牌/不可交易日不消耗 lag。
- 入场：父 MKF 信号按指定 lag 确认后，取其后的下一个股票可交易日开盘 `entry_open`；买入日最高价不计入卖出触达，符合 A 股 T+1 约束。
- 目标价：`target_price = entry_open × (1 + target_pct / 100)`。
- 命中定义：从买入后的 T+1 开始，在指定观察窗口内，任意可卖交易日 `high >= target_price` 即命中；同一样本只计一次命中。
- 旧口径：未获用户明确批准前，`target_pct if hit else T+N close / entry_open - 1` 的超时收益/均值排名不得引用为有效结论；旧结果只能视为禁止方法残留。
- 口径 A（target-zero-return，用户确认）：命中收益 `target_pct / 100`；未命中收益固定 `0%`；组合指标 `mean_target_zero_return = target_pct / 100 × target_hit_rate`；按该指标排序。
- 口径 B（T+20 close fallback，用户确认）：始终观察到 T+20；T+1..T+20 命中则收益 `target_pct / 100`；截至 T+20 未命中则收益 `T+20 close / entry_open - 1`；按 `mean_realized_return` 排序。该口径不再用 T+N close 作为不同 horizon 的兜底。
- 口径 A 结果：`docs/research/results/mkf/lag0-to_lag7/2026-08-26/`，full-period 为 `8 × 20 × 20 = 3200` cells。
- 口径 B 结果：`docs/research/results/mkf/lag0-to_lag7_t20-close-fallback/2026-08-26/`，full-period 为 `8 × 20 = 160` cells，horizon 固定 T+20。
- 已观察的描述性结论：口径 A full-period 最优为 lag7/T+20/11%，约 3.9157% 简化均值；lag0-lag5 版本最优为 lag4/T+20/11%，约 3.9123%。口径 B lag0-lag7 最优为 lag4/T+20/20%，约 1.4209% 均值实现收益。以上只是在样本和简化规则下的排序，不是实盘收益承诺。
- 固定目标的既有比较：口径 A 下目标 5% 和 6% 的最优窗口均为 T+20，lag4领先但 lag0接近；T+20 的最优简化均值高于 T+10。此类比较不得脱离对应口径和样本解释。
- 两种口径均为研究指标，不是可执行 P&L：未建模手续费、滑点、税费、涨跌停/排队/成交概率、部分成交、仓位、止损、资金占用、退出路径和真实撮合。
- 不得据此直接修改生产 selector、watchlist、AI 默认输入或交易路径；未来回测仍按 WSL → Doris `.venv-doris/bin/python` → 本地的顺序，并记录环境与 worker。

### Friction + per-position drawdown study (lag0-7 × T+1..T+20 × target 1%..20%, 3手, net-drawdown 1:1) — DONE 2026-08-27
- 研究范围：父 MKF 交叉信号 + `production_gate_mask` 硬门，固定 **3手 = 300 股**/边。模块 `src/ashare_edge_scout/pmkf_mkf/mkf_friction_drawdown.py`；CLI `scripts/evaluate_mkf_friction_drawdown.py`（多进程 ProcessPoolExecutor 聚合）。
- 手续费（三费）：佣金 万2.5（每边 5 元最低）、过户费 万0.1（买卖双边）、印花税 0.05%（仅卖）；净收益 = `(exit − 卖出费)/(entry + 买入费) − 1`。
- 回撤：单 3手头寸、以每日收盘标记；T+1 起运行最高价触及 `entry×(1+target)` 即按**目标价**止盈，否则 T+n 收盘卖出；drawdown 为日内权益曲线（含卖出日按成交额标记）的峰值-谷值。
- 稳定性门（防小 n 过拟合）：`min_n≥300, min_codes≥50, min_entry_dates≥120`。结果 **3200/3200 cells 全过门**（每 cohort 2368–2524 股票、1158–1175 入场日），统计有效。
- 单位：`-0.01` 约 −1% 净收益 / 1% 回撤；行尾 `%` 标记打印用归一化数值的千倍（与既有口径一致的呈现）。
- **结果（1:1 最优 / 最优净收益 / 最小回撤）：**
  - 1:1 最优（`scored[0]`）：**lag0 / T+1 / target 17%**，score = −0.0136，net ≈ −0.05%，mean_dd ≈ 1.31%，max_dd 17.8% —— 临界持平，非可执行规则。
  - 最优净收益（`scored_by_net_return[0]`）：**lag5 / T+19 / target 20%**，net = **+1.13%**，mean_dd 9.34%，max_dd 54.6% —— 唯一正净收益在长窗口高目标，但回撤大、风险收益差。
  - 最小回撤（`scored_by_drawdown[0]`）：**lag0 / T+1 / target 1%**，mean_dd 1.16%（最小），但 net = −0.78%（几乎必 miss → 次收低于入场）。
- 结论：手续费基本抹平短端边际收益；唯一正净收益来自“长窗口等 20% 脉冲”的高回撤押注（9% 平均 / 55% 最大回撤），在 1:1 惩罚下不划算。方法论稳态结论：3手+三费下该网格**净收益多为负至临界持平**，非稳健 edge；1:1 最优 (lag0/T+1/17%) 非可执行独立规则。
- 产物：`.runtime/mkf-friction-drawdown.json`（全量）+ `.runtime/mkf-friction-drawdown.csv`（按 1:1 最优排序的 gated 行）。文档：`docs/2026-08-27-mkf-friction-drawdown.md`。`production_enabled: false`，未改任何生产路径。
- 后续可选：对 1:1 惩罚权重做敏感性（如 2:1 向下）、按组合市值定仓（3手费/资本随股价波动，低股价受 5 元地板约束）需重算 optimum。

## Repository / Governance
- Branch: `chore/ncn-structured-research-checkpoint`; main branch: `main`.
- Current phase permits research signal generation, demo/paper workflows, PMKF/MKF dashboards, risk controls, audit logs, and read-only AI review.
- Keep `production_enabled: false`.
- Live broker login, live orders, leverage, custody/settlement, unattended real-money execution, and committed real-money P&L remain prohibited without future explicit governance authorization.
- Do not push, reset, clean, force-update, or delete user work unless explicitly requested.
- Existing working tree contains broader unrelated SMC/news, docs, and research changes; review diffs by task/file rather than assuming all modifications belong to the latest MKF task.
