# SMC 子项目（smc/）

A 股 SMC 强势突破选股 + 新闻 AI 复核 + 前瞻归档/回放的独立子项目。
2026-09-27 从主仓分离（`scripts/edge_scout_scan.sh` 的 SMC 命令与
`src/ashare_edge_scout/` 的 SMC 专属模块迁入本目录）。

## 隔离契约（验收标准）

- **删除或移走整个 `smc/` 目录，对主仓 MKF/Web/研究流程零影响**：主仓测试收集
  （根 `pyproject.toml` 的 `testpaths=["tests"]`、`pythonpath=["src"]`）从不引用
  `smc/`；主仓代码不 import 本目录任何模块。
- 依赖方向**只允许 smc → main**：本目录代码可 import `ashare_edge_scout.*`
  （数据、信号、AI provider、研究工具），反向禁止。
- 共享资源保持在仓库根：`PFrontStockData/`（BaoStock 日线）、`.venv/`、`Key/`、
  `Message/`（MKF 新闻缓存）、`output/`（历史遗留输出只读）。

## 目录结构

```text
smc/
  smc.sh                 # 交互菜单/入口（smc-select / smc-review / smc-layer / review-news）
  aismc.sh               # MKF 风格 SMC AI 入口（选股走本目录 hub；review-mkf-ai 复用主仓 hub）
  scripts/smc_scan.sh    # SMC 自有控制 hub：select / daily / select-review / review-news /
                         #   post-smc-analysis / archive-smc-news / audit-smc-news / replay-smc-news
  scripts/*.py           # SMC 命令行脚本（select_stocks / review_smc_news / 归档 / 审计 / 回放等）
  src/ashare_smc/        # SMC 专属 Python 包（sys.path bootstrap，不做 pip 安装）
  yaml/                  # SMC 配置（见下方“配置副本”约定）
  tests/                 # pytest 套件；conftest.py 负责双 src 路径注入
  docs/                  # SMC 契约文档
```

运行方式（仓库根）：

```bash
./.venv/bin/python -m pytest smc/tests -q   # SMC 测试
./smc/scripts/smc_scan.sh help              # SMC hub 用法
```

## 配置与路径约定（关键假设，勿改错）

- SMC 业务 yaml 放在 `smc/yaml/` 时，其 `project_root` 解析为 `smc/`；因此
  `ai_config: "yaml/ai_providers.yaml"` 会解析到 **`smc/yaml/ai_providers.yaml`**，
  其中的 `key_file: ../Key/xxx.key` 以 `smc/` 为根 → 实际密钥仍是仓库根 `Key/`。
- `smc/yaml/ai_providers.yaml`、`mkf_news_context.yaml`、`edge_scout_v1.yaml` 是主仓
  `yaml/` 同名文件的**受维护副本**（文件头有说明）。主仓 provider/模型/密钥或 MKF
  语义变更时，必须同步刷新副本（副本仅重写相对路径，不改业务语义）。
  `news_ai_review.yaml`、`smc_ai_review.yaml` 为 SMC 独有，已整体移入（主仓不留）。
  `baostock_config.yaml` 不复制：数据更新委托主仓 hub 的 `update`。
- MKF 与 SMC 新闻复核解析同一 provider 的等价性由
  `smc/tests/test_smc_ai_provider_parity.py` 守护（原主仓测试移植）。
- SMC 原生新闻缓存：`smc/.runtime/news_cache/`（可再生；hub 显式传入）。
  `audit`/`replay`/`archive` 裸跑 CLI 时的旧默认值（`output/edge_scout/...`、
  `PFrontStockData`）保留为遗留兼容，hub 调用一律显式传 root，不依赖默认值。
- SMC 输出根默认 `仓库根/smc-output/`（`SMC_OUTPUT_ROOT` / `EDGE_SCOUT_OUTPUT_ROOT`
  可覆盖）；分离前的历史输出仍在 `output/edge_scout/`，回放归档保护同时覆盖新旧路径。

## 环境变量

| 变量 | 作用 |
| --- | --- |
| `SMC_CONFIG` / `EDGE_SCOUT_CONFIG` | SMC 选股配置（默认 `smc/yaml/edge_scout_v1.yaml`） |
| `SMC_NEWS_AI_CONFIG` / `EDGE_SCOUT_NEWS_AI_CONFIG` | 新闻复核配置（默认 `smc/yaml/news_ai_review.yaml`） |
| `EDGE_SCOUT_SMC_AI_CONFIG` | `aismc.sh` 传给主仓 `review-mkf-ai` 的 SMC AI 配置 |
| `SMC_OUTPUT_ROOT` / `EDGE_SCOUT_OUTPUT_ROOT` | 输出根（默认 `仓库根/smc-output`） |
| `EDGE_SCOUT_SCAN_SCRIPT` | 主仓 hub 路径覆盖（`update`/`review-mkf-ai` 委托目标） |
| `SMC_SCAN_SCRIPT` | SMC hub 路径覆盖（`smc.sh` 的 select/review 委托目标） |
| `EDGE_SCOUT_DATA_ROOT` / `EDGE_SCOUT_AUTO_UPDATE` / `VENV_PYTHON` | 与主仓 hub 同语义 |

## 边界

只读研究：不连接券商、不提交订单、不计算 P&L、不构成投资建议；
`production_enabled=false` 的 fail-closed 约束继承自主仓配置。
