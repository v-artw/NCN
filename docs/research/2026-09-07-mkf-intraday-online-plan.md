# MKF 分钟/小时级别线上使用研究方案

> **性质**：决策支持 / 研究运行设计，**不是可执行 P&L，也不是买入或交易建议**。
> 本文档不修改任何生产程序、selector、config、watchlist，也不经手真实资金。
> 本文档讨论的"线上使用"指**在 A 股交易时段内，更频繁地跑 MKF 研究流水线**（日内频率），**不是实盘下单、不是真实成交、不是杠杆、不是无人值守执行**。
> 承接 [`2026-08-27-mkf-live-probe-plan.md`](2026-08-27-mkf-live-probe-plan.md)（日级、`T+1..T+20`、开盘入场）；本文把视角从"日级信号 + 多日观察"改为"日内分钟/小时频率的确认与失效"。

---

## 一、背景与目的

`2026-08-27-mkf-live-probe-plan.md` 验证的是**日级 MKF 信号**在 `T+1..T+20` 观察窗下的命中与费用表现，入场点是下一个可交易日的**开盘价**。它回答"日级信号在目标 4%/3% 下扣费后是否划算"。

本文档是**一个新研究方向**：MKF 的**决策流水线目前是日级的**，但**日内分钟/小时级数据的基础设施已经存在且只读**。我们要研究的是——

> **能否（以及如何在边界内）把 MKF 的"信号确认/失效"细化到分钟或小时级别，在交易时段内更频繁地运行研究流水线，从而给人工复核提供更及时的日内证据？**

目标不是替代日级信号，而是**在日级信号之上叠加日内颗粒度的确认/失效证据**，并评估其研究价值、可行性与成本。

---

## 二、现状基线（代码事实）

### 2.1 决策流水线是日级的

- 入口 `mkf.sh` → `scripts/edge_scout_scan.sh`。
- 核心命令：
  - `mkf-review`：选 MKF 候选 → AI 委员会只读复核（`edge_scout_scan.sh:745+`）。
  - `select-mkf`：独立 MKF 候选源实验，支持 `--as-of DATE` 历史回放。
  - `daily`：**自动日期、仅日终**跑一次，明确拒绝 `--as-of` 手动日期（`edge_scout_scan.sh:970`）。
- AI review 上下文是**日线**的：`lookback_bars: 60`、`recent_daily_bars: 8`，复核视角是"未来 1-10 个交易日"（`yaml/mkf_ai_review.yaml:29,51-52`）。
- 信号语义是 MKF 指标穿越数值阈值 20（非均线），提示词有硬性措辞约束（`yaml/mkf_ai_review.yaml:16-17`）。

### 2.2 日内数据基础设施已存在（独立、只读）

- `src/ashare_edge_scout/data/intraday_data.py`（427 行）。
- `SUPPORTED_MINUTE_PERIODS = ("1m", "5m", "15m", "30m", "60m")`。
- `IntradayDataClient`：
  - `fetch_snapshot(code)`：实时快照（新浪）。
  - `fetch_minute_bars(code, period, limit=120)`：多周期分钟线（东财）。
  - 自带**当前未收盘 K 线状态** `is_forming`、进程内缓存 `_cached/_store`、时效校验 `freshness_payload`、周期校验 `validate_minute_period`。
- 文档明确：**"read-only intraday market-data adapters for research display. They do not provide execution, portfolio or return inputs."**（仅供研究展示，不提供执行/组合/收益输入）。
- 限制：东财 **1m 历史只回看最近 5 天**。

### 2.3 生产边界（AGENTS.md）

- `production_enabled: false` 必须保持（`yaml/edge_scout_v1.yaml:9`）。
- **禁止**：实盘券商登录、真实下单、杠杆、 custody/settlement、无人值守真金白银执行。
- **允许**：研究信号生成、组合式 demo 分析、paper/simulation、PMKF/MKF 研究看板、风控、审计日志。
- 数据源优先级 remote-first：WSL → Doris → local（`AGENTS.md:117-123`）。

---

## 三、三条线上化路径 + 权衡

| 路径 | 做什么 | 改动量 | 风险 / 成本 | 是否推荐 |
|---|---|---|---|---|
| **A. 日内确认叠加层** | 日级流水线不变，每天产出候选；交易时段内每 5-15 分钟用 `intraday_data.py` 拉当前分钟线 + 未收盘 K 线状态，对每个候选算一个"日内确认/失效"轻信号，刷新成研究看板 | 小（新增一个消费者，复用现成客户端） | 低；LLM 成本几乎为零 | ✅ 起步首选 |
| **B. 日内重选** | 把 `select-mkf` 本身改成小时 / 15 分钟节奏，而非日级 | 大（选择逻辑要从日线改到分钟线，重设 review 回看窗口） | 中-高；review 提示词与 YAML 都是日线的，要另开短视角模式 | 后续，A 验证后再评 |
| **C. 调度编排** | 用 cron / 循环在交易时段每 N 分钟跑现有命令 | 中 | 高；AI 委员会每个候选 7 个角色 = 多次 LLM 调用，每分钟全量跑很贵，必须把"便宜的重选"与"贵的 review"解耦 | 仅作为 A/B 的调度外壳 |

---

## 四、关键约束与风险（steelman 提醒）

1. **未收盘 K 线（forming bar）问题**：分钟线最新一根是 incomplete 的。一个 1m 上的"穿越阈值20"在 K 线未收盘时**不算确认**。必须先定义"是否对 forming bar 行动"——建议研究阶段**只对已收盘 K 线信号计数**，forming bar 单列为"未确认"状态。
2. **回看窗口不匹配**：review 要 `lookback_bars: 60`。在 1m 上 60 根 = 60 分钟，在 60m 上 60 根 = 30 小时；而东财 1m 只给 5 天历史。接日内时 **review 上下文必须重缩放**，否则证据窗口与信号周期错配。
3. **数据源限频**：新浪 + 东财有拉取限制。每分钟对 ~400 只全量拉会撞限频。依赖现有缓存（`_cached/_store`）+ 节流 + 批量合并请求。
4. **成本**：AI 委员会很贵（每候选 7 个角色）。不能每分钟全量跑。必须**事件驱动**（日内叠加层报警才触发）或**固定小时级**。
5. **"线上" ≠ "实盘"**：本文的"线上"= 交易时段内更频繁地跑**研究**流水线，不是实盘。`production_enabled` 保持 false。
6. **交易时段约束**：A 股 9:30-11:30、13:00-15:00。"线上运行"只在这些窗口有意义；开盘前 30 分钟、收盘前 30 分钟数据质量特殊，需单独处理。

---

## 五、推荐路径 A 的设计细节

### 5.1 数据流

```
[日级] mkf-review / select-mkf  ──►  每日 MKF 候选清单 (CSV/JSON)
                                          │
[日内, 交易时段每 5-15 分钟]            │
   IntradayDataClient.fetch_minute_bars ─┘
   IntradayDataClient.fetch_snapshot
                                          ▼
         日内确认/失效叠加层 (对每个候选)
                                          ▼
         研究看板 / 刷新 watchlist (只读展示)
                                          ▼
   仅当叠加层报警 ──►  触发 AI 委员会 review (事件驱动)
```

### 5.2 频率建议

- **数据拉取**：每 5 分钟（1m/5m 数据下，5 分钟是噪声与成本的平衡点）。
- **叠加层计算**：与拉取同频。
- **AI review 触发**：非固定频率，而是**事件驱动**（见 5.4），或最多每小时一次兜底。

### 5.3 日内确认 / 失效逻辑（轻信号，非执行）

对每个日级候选 `c`（其日级信号为"穿越阈值20 向上"）：

- **日内确认**：在 `5m/15m/60m`（选一个主周期）上，已收盘 K 线再次满足 MKF 穿越阈值20 向上 → 标记 `intraday_confirm`。
- **日内失效**：已收盘 K 线出现 MKF 穿越阈值20 **向下**，或价格回落跌破日级信号当日关键位 → 标记 `intraday_fail`。
- **未确认**：forming bar（当前未收盘）不纳入确认/失效计数，单列为 `forming`。
- 全部为**研究标签**，不映射到任何自动下单、仓位、止盈止损执行。

### 5.4 事件驱动 review

- 叠加层把 `intraday_confirm` / `intraday_fail` 写入候选状态。
- 仅当候选出现 `intraday_fail`（或连续多次 `intraday_confirm` 达到阈值）时，才触发一次 AI 委员会 review。
- 其余时间不消耗 LLM。

### 5.5 输出

- 一个**只读研究看板 / 刷新 watchlist**（复用 `export-mkf-web-ai` 的导出思路，但增加日内列）。
- 每个候选增加列：`intraday_state(confirm/fail/forming/none)`、`last_confirm_period`、`last_update`。
- 明确标注：研究证据，非交易指令。

---

## 六、预注册研究设计

按项目预注册研究文化（见 `AGENTS.md:42-43` 与 live-probe plan），先定一个可证伪的假设与门槛：

- **假设 H1**：在日级 MKF 信号之上叠加 15m/60m 日内确认/失效标签后，`intraday_confirm` 候选的次日/当日内命中质量（用现有日级回测口径）显著优于"仅日级信号、无日内过滤"的基线。
- **固定候选集**：现有 MKF selector 在某个 `--as-of` 日产出的候选。
- **成功门槛**：日内过滤组的**日级回测命中率 / 扣费后期望** 相对基线提升 ≥ 预注册阈值（如 +2 个百分点命中率，或期望 +X%）。
- **失败门槛**：无提升或变差 → 停止该路径，记录负结果（负结果也是证据）。
- **预算**：单次回测的数据量、计算量、时间上限预注册后固定。
- **决策**：达成功门槛 → 推进 A 的实跑（paper/demo）；达失败门槛 → 记录并终止。

> 注意：H1 的"命中质量"必须用**现有日级回测口径**评估，不能引入新的、未校准的日内命中定义，否则破坏验证一致性（参照项目"回测口径确认"反馈）。

---

## 七、什么现在不要做

- ❌ 不改 `select-mkf` 的选择逻辑为日内节奏（路径 B，改动大、review 不匹配）。
- ❌ 不做每分钟全量 AI 委员会 review（路径 C 的 naive 版，成本失控）。
- ❌ 不引入实盘下单、真实成交、杠杆、仓位执行、止盈止损自动执行。
- ❌ 不对 forming bar 直接计为确认（除非后续研究单独证明其价值）。
- ❌ 不改 `production_enabled`（保持 false）、不改生产 YAML 的日级语义。
- ❌ 不引入新的、未校准的"日内命中"定义来替代日级回测口径。

---

## 八、最小下一步

1. **读码确认**：精读 `src/ashare_edge_scout/data/intraday_data.py` 的 `fetch_minute_bars` / `fetch_snapshot` / `is_forming` 语义与返回字段，确认叠加层可复用的接口。
2. **写一个只读探针脚本**（放 `.runtime/` 或 `output/edge_scout/research/`）：对 3-5 只已知 MKF 候选，拉 15m/60m 分钟线 + snapshot，打印 `intraday_state` 标签，**不接任何执行、不跑 LLM**。
3. **人工核对**：把叠加层标签与当日 K 线肉眼对照，验证"确认/失效/forming"语义是否符合预期。
4. 仅当 2-3 通过，再评估是否把探针升级为对全量候选的叠加层，并预注册 H1 回测。

---

## 附录：相关文件

- 日级流水线入口：`mkf.sh` → `scripts/edge_scout_scan.sh`（`mkf-review` / `select-mkf` / `daily`）
- AI review 配置：`yaml/mkf_ai_review.yaml`（日线 `lookback_bars:60`、`recent_daily_bars:8`）
- 日内数据适配器：`src/ashare_edge_scout/data/intraday_data.py`（`IntradayDataClient`、`SUPPORTED_MINUTE_PERIODS`、`is_forming`）
- 兼容别名：`src/ashare_edge_scout/intraday_data.py`
- 生产开关：`yaml/edge_scout_v1.yaml:9`（`production_enabled: false`）
- 边界与远程优先级：`AGENTS.md`
- 承接文档：`docs/research/2026-08-27-mkf-live-probe-plan.md`
