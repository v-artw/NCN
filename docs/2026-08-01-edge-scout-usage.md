# Edge Scout 只读研究扫描使用说明

> 本说明用于运行 `ashare_edge_scout`，查看全市场扫描、单股分析和 `near_miss.csv`。输出仅用于人工研究，不是投资建议，不连接券商，不提交真实订单。

## 数据自动更新

默认入口 `./scripts/edge_scout_scan.sh` 会先检查 BaoStock 最新交易日：

1. 本地最新日期等于远端最新交易日，且本地最新日文件覆盖率至少 95%：跳过下载；
2. 远端日期更新、本地目录为空或最新覆盖率不足：使用 `--no-clean` 增量下载；
3. 远端检查失败、下载失败率超过门槛、或下载后本地日期仍未追平：停止扫描；
4. 不会清空已有 `PFrontStockData/`。

可用环境变量：

```bash
EDGE_SCOUT_DATA_ROOT=/path/to/PFrontStockData
EDGE_SCOUT_AUTO_UPDATE=0
EDGE_SCOUT_DOWNLOAD_WORKERS=4
EDGE_SCOUT_DOWNLOAD_MAX_FAILURE_RATE=0.10
EDGE_SCOUT_MINIMUM_LATEST_COVERAGE=0.95
```

`EDGE_SCOUT_AUTO_UPDATE=0` 表示完全跳过联网检查和下载，只扫描现有本地数据。BaoStock 前复权数据仅用于研究信号，不得作为执行价格、撮合或收益输入。

## 1. 一句话定位

Edge Scout 当前是：

```text
A 股只读研究扫描器 / 候选观察工具 / 历史信号辅助筛选工具
```

不是：

```text
自动盈利股票预测器 / 实盘荐股系统 / 自动交易系统
```

当前 `production` A 级候选仍禁用，主要可用结果是 `near_miss.csv`。

## 2. 运行全市场扫描

默认无参数运行，输出 T 日 setup 与 T+1 价格/量能状态明确的研究观察样本：

```bash
./scripts/edge_scout_scan.sh market
```

默认扫描日期 = **T 信号日自动回退 2 个交易日**（即 T=最新数据日往前 2 个交易日，T+1=昨日，T+2=最新数据日）。这样可以观察 T+1 收盘价格与量能；TOP 表中的 `✓` 还要求 T 日 setup 有效。T+2 只进入人工观察阶段，不代表可成交或应入场。

全市场扫描通常需要数分钟。CLI 会将实时进度写到 `stderr`，阶段包括 `data_admission`（读取和校验 parquet）、`signal_scan`（逐证券评分）和 `publication`（原子发布）。阶段切换、每 100 个证券、每 10 秒或阶段完成时会立即刷新，例如：

```text
progress stage=data_admission processed=100/7337 (1.4%) | current=sh.000114
```

若运行的是修复前已经启动的旧进程，需要先用 `Ctrl-C` 中止，再重新执行脚本；运行中的 Python 进程不会自动加载新代码。

也可显式指定 T 信号日：

```bash
./scripts/edge_scout_scan.sh market --as-of 2026-07-28
```

正常输出应类似：

```text
status=success
as_of=2026-07-28
as_of_is_t_signal_day=True
observation_day=T+2
candidate_count=0
watchlist_count=0
near_miss_count=100
input_code_count=7336
admitted_count=3521
rejected_count=3815
scored_count=415
unexpected_error_count=0
quantity_conservation_valid=True
```

重点看：

- `status=success`：扫描完成；
- `scored_count > 0`：有股票完成评分；
- `unexpected_error_count=0`：没有运行时异常；
- `near_miss_count=100`：输出 100 个观察候选；
- `quantity_conservation_valid=True`：数量审计通过。

如果出现：

```text
scored_count=0
no_tier_reason_counts 中有 unexpected_error
```

不要解释为市场无候选，应先检查程序或数据边界问题。

## 3. 查看最新扫描结果

最新结果指针：

```bash
cat output/edge_scout/latest.json
```

示例：

```json
{
  "run_directory": "market-20260731_223043",
  "as_of": "2026-07-29",
  "near_miss_count": 100,
  "status": "success"
}
```

实际结果目录：

```text
output/edge_scout/<run_directory>/
```

常见文件：

| 文件 | 用途 |
|---|---|
| `summary.json` | 汇总统计，先看这个 |
| `candidates.csv` | V1 强制为空的保留兼容文件 |
| `watchlist.csv` | B 级候选，当前可能为空 |
| `near_miss.csv` | 当前主要观察候选表 |
| `discovery.csv` | CNstock 风格研究发现层，含启动信号、PMK、K 线、量价证据与过滤原因 |
| `daily_research_watchlist.csv` | 每日统一人工观察主表，按四个 research-only 阶段排序 |
| `reference_prices.csv` | TOP 10 研究参考价（参考买入/止损/止盈） |
| `results.jsonl` | 逐股票审计明细 |
| `report.md` | Markdown 报告（含 TOP 研究参考价表） |
| `manifest.json` | 输出文件 hash 清单 |

## 4. 如何使用 `near_miss.csv`

`near_miss.csv` 是观察候选表，不是买入清单。

查看前 20 名：

```bash
head -21 output/edge_scout/<run_directory>/near_miss.csv
```

字段说明：

| 字段 | 含义 |
|---|---|
| `rank` | 按 `edge_score` 从高到低排序 |
| `code` | 股票代码 |
| `as_of` | 扫描日期，即 T 日 |
| `edge_score` | 综合分 |
| `base_quality_score` | 基础质量分 |
| `timing_score` | 时机分 |
| `risk_score` | 风险分 |

人工筛选建议：

1. 先看 `edge_score` 前 20 名；
2. 优先关注分数较均衡的股票，不要只看单项高分；
3. 再看 `results.jsonl` 里的 `t1_reason`、`limitations`、`admission_error_code`；
4. 人工复核 K 线、成交量、公告、财报、行业和市场状态；
5. 只作为观察池，不要自动买入。

## 5. 使用研究发现层

屏幕会额外打印满足研究过滤且启动信号达到 2/5 的发现层 TOP；完整结果在 `discovery.csv`。排序依次优先：`discovery_eligible=true`、启动信号数量、`discovery_score`，未通过过滤的行仍保留并写明 `discovery_rejection_reasons`，便于审计。

发现层级：

| 层级 | 含义 |
|---|---|
| `strong_start` | 4/5 或 5/5 启动信号 |
| `profit_shadow` | 3/5 启动信号 |
| `early_low_position` | 2/5 启动信号 |
| `general_observation` | 0/5 或 1/5 启动信号 |

`discovery_eligible` 只表示满足价格、成交额、当日涨幅、5 日涨幅、换手率和量比研究过滤。它不会使样本成为 V1 setup、有效 T+1 确认、production candidate 或买入建议。

每日主表的四个阶段依次为：`confirmed_watch`、`setup_watch`、`cnstock_pool_watch`、`discovery_watch`。兼容池另外使用 `strong_start`（4+/5，基础分至少 60）、`profit_shadow`（3/5，基础分至少 75）和 `low_position_discovery`（2/5，基础分至少 75）命名。它与广义发现层的 `early_low_position` 是不同字段，不应混用。

分数字段也必须分开解释：`edge_score` 是 V1 评分，`discovery_score` 是包含 Edge 分的广义发现排序，`cnstock_discovery_rank` 是独立的 CNstock V4/V5 兼容软排名。

## 6. 查询单只股票审计明细

例如想查看 `sz.002847`：

```bash
grep '"code": "sz.002847"' output/edge_scout/<run_directory>/results.jsonl
```

重点看这些字段：

- `status`：是否完成评分；
- `tier`：当前分层；
- `edge_score`：综合分；
- `t1_confirmed`：T+1 是否确认；
- `t1_reason`：T+1 原因；
- `admission_error_code`：准入或边界原因；
- `limitations`：限制说明。

如果 `as_of` 是最新交易日，没有下一根 T+1 bar，可能看到：

```text
admission_error_code=missing_t1_bar
t1_reason=missing_t1_bar
```

这是稳定边界状态，不是程序崩溃。

## 7. 单股分析

运行（默认自动回退 2 个交易日到 T，观察 T+1 状态并进入 T+2 人工观察；也可用 `--as-of` 显式指定 T）：

```bash
./scripts/edge_scout_scan.sh single sh.600023
./scripts/edge_scout_scan.sh single sh.600023 --as-of 2026-07-28
```

示例正常结果：

```text
code=sh.600023
as_of=2026-07-30
input_code_count=1
status=admitted
admission_error_code=missing_t1_bar
tier=near_miss
edge_score=15.0000
limitations=research_approximation_only,missing_t1_bar
```

如果数据质量不合格，可能看到：

```text
status=rejected
admission_error_code=data_load_failed
```

这表示该股票数据不能用于本次研究扫描。

## 8. 当前结果如何解读

当前常见情况：

```text
candidate_count=0
watchlist_count=0
near_miss_count=100
```

含义：

- 没有 A 级 production candidate；
- 没有 B 级 watchlist；
- 有 100 个 C 级 near-miss 观察候选；
- 这些候选只能用于人工研究，不是实盘买入建议。

## 8.5 TOP 10 研究参考价（屏幕输出）

运行全市场扫描后，屏幕末尾会打印 TOP 10 研究观察候选的参考价表：

```text
#  code         tier        edge   T+1     参考买入   参考止损   止盈1.5R   止盈2R   风险距
 1  sh.603043    near_miss 39.000     ✓   13.5600  12.9568  14.4648  14.7664  4.45%
```

字段含义：

| 字段 | 含义 |
|---|---|
| `有效确认` | `✓` = T 日 setup 有效且 T+1 价格/量能研究观察通过；仍不代表订单、成交或买入资格 |
| `研究触发参考` | T 日信号高点 `signal_high`，不是 T+2 开盘价或成交价 |
| `参考止损` | 参考止损价 = `min(signal_low - 0.10*ATR14, 参考买入 - 1.5*ATR14)` |
| `止盈1.5R` | 参考分批止盈价 = 参考买入 + 1.5 × 每股风险（R） |
| `止盈2R` | 参考目标止盈价 = 参考买入 + 2.0 × 每股风险（R） |
| `风险距` | 每股风险 / 参考买入（V1 要求可交易范围在 2.5%–6.0%） |

选择逻辑：**T+1 已确认优先**，已确认样本内部按 A 级、B 级、C 级排，同级按 `edge_score` 从高到低，取前 10 只。默认（无 `--as-of`）扫描时 T+1 有真实 bar，TOP 10 通常全部为 ✓。

**风险距过滤**：TOP 参考价表和 `reference_prices.csv` 只展示参考风险距落在 V1 可交易范围 `[2.5%, 6.0%]` 内的样本；参考风险距超过 6% 的样本已从 TOP 表排除（仅供观察，不满足 V1 入场风险约束）。若所有样本均超范围，TOP 表显示"无候选"。

**必须理解**：

1. 这些是研究近似参考价，不是可执行价格、真实成交价或投资建议；
2. T+2 仅进入人工观察阶段；即使有效确认（✓）也未证明开盘可成交；
3. `PFrontStockData/` 是前复权研究数据；扫描准入会过滤 T 日停牌和接近主板涨停的记录，但不模拟撮合、滑点或费用；
4. 当前 `production` 候选在 MVP 下不可达，TOP 10 通常全部来自 C 级 near-miss。

## 9. 风险边界

必须记住：

1. `PFrontStockData/` 是前复权研究数据，不能作为真实成交价；
2. 当前没有完整 PIT 股票池和真实执行价证明；
3. 当前没有真实订单、持仓、现金、权益曲线；
4. 当前没有完整滑点、手续费、印花税、涨跌停和停牌撮合；
5. 输出不能保证未来盈利；
6. 不得自动下单；
7. 不得把 `near_miss.csv` 当作投资建议。

## 10. 推荐日常流程

```text
1. 更新行情数据
2. 运行全市场扫描
3. 查看 latest.json
4. 打开 summary.json 确认扫描健康
5. 查看 discovery.csv 的 2/5 以上合格样本与 near_miss.csv 前 20 名
6. 用 results.jsonl 查单只股票审计原因
7. 人工复核 K 线、公告、财报、行业和市场状态
8. 只做研究记录，不自动交易
```

## 11. 健康检查清单

每次扫描后确认：

```text
status=success
scored_count > 0
unexpected_error_count=0
quantity_conservation_valid=True
```

如果 `near_miss.csv` 为空，先检查：

1. `summary.json` 中 `scored_count` 是否为 0；
2. `no_tier_reason_counts` 是否出现 `unexpected_error`；
3. `results.jsonl` 是否有 detail；
4. `as_of` 是否是最新交易日且缺少 T+1；
5. 数据是否更新完整。

只有当扫描健康且规则确实无候选时，才能把空结果解释为“本日没有观察候选”。
