# NCN 用户手册

可在浏览器离线打开的版本：[`USER_MANUAL.html`](USER_MANUAL.html)。

> 适用范围：A 股研究扫描、SMC/MKF 候选研究、Web 研究工作台、Demo Portfolio、Paper Monitor、AI 只读复核、前瞻证据归档与审计。
>
> 当前边界：**不连接券商、不提交真实订单、不使用杠杆、不执行无人值守实盘、不记录真实资金 P&L。**

## 1. 系统定位

NCN 是一个分阶段 production-adjacent 的 A 股研究系统。当前允许的功能包括：

- 本地日线数据检查与增量更新；
- 全市场和单股 Edge Scout 研究扫描；
- SMC、MKF、A 类候选研究；
- 新闻、K 线、PMKF/MKF 与 AI 只读复核；
- 手工研究 watchlist；
- Demo Portfolio 和 Paper Monitor；
- 不可覆盖的研究 publication、manifest、前瞻快照与成熟度审计；
- Web 工作台、审计日志和运维控制。

这些输出用于人工研究复核，不是投资建议，也不是成交、收益或执行证据。

## 2. 首次安装

### 2.1 环境要求

- macOS 或 Linux/WSL；
- Python `>=3.12,<3.15`；
- 本地数据目录 `PFrontStockData/`；
- 如需 AI 复核，需要可用的 OpenAI-compatible 模型服务和本地密钥文件。

### 2.2 安装项目

在项目根目录执行：

```bash
./scripts/setup.sh
```

安装完成后运行：

```bash
.venv/bin/python -m pytest -q
```

当前完整测试基准：

```text
497 passed, 3 skipped
```

## 3. 统一入口

### 3.1 交互菜单

```bash
./main.sh
```

使用方向键选择功能，按 Enter 执行。

### 3.2 查看帮助

```bash
./main.sh help
```

### 3.3 Web 控制

```bash
./main.sh start
./main.sh stop
./main.sh restart
./main.sh status
```

等价的底层命令：

```bash
./scripts/edge_scout_web_control.sh start
./scripts/edge_scout_web_control.sh stop
./scripts/edge_scout_web_control.sh restart
./scripts/edge_scout_web_control.sh status
```

Web 默认地址：

```text
http://127.0.0.1:9091
```

## 4. 日常推荐工作流

### 4.1 每日一键流程

```bash
./main.sh daily --top 10
```

该流程会按配置执行：

1. 检查并按需更新本地日线；
2. 运行 SMC 选股；
3. 检查同一信号日是否已经归档；
4. 运行新闻 + K 线 AI 复核；
5. 冻结前瞻证据；
6. 运行前瞻成熟度审计；
7. 输出人工复核摘要。

`daily` 不接受手工 `--as-of`，避免把回溯研究混入前瞻证据。

### 4.2 仅本地数据研究

```bash
EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh scan-local
EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-local --top 20
EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh single-local 600519
```

适合离线检查、结构验证和确定性复现。

### 4.3 数据更新

```bash
./main.sh update
```

只检查并增量更新研究数据，不运行扫描。

## 5. Edge Scout 扫描

### 5.1 全市场扫描

自动检查数据并扫描：

```bash
./main.sh scan
```

指定 T 日：

```bash
./main.sh scan --as-of 2026-08-21
```

仅使用本地数据：

```bash
./main.sh scan-local
```

主要输出：

```text
output/edge_scout/<run-id>/
```

常见文件：

- `daily_research_watchlist.csv`
- `candidates.csv`
- `watchlist.csv`
- `near_miss.csv`
- `discovery.csv`
- `reference_prices.csv`
- `results.jsonl`
- `summary.json`
- `report.md`
- `prospective_snapshot.json`
- `manifest.json`

`output/edge_scout/latest.json` 指向最新成功 publication。

### 5.2 单股分析

```bash
./main.sh single 600519
./main.sh single 600519 --as-of 2026-08-21
./main.sh single-local sh.600519
```

代码可写为六位数字，也可使用 `sh.` / `sz.` 前缀。

默认 T 日为可见最新数据日回退两个交易日；T+1 用于研究确认，T+2 仅进入人工观察。

## 6. SMC 候选研究

### 6.1 运行选股

联网检查数据：

```bash
./main.sh select --top 20
```

仅本地数据：

```bash
./main.sh select-local --top 20
```

输出目录：

```text
output/edge_scout/selections/<run-id>/
```

`candidates.json` 和 `candidates.csv` 保存完整候选集。

> **注意：`--top` 只限制终端显示，不限制实际处理或保存数量。**

### 6.2 选股并 AI 复核

```bash
./main.sh select-review --top 10
```

指定历史日期时只做研究复核，不进入前瞻归档：

```bash
./main.sh select-review --as-of 2026-08-15 --top 10
```

### 6.3 复核指定 selection run

```bash
./main.sh review-news \
  --selection-run output/edge_scout/selections/<run-id> \
  --top 10
```

推荐始终显式提供 `--selection-run`，确保 AI 复核与候选源严格绑定。

AI review 输出：

```text
output/edge_scout/news_reviews/<review-run-id>/
```

包括：

- `reviews.json`
- `news_ai_reviews_YYYYMMDD_HHMMSS.csv`
- `news.json`
- `summary.json`
- `manifest.json`

## 7. MKF / PMKF 研究

### 7.1 MKF 一键流程

```bash
./main.sh mkf-review --top 10
```

流程：

1. 运行独立 MKF 红蓝线上穿 20 后 YAML 配置允许 lag 范围内的候选源；
2. 对本次明确的 selection run 运行 AI 委员会复核；
3. 无候选时跳过 AI；
4. 不影响 SMC 候选、排序或 watchlist。

### 7.2 小资金 MKF

```bash
./main.sh mkf-small --top 10
```

候选源规则为：先识别上一交易日处于 MFK4 绿色背景块（`momentum/inter/near <= 20`），且红线 `momentum` 与蓝线 `near` 同时从 20 下方上穿到 20 以上、红蓝线仍低于 80 的上穿日；候选日取该上穿日当天及 `yaml/edge_scout_v1.yaml` 中 `mkf.candidate_selector.post_cross_lag_range` 允许的后续股票可交易日。当前配置为 `lag0-lag5`，即上穿日当天至上穿后第 5 个股票可交易日；停牌日不消耗 lag。

该模式保留主板、非 ST、价格、停牌等硬门槛，将 ADV20 门槛降为 5000 万。

### 7.3 只运行候选源

```bash
./main.sh select-mkf --top 10
./main.sh select-mkf-local --top 10
```

输出目录：

```text
output/edge_scout/mkf_candidate_selections/<run-id>/
```

### 7.4 复核指定 MKF run

```bash
./main.sh review-mkf-ai \
  --selection-run output/edge_scout/mkf_candidate_selections/<run-id> \
  --top 10
```

输出目录：

```text
output/edge_scout/mkf_ai_reviews/<run-id>/
```

> AI 复核默认分析数量由 `yaml/mkf_ai_review.yaml` 的 `review.max_candidates` 控制，当前默认 20；`--top N` 是本次运行的临时覆盖。超过上限的候选仍保留复核行但标记为 AI 未评分。

## 8. 统一 AI 模型配置

所有 AI 功能统一读取：

```text
yaml/ai_providers.yaml
```

业务配置：

```text
yaml/mkf_ai_review.yaml
yaml/news_ai_review.yaml
```

只能定义业务参数并引用中央文件，不能覆盖 provider/model/endpoint/key/timeout 等设置。

### 8.1 当前默认模型

```yaml
provider: local_finance
```

对应：

```text
Endpoint: http://ts.dorisw.kdns.fr:18090/v1
Model: Qwen3.8-27B-oQ4e-mtp
Credential: EDGE_SCOUT_LOCAL_AI_API_KEY 或 Key/ts.key
```

Doris Qwen 使用：

```yaml
extra_options:
  chat_template_kwargs:
    enable_thinking: false
```

这是为了让结构化复核返回最终 JSON，而不是长推理文本。

### 8.2 切换模型

修改中央文件顶部：

```yaml
provider: deepseek
```

或添加新的 backend：

```yaml
providers:
  new_provider:
    enabled: true
    name: New Provider
    base_url: https://example.com/v1
    model: model-name
    key_file: Key/new-provider.key
    api_key_env: NEW_PROVIDER_API_KEY
    timeout_seconds: 120
```

然后选择：

```yaml
provider: new_provider
```

MKF 与 SMC/news 会一起切换；运行时不会静默 fallback 到另一个 provider。

### 8.3 密钥优先级

1. provider 的非空 `api_key_env`；
2. provider 的 `api_key_file_env` 指定文件；
3. provider 的 `key_file`。

中央 YAML 禁止保存非空 inline `api_key`。

密钥目录 `Key/` 被 Git ignore。建议权限：

```bash
chmod 600 Key/*.key
```

### 8.4 AI 连接测试

仅测试 models：

```bash
PYTHONPATH=src .venv/bin/python -B scripts/smoke_ai_provider.py \
  --config yaml/ai_providers.yaml \
  --models-only
```

测试 models 和 tiny JSON chat：

```bash
PYTHONPATH=src .venv/bin/python -B scripts/smoke_ai_provider.py \
  --config yaml/ai_providers.yaml \
  --chat
```

当前 Doris 验证状态：

- `/v1/models` 可用；
- `Qwen3.8-27B-oQ4e-mtp` 在模型列表中；
- tiny JSON chat 可用；
- MKF 与 SMC/news 三候选隔离 smoke 均为 3/3 AI 成功。

## 9. Web 研究工作台

启动：

```bash
./main.sh start
```

打开：

```text
http://127.0.0.1:9091
```

主要区域：

1. **Research Watchlist**：手工维护股票代码，仅保存代码；
2. **K 线研究**：日线与 1m/5m/15m/30m/60m 研究 K 线；
3. **Demo Portfolio**：本地 demo 组合状态；
4. **Paper Monitor**：模拟现金、持仓状态、数据 freshness 与风险配置；
5. **PMKF/MKF**：单代码 PMKF/MKF 与预计算报告；
6. **Audit/Risk**：边界和近期审计事件。

Web 明确显示：

- Demo portfolio；
- Paper-only；
- No broker connection；
- Live orders off；
- No live order submission。

Web 使用 stdlib 串行 `HTTPServer`，不要改为线程服务器。

## 10. Demo Portfolio

配置位置：

```yaml
demo_portfolio:
  enabled: true
  state_root: output/edge_scout/demo_portfolios
  audit_root: output/edge_scout/audit_logs
  initial_capital: 20000.0
  max_portfolios: 5
  max_positions: 20
```

允许的状态：

```text
WATCH
RESEARCH_REVIEW
PAPER_PRE_BUY
PAPER_HOLD
PAPER_EXITED
```

所有修改写入 append-only JSONL 审计：

```text
output/edge_scout/audit_logs/demo_portfolio_events.jsonl
```

重置 capital 会保留 positions，并写入审计事件。

## 11. Paper Monitor

Paper Monitor 只读取 demo/paper 状态，并显示：

- simulated cash；
- simulated positions；
- paper risk controls；
- 本地研究数据 freshness；
- 最近审计事件。

默认：

```yaml
paper_trading:
  engine_enabled: false
  manual_intents_enabled: false
  allow_live_order_submission: false
```

`/api/paper/intent` 默认返回 403。系统没有 `/force_buy`。

## 12. 前瞻归档与审计

### 12.1 SMC + News 前瞻证据

```bash
./main.sh archive-smc-news
./main.sh audit-smc-news
```

### 12.2 通用 prospective audit

```bash
./main.sh audit
```

### 12.3 历史回放

```bash
./main.sh replay-smc-news --dry-run
```

回放标记为 `simulation_only`，不是前瞻证据，也不会写入 prospective archive。

不可覆盖和 hash 校验是 publication/audit 契约的一部分。不要手工修改已发布 run 中的 JSON/CSV/manifest。

## 13. 输出目录说明

```text
output/edge_scout/
├── <market-run-id>/
├── selections/
├── news_reviews/
├── mkf_candidate_selections/
├── mkf_ai_reviews/
├── demo_portfolios/
├── paper_trading/
├── audit_logs/
└── prospective_audits/
```

临时运行状态：

```text
.runtime/
```

AI smoke：

```text
.runtime/ai-smoke/
```

新闻缓存：

```text
.runtime/news_cache/
Message/
```

`output/`、`.runtime/`、`Message/`、`Key/` 均被 Git ignore。

## 14. 常用环境变量

| 变量 | 作用 |
|---|---|
| `EDGE_SCOUT_AUTO_UPDATE=0` | 跳过联网数据检查和下载 |
| `EDGE_SCOUT_DATA_ROOT` | 覆盖本地日线目录 |
| `EDGE_SCOUT_MINIMUM_LATEST_COVERAGE` | 覆盖最新日期覆盖率门槛 |
| `EDGE_SCOUT_WEB_HOST` | Web 监听地址，默认 `127.0.0.1` |
| `EDGE_SCOUT_WEB_PORT` | Web 端口，默认 `9091` |
| `EDGE_SCOUT_AI_PROVIDERS_CONFIG` | 覆盖中央 AI provider YAML 路径 |
| `EDGE_SCOUT_MKF_AI_CONFIG` | 覆盖 MKF 业务 YAML |
| `EDGE_SCOUT_NEWS_AI_CONFIG` | 覆盖 news 业务 YAML |
| `EDGE_SCOUT_LOCAL_AI_API_KEY` | 覆盖 Doris AI key |

## 15. 运维和调度

查看状态：

```bash
./main.sh status
```

日志：

```text
.runtime/edge_scout_web.log
```

调度配置：

```text
config/edge_scout_schedule.env.example
```

安装 macOS LaunchAgent：

```bash
./scripts/install_edge_scout_launchd.sh
```

LaunchAgent：

```text
com.vartw.stock-ncn.edge-scout
```

默认工作日 18:30 运行。

## 16. 故障排查

### 16.1 Web 无法启动

```bash
./scripts/edge_scout_web_control.sh status
```

查看：

```text
.runtime/edge_scout_web.log
```

确认 `.venv/bin/python` 存在，并检查端口 9091 是否占用。

### 16.2 数据加载失败

典型错误：

```text
missing_value: Record N field 'turn' must not be None
```

这表示 Parquet 数据不满足严格数据契约。不要放宽校验；应修复或重新下载数据。

### 16.3 AI 返回 401

先运行：

```bash
scripts/smoke_ai_provider.py --config yaml/ai_providers.yaml --models-only
```

检查：

- endpoint 是否包含正确 `/v1`；
- HTTP/HTTPS 是否与服务一致；
- `EDGE_SCOUT_LOCAL_AI_API_KEY` 是否为空或过期；
- `Key/ts.key` 是否与服务端一致；
- key 文件权限是否为 0600。

不要把 key 输出到终端、日志或 Git。

### 16.4 Qwen 返回 `{}` 或长推理文本

确认中央 backend 包含：

```yaml
extra_options:
  chat_template_kwargs:
    enable_thinking: false
```

### 16.5 AI 复核部分失败

查看 review run 中：

- `summary.json`
- `ai_error_counts`
- `ai_client_status`
- `ai_provider`
- `ai_model`
- `manifest.json`

AI 失败会 fail-closed 为 `ai_unavailable` 或 partial status，不会自动切换其他 provider。

### 16.6 调整 AI 复核股票数量

默认数量在业务 YAML 中配置：SMC/news 使用 `yaml/news_ai_review.yaml` 的 `review.max_candidates`，MKF 使用 `yaml/mkf_ai_review.yaml` 的 `review.max_candidates`，当前均为 20。命令行 `--top N` 会临时覆盖本次 AI 调用上限；输出仍保留完整候选复核行，超过上限的候选标记为 AI 未评分。

## 17. 安全边界与禁止事项

必须保持：

```yaml
allow_live_order_submission: false
production_enabled: false
```

当前禁止：

- broker 登录；
- live order；
- leverage；
- unattended real-money execution；
- real account IDs；
- real-money P&L；
- 用前复权研究数据作为成交或 fill 证据；
- 将 AI 文本直接转成订单；
- `/force_buy`。

当前允许：

- read-only research；
- demo portfolio；
- paper/simulation；
- PMKF/MKF dashboard；
- AI human-review prioritization；
- audit/risk/operational hardening。

## 18. 验证与开发

完整测试：

```bash
PYTHONPATH=src .venv/bin/python -B -m pytest -q --tb=short
```

静态检查：

```bash
PYTHONPATH=src .venv/bin/python -B -m compileall -q src scripts tests
node --check src/ashare_edge_scout/web_static/app.js
bash -n main.sh scripts/edge_scout_scan.sh scripts/edge_scout_web.sh scripts/edge_scout_web_control.sh
git diff --check
```

当前通过状态：

```text
497 passed, 3 skipped
```

## 19. 快速参考

### 每日人工研究

```bash
./main.sh daily --top 10
./main.sh start
open http://127.0.0.1:9091
```

### 本地确定性研究

```bash
EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-local --top 20
EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh single-local 600519
```

### MKF + AI

```bash
./main.sh mkf-review --top 10
```

### AI 模型切换

编辑：

```text
yaml/ai_providers.yaml
```

然后验证：

```bash
PYTHONPATH=src .venv/bin/python -B scripts/smoke_ai_provider.py \
  --config yaml/ai_providers.yaml \
  --chat
```

### Web 状态

```bash
./main.sh status
./main.sh restart
```

---

最后更新依据：项目完整测试 `497 passed, 3 skipped`；Doris `Qwen3.8-27B-oQ4e-mtp` models/chat 与隔离三候选 MKF、SMC/news smoke 均已通过。
