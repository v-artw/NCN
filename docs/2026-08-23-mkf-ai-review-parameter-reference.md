# MKF AI 复核参数对照与股票排序规则

本文说明 `review_mkf_ai.py` / `mkf_ai_review.py` 生成的 MKF AI 委员会只读研究复核结果。它用于人工研究分层，不是买入、卖出、仓位、收益或实盘执行建议。

## 适用范围

- 默认 MKF 候选 lag 范围由 `yaml/edge_scout_v1.yaml` 的 `mkf.candidate_selector.post_cross_lag_range` 控制；`lag0-lag2` 表示 lag0、lag1、lag2，改为 `lag0-lag5` 表示 lag0 至 lag5。
- 默认配置仍使用 `lag0-lag2`，对应候选规则 `mkf_red_blue_cross20_post_lag0_lag1_lag2_v5_and_existing_hard_gates`。
- 适用于 MKF AI 复核输出文件：`reviews.json`、`mkf_ai_reviews_*.csv`。
- 不适用于 SMC 主扫描、SMC 新闻复核、Demo/Paper 组合、实盘交易或收益承诺。
- `experimental_unvalidated = TRUE` 表示该研究层仍是实验性输出，必须通过单独预注册验证后才能提升为稳定策略依据。

## 候选源触发规则

默认 MKF 候选源使用 v5 规则：

1. 绿色区域按 MFK4 公式 `BULLCLUSTER := MOMENTUM <= 20 AND INTER <= 20 AND NEAR <= 20` 理解。
2. 上穿日的上一交易日必须处于该绿色背景块。
3. 上穿日红线 `mkf_momentum` 和蓝线 `mkf_near` 必须同一交易日从 20 下方上穿到 20 以上。
4. 上穿日红线和蓝线必须仍低于 80，避免过热起点。
5. 入选日取上穿日当天、上穿日后的第 1 个或第 2 个股票可交易日；停牌日不消耗 lag，lag3 以后不入选。
6. 输出中的 `cross_date` 是原始上穿日，`signal_date` 是入选日，`post_cross_lag` 只能为 0、1 或 2。
7. 其他主板、非 ST、价格、停牌、流动性等硬门槛保持不变。

## 股票排序规则

MKF 流程里有两套排序，必须区分：

### 1. 候选源排序

候选源是 AI 复核之前的原始 MKF 候选列表，输出在 `candidates.csv` / `candidates.json`。

排序规则：

```text
amount_cny 降序 → code 升序
```

含义：

1. 成交额 `amount_cny` 越高越靠前。
2. 成交额相同时，按股票代码 `code` 字典序升序。
3. 该排序只表示候选源展示顺序和流动性优先，不代表 AI 更看好。
4. 候选源 summary 中的 `review_order` 为 `amount_cny_desc_code_asc`。

### 2. AI 复核排序

AI 复核是在候选源之上做只读研究分层，输出在 `reviews.json` / `mkf_ai_reviews_*.csv`。

排序规则：

```text
review_state 优先级 → confidence 降序 → local_score 降序 → code 升序
```

状态优先级从高到低：

| 顺序 | review_state | 中文含义 | 解释 |
|---:|---|---|---|
| 1 | `priority_research` | 优先研究 | 技术、消息和委员会判断更值得优先人工研究。 |
| 2 | `standard_research` | 标准研究 | 候选有效，但仍有阻力、证据不足或持续性分歧。 |
| 3 | `insufficient_evidence` | 证据不足 | 无法形成足够强的研究支持。 |
| 4 | `risk_attention` | 风险关注 | 存在需要优先排查的风险。 |
| 5 | `ai_unavailable` | AI 未评分 | AI 调用失败或不可用时的保守兜底状态。 |

同一个 `review_state` 内：

1. `confidence` 越高越靠前。
2. `confidence` 相同时，`local_score` 越高越靠前。
3. 两者都相同时，按 `code` 升序。

因此，不能只看 `local_score` 或 `confidence` 做全局排序。例如，一个 `standard_research` 且 `confidence=0.90` 的股票，仍排在所有 `priority_research` 后面。

CLI 参数 `--top` 只限制终端展示数量，不限制实际处理数量；AI 复核会处理输入候选源中的全部候选。

## 核心字段对照

| 字段 | 类型/范围 | 来源 | 含义 | 使用注意 |
|---|---|---|---|---|
| `code` | 字符串 | 候选源 | 股票代码，例如 `sz.002815`。 | 仅用于标识和最终排序兜底。 |
| `signal_date` | 日期字符串 | 候选源 | MKF 信号日期。 | 技术上下文只使用截至该日的数据。 |
| `review_state` | 枚举 | AI 或兜底逻辑 | 研究分层状态。 | 第一排序键；不是买卖评级。 |
| `confidence` | 0–1 小数 | AI 或兜底逻辑 | AI 对 `review_state` 的结构化判断置信度。 | 不是上涨概率，也不是胜率。 |
| `research_summary` | 文本 | AI 或兜底逻辑 | 综合研究摘要。 | 用于人工快速理解，不替代验证。 |
| `technical_observations` | 字符串数组 | AI；缺失时用本地规则 | 技术观察，例如 MKF、K线、量价、20日位置。 | 可作为人工复核检查清单。 |
| `risk_flags` | 字符串数组 | AI；本地和新闻风险会补充 | 风险提示，例如长上影、量价背离、新闻风险词。 | 风险项不等于必然下跌，只表示需要核查。 |
| `local_score` | 1–10 小数 | 本地确定性规则 | 本地 MKF/K线/OHLCV 技术分。 | 第三排序键；不能单独代表最终排序。 |
| `model` | 字符串 | 中央 AI 配置 | 实际复核模型。 | 目前示例为 `Qwen3.8-27B-4bit`。 |
| `source_selection_reason` | 字符串 | 候选源 | 原始入选规则。 | 用于追溯候选为什么进入 AI 复核。 |
| `committee_summary` | JSON 对象 | AI | 模拟委员会各角色的 stance/notes。 | 单次 LLM 结构化输出，不是真实多代理投票。 |
| `committee_roles` | 字符串数组 | 固定配置 | 参与复核的角色列表。 | 包含技术、情绪、基本面、多空、策略、风控等。 |
| `technical_context_status` | 字符串 | 本地技术上下文 | 技术上下文构建状态。 | `ok` 表示可用；异常状态会降低本地评分。 |
| `candlestick_patterns` | 字符串数组 | 本地K线识别 | 信号日识别到的K线形态。 | 看涨形态加分，看跌形态减分。 |
| `candle_confirm_score` | 数值/空 | 本地K线确认 | K线确认强度。 | 高分说明信号日K线质量较强，不代表未来收益。 |
| `committee_disagreement_flags` | 字符串数组 | AI | 委员会分歧点。 | 分歧越多，越需要人工复核。 |
| `news_context_status` | 字符串 | 新闻上下文 | 新闻上下文状态。 | `refreshed` 表示已刷新；`no_data` 表示无新闻文本。 |
| `news_cache_status` | 字符串 | 新闻缓存 | 新闻缓存状态。 | 用于判断新闻数据是否来自刷新或缓存。 |
| `fatal_news_risks` | 字符串数组 | 新闻风险词 | 致命风险词命中。 | 非空时必须优先人工排查。 |
| `attention_news_risks` | 字符串数组 | 新闻风险词 | 关注级风险词命中。 | 非空时应纳入风险检查。 |
| `experimental_unvalidated` | 布尔 | 固定输出 | 实验性未验证标记。 | 为 `TRUE` 时不能宣称已验证胜率。 |

## 本地评分 local_score 规则

`local_score` 从 5.0 起步，按本地确定性技术条件加减分，最后裁剪到 1.0–10.0。

主要加分项：

| 条件 | 分值影响 | 含义 |
|---|---:|---|
| MKF 红线 `mkf_momentum` 和蓝线 `mkf_near` 位于 20–45 | +1.0 | 刚脱离低位且未过热。 |
| 中线 `mkf_inter >= 20` | +0.5 | 中线同步改善。 |
| 5日量能温和放大，`volume_ratio_5d` 在 1.1–3.0 | +0.5 | 放量但未异常。 |
| 信号日收盘位置 `candle_close_location >= 0.65` | +0.4 | 收盘靠近日内高位。 |
| 无明显长上影风险 | +0.3 | 日内抛压较小。 |
| 看涨反转上下文 | +0.6 | K线支持反转。 |
| 看涨延续上下文 | +0.5 | K线支持延续。 |
| 箱体突破确认 | +0.5 | OHLCV 结构确认。 |
| 20日量能确认健康 | +0.3 | 量能支持信号。 |
| 识别到看涨K线形态 | +0.5 | 例如看涨吞没、镊子底等。 |

主要减分项：

| 条件 | 分值影响 | 含义 |
|---|---:|---|
| 红线或蓝线 `>= 70` | -1.0 | MKF 接近高位，节奏风险上升。 |
| 5日量能异常放大，`volume_ratio_5d > 5.0` | -0.8 | 需排查冲高回落风险。 |
| 近5日涨幅 `> 18%` | -0.8 | 短期偏热。 |
| 近10日涨幅 `> 30%` | -0.6 | 中短期偏热。 |
| 长上影风险 | -0.8 | 上方抛压明显。 |
| 收盘接近日内低位，`candle_close_location <= 0.25` | -0.6 | 信号日承接较弱。 |
| 识别到看跌K线形态 | -0.8 | 形态风险。 |
| 技术上下文非 `ok` | -0.5 | 数据或上下文构建不完整。 |

## 状态解释和人工复核建议

| review_state | 人工处理优先级 | 建议动作 |
|---|---:|---|
| `priority_research` | 高 | 优先看技术结构、风险项、新闻证据和后续验证表现。 |
| `standard_research` | 中 | 可纳入观察池，但需要确认阻力、量价和消息面证据。 |
| `insufficient_evidence` | 低 | 暂不提升优先级，除非人工发现缺失数据或新证据。 |
| `risk_attention` | 风险优先 | 先查风险，不应按高分候选处理。 |
| `ai_unavailable` | 单独处理 | 不参与 AI 有效排序；需要先修复 AI 或复核兜底本地分。 |

## 示例解读

若一行数据为：

```text
review_state = standard_research
confidence = 0.78
local_score = 8.6
candlestick_patterns = candle_bullish_engulfing|candle_tweezer_bottom
risk_flags = 长上影线、未突破20日高点、动能不稳定
```

解释为：该股票的 MKF 和K线确认较强，本地技术分较高，但 AI 委员会认为仍存在上方抛压、阻力未突破或证据不足，因此放在 `standard_research`，而不是 `priority_research`。排序时，它会排在所有 `priority_research` 之后；只在 `standard_research` 内按 `confidence`、`local_score` 和 `code` 排名。

## 禁止误读

- `confidence=0.78` 不是“上涨概率 78%”。
- `local_score=8.6` 不是“可以买入”。
- `priority_research` 不是买入建议。
- `risk_attention` 不是必然下跌判断。
- `--top 10` 不是只处理 10 只股票，只是展示前 10 条有效 AI 评分结果。
- 本文排序规则只说明研究输出如何排列，不证明该排序能产生稳定超额收益。

## 代码依据

- 候选源字段和候选排序：`src/ashare_edge_scout/pmkf_mkf/candidates.py`
- AI 复核字段、状态、解析、排序和 summary `review_order`：`src/ashare_edge_scout/mkf_ai_review.py`
- 终端展示和 `--top` 行为：`scripts/review_mkf_ai.py`
- MKF AI 复核配置：`yaml/mkf_ai_review.yaml`
- MKF lag0..5 目标收益网格回测口径：`docs/2026-08-26-mkf-target-grid-backtest.md`
