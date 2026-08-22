# NCN Agent Instructions

## Boundaries

- NCN is transitioning from a read-only A-share research scanner into a phased production-adjacent research/trading system. The current authorized phase allows research signal generation, portfolio-style demo analysis, paper/simulation workflows, PMKF/MKF research dashboards, risk controls, audit logs, and operational hardening.
- Real-money/live trading remains prohibited until a separate explicit authorization updates this governance again. Do not add live broker login, live order submission, leverage, custody/settlement behavior, or unattended real-money execution in the current phase.
- Portfolio/SuperTrader features may be migrated only as demo, analysis, paper/simulation, or risk-review workflows by default. Any UI that resembles trading must be clearly labeled with its mode and must fail closed unless a future live-trading authorization and runtime flag explicitly enable real broker actions.
- `PFrontStockData/` contains adjusted research data. It may be used for clearly labeled offline research, paper/simulation, and demo analysis; never use it as live execution, live matching, or real-money fill evidence.
- Keep `production_enabled: false` in `yaml/edge_scout_v1.yaml` unless a future governance change explicitly authorizes live trading. Production-adjacent research/paper/demo hardening must use separate, explicit mode flags and must not imply live order permission.
- Keep runtime imports within `ashare_edge_scout` or declared third-party dependencies. Do not add runtime dependencies on `Stock/CN`, `CNstock`, or `a_share_short_swing`; port required code into NCN or use documented files as references.
- Preserve a hard separation between research watchlists, demo/paper portfolios, and any future live portfolio. Credentials, account identifiers, broker sessions, real orders, and real-money P&L must never be committed.

## OpenCode Role

- OpenCode should work as a senior Python engineer with strong ownership of correctness, maintainability, testability, and simple project-local implementations.
- OpenCode should also apply the judgment of a senior China A-share research trader with a long-term win rate above 60%.
- Use the trader perspective to improve research quality and phased production-adjacent safety: A-share market-structure awareness, signal interpretation, false-positive reduction, risk recognition, practical review of scanner outputs, paper/simulation controls, and demo portfolio analysis.
- Do not convert trader judgment into unattended live broker actions, return promises, or real-money execution. In the current phase, any portfolio/trader behavior must be demo, paper/simulation, or human-review oriented unless future governance explicitly authorizes live trading.

## Problem Steelman Gate

- For complex, ambiguous, high-risk, or direction-setting work, do not answer or implement immediately. First steelman the user's problem.
- Before giving a solution, state: assumptions the user may be making but has not said out loud; missing information that would significantly change the answer; the most common mistake people make with this type of question; and what could go wrong if the project acts on a plausible but unverified answer.
- Then ask the single most useful clarifying question for this specific NCN situation.
- Apply this gate to strategy research, scanner/watchlist logic, data validation design, backtest methodology, architecture changes, ambiguous bugs, and any change that could affect research conclusions.
- Skip this gate for simple bug fixes, clearly specified mechanical edits, formatting, git inspection, focused validation, and other tasks where success criteria are already explicit.
- After the user answers, give the recommendation, reasoning, validation target, what not to do yet, and the smallest next action.
- Optimize for reducing false confidence, avoiding overfitting, preserving validation consistency, and minimizing unnecessary code changes.

## Current Project Phase

- The user's ultimate economic objective is profitable A-share decision support, not academic publication or research for its own sake. Every strategy task must have a credible path to improving the practical quality of stocks surfaced for human review.
- NCN's direct, testable objective remains selected-stock precision, false-positive reduction, and safe staged operationalization. Historical hit-rate, paper/simulation results, or demo portfolio results do not prove real profit and must not be presented as return promises.
- Treat time, data, and compute as economic resources. Prefer the smallest decisive test, stop failed directions quickly, and do not create analysis artifacts that cannot change the next scanner/watchlist/paper-review decision.
- The current project phase prioritizes improving selected-stock quality while preparing demo/paper production-adjacent workflows, auditability, and risk controls.
- Define win-rate improvement as research-selection and paper/simulation quality, not guaranteed profit optimization: reduce false positives, strengthen multi-signal confirmation, filter weak or risky setups, and make human review prompts clearer.
- Prefer changes that improve candidate precision even if they reduce the number of selected stocks. A smaller, higher-quality watchlist is better than broad coverage in this phase.
- Treat A-share trader judgment as a review lens for signal quality: trend context, volume-price confirmation, candle/structure quality, sector or market regime fit, liquidity, volatility, and obvious event or data risks.
- When changing scanner logic, make the selection reason explainable from available data. Avoid opaque scoring tweaks that cannot be reviewed by a human trader.
- Preserve deterministic, testable research behavior. Use historical/local data and explicit indicators; do not introduce live execution assumptions, hidden manual overrides, or unverifiable market opinions.
- Do not optimize for portfolio return, execution performance, transaction simulation, personalized trading advice, or guaranteed outcomes in this phase.
- Keep strategy work decision-oriented and resource-bounded. Before each study, state one actionable hypothesis, a fixed candidate set, success/failure thresholds, the maximum data/compute budget, and the implementation decision that follows each outcome.
- Stop a strategy direction when it misses its pre-registered precision/stability threshold. Do not repeatedly mine the same historical period, add post-hoc filters, or expand candidate combinations merely to produce a positive result.
- Prefer changes that can improve the practical usefulness of the next read-only watchlist. Research artifacts are supporting evidence, not the product goal; avoid analyses that cannot lead to a clear keep, reject, or implement decision.
- For an explicitly authorized autonomous strategy search, do not pause for routine confirmation between hypotheses, source reviews, implementations, or bounded evaluations. Continue through the pre-registered decision sequence unless a destructive/external action, credential need, legal/licensing issue, material cost, or ambiguous user boundary requires confirmation.
- Record every autonomous exploration direction in the newest `HANDOFF.md` entry: hypothesis, source/data provenance, fixed rules, success and failure thresholds, compute budget, validation result, and the resulting keep/reject/implement decision. Negative results are required evidence and must not be omitted.
- A target such as 70% selection precision is not satisfied by a point estimate alone. Require the pre-registered minimum sample, annual coverage, out-of-sample stability, and confidence-bound gates; never lower those gates merely to end the search.

## OpenCode Model Routing

- Default to the low-cost model `openai/Ornith-1.0-35B-4bit` for routine OpenCode work when success criteria are explicit and easy to verify.
- Use `openai/Ornith-1.0-35B-4bit` for bounded mechanical tasks: compact/summarize, handoff compression, git status/diff/log inspection, commit/push preparation, simple file discovery, formatting checks, straightforward documentation updates, and concise handoff drafting.
- Automatically escalate to `gsykj/gpt-5.6-sol` when a task is high-stakes or ambiguous: scanner strategy changes, win-rate improvement logic, A-share signal/risk analysis, architecture decisions, cross-file refactors, debugging unclear failures, test design, reviewer-facing synthesis, or any task requiring senior Python plus senior A-share trader judgment.
- Escalate from `openai/Ornith-1.0-35B-4bit` to `gsykj/gpt-5.6-sol` after repeated failed attempts, conflicting evidence, unclear root cause, suspected correctness risk, or when internet research changes the implementation approach.
- Do not rely on `openai/Ornith-1.0-35B-4bit` for ambiguous trading interpretation, broad codebase design, non-obvious correctness decisions, or changes to stock-selection criteria.
- Keep GitHub push agents conservative regardless of model: inspect status/diff/remote/branch first, avoid destructive git operations, stop on conflicts or unexpected remote state, and ask for user confirmation before actions visible to others.

## Internet Research And Citations

- When Claude or OpenCode encounters a blocker, unfamiliar error, ambiguous external behavior, version-specific tooling issue, or repeated failed attempt, search the internet for authoritative information before continuing to guess.
- Prefer official documentation, upstream issue trackers, release notes, and well-established technical references. Use community posts only as supporting evidence unless they contain the exact working procedure being evaluated.
- Include the URLs used in the final answer or handoff notes when internet research influenced the solution. Cite links precisely enough that reviewers can verify the source and avoid hallucinated fixes.
- If internet access fails or a source is blocked, state that clearly and ask the user to paste the relevant content or provide another accessible source.

## Remote Internet Proxy

- The local machine exposes HTTP, HTTPS CONNECT, and SOCKS5 proxy service on `127.0.0.1:1082`.
- When WSL, Doris, or another remote test environment cannot download dependencies or reach the internet, use the local `1082` proxy through an SSH reverse tunnel. A remote host cannot use the local machine's `127.0.0.1:1082` directly.
- Preferred session-scoped pattern for Doris: `ssh -R 18082:127.0.0.1:1082 ...`, then run the remote command with `HTTP_PROXY=http://127.0.0.1:18082`, `HTTPS_PROXY=http://127.0.0.1:18082`, and, when SOCKS is required, `ALL_PROXY=socks5h://127.0.0.1:18082`.
- Use `ExitOnForwardFailure=yes` and verify the remote proxy path with a bounded `curl` request before dependency installation or internet research.
- Keep proxy use temporary and command-scoped. Do not write proxy settings into global shell profiles, system network configuration, repository secrets, or committed environment files unless the user explicitly requests persistent configuration.
- Do not expose the reverse-forwarded proxy on a non-loopback remote address. Use a high, unoccupied remote loopback port and close it when the SSH session ends.

## Session Continuity

- `HANDOFF.md` is the single source of truth for cross-session continuation.
- At the start of every substantive task, read the newest relevant `HANDOFF.md` entry before making assumptions from conversation history.
- Before reporting work as complete, blocked, paused, or ready for another agent, update `HANDOFF.md` with the current state and exact next action.
- The newest `HANDOFF.md` entry must be enough for a fresh agent to continue without reading the previous chat transcript.
- If work is split between agents, each agent must write only verified facts to `HANDOFF.md`: what changed, what was validated, what remains, and what must not be repeated.
- Do not store ephemeral task state in `AGENTS.md`; store it in `HANDOFF.md`.
- Do not rely on unstated chat context after session restart. If it matters for continuation, write it into `HANDOFF.md`.

## OpenCode Handoff

- After each OpenCode task, create or update `HANDOFF.md` before reporting the task as complete.
- Treat `HANDOFF.md` as a reviewer handoff, not a changelog, diary, or design document. It should help another reviewer quickly understand what changed, how it was validated, and what deserves attention.
- Keep the newest task handoff at the top. Use one concise entry per completed task unless the user explicitly asks for a broader summary.
- For unfinished work, the newest entry must explicitly include current status, files touched, validation already run, validation not yet run, exact next recommended action, and rejected or stopped directions that must not be repeated.
- Use this entry shape: `Task`, `Changed Files`, `Behavior / Logic Changes`, `Validation`, and `Risks / Review Notes`.
- Under each field, write short bullets with only reviewer-relevant facts. If there is nothing important for a field, write `None`.
- Do not paste large diffs, full logs, full test output, repeated implementation details, speculative notes, or long reasoning traces.
- Mention failed or skipped validation only when it affects reviewer confidence. Include the exact command or check name, not full output.
- Prefer updating/removing stale handoff content over accumulating redundant entries that waste review context.

## Package And Data Flow

- This is a single `src`-layout Python package (`ashare_edge_scout`); package discovery and pytest's `src` path are configured in `pyproject.toml`.
- Scans read validated per-code Parquet from `PFrontStockData/` and atomically publish immutable runs under `output/edge_scout/<run-id>/`; `output/edge_scout/latest.json` points the Web UI at the latest successful run.
- `src/ashare_edge_scout/research_web.py` is the Web/API entrypoint. It combines published scan rows, local daily bars, and the native HTTPS adapters in `intraday_data.py`; it must not import legacy projects.
- Keep the Web server on the stdlib serial `HTTPServer`. Concurrent PyArrow reads under Python 3.14 caused native crashes; local UI throughput does not justify switching back to a threaded server.
- Sina snapshots and Eastmoney `1m/5m/15m/30m/60m` bars have no exchange latency SLA. Preserve provider/source timestamps, freshness, forming-bar state, warnings, bounded retry/cache behavior, and explicit last-observation fallback; never present them as execution feeds.
- `config/research_watchlist.json` is an ignored, atomically written local file containing codes only. `.runtime/` is ignored process state/logging for the managed Web service.

## Commands

- Set up the supported environment with `./scripts/setup.sh`; it creates `.venv` and installs the package plus pytest. Supported Python is `>=3.12,<3.15`.
- Run the default suite with `.venv/bin/python -m pytest -q`. For a focused test, pass a file or node id, for example `.venv/bin/python -m pytest tests/test_edge_scout_config.py -q`.
- `./main.sh` without arguments is a TTY-only arrow-key menu. For automation use `./main.sh start|stop|restart|status`, `scan [--as-of DATE]`, `scan-local`, `single <code> [--as-of DATE]`, `single-local <code>`, or `update`.
- `./scripts/edge_scout_scan.sh` is the underlying scanner wrapper and supplies `PYTHONPATH=src` plus `.venv`. It checks BaoStock freshness and incrementally updates with `--no-clean` by default; set `EDGE_SCOUT_AUTO_UPDATE=0` for deterministic local-data-only work.
- Manage the background Web only through `./scripts/edge_scout_web_control.sh start|stop|restart|status` (or `main.sh`); it owns `.runtime/edge_scout_web.pid`, logs, PID validation, and HTTP health checks. `edge_scout_web.sh` is the foreground entrypoint.
- Use `./scripts/edge_scout_production.sh` for the calendar/freshness-gated production wrapper. It fails closed unless the approved calendar path, SHA-256, coverage, freshness, and atomic publication checks pass.
- After Web changes, at minimum run the focused Python test, `node --check src/ashare_edge_scout/web_static/app.js`, and `git diff --check`. Playwright is intentionally separate in ignored `.venv-playwright`; the default setup/test suite does not install or require it.

## Test Environment Resource Priority

- Available test environments, in priority order for every backtest and test run:
  1. **WSL** - host `10.20.98.161`, port `22`, user `adminwsl`. FIRST choice when the network is reachable and the remote environment is set up. Use when code changes can be synced via `scripts/remote_test_env.sh`.
  2. **Doris (ts.dorisw.kdns.fr)** - host `ts.dorisw.kdns.fr`, port `56731`, user `chinaadmin`. SECOND choice when the above two are unavailable or when backtests specifically require the Doris data layer.
  3. **Local** (本地环境) - LAST resort only. Only use local `.venv` and `PFrontStockData` when both WSL and Doris are unavailable (network unreachable, environment not set up, or dependency conflict).
- Always attempt resources in the order above, from 1 to 3. Do NOT skip WSL or Doris in favor of local unless they are genuinely unreachable. The default behavior is REMOTE-FIRST: try WSL first, then Doris, and only fall back to local when remote options fail.
- Record which environment was actually used for a given test/backtest run in `HANDOFF.md` so reviewers can track consistency across runs.
- This order is permanent unless the user explicitly updates it.

## Test Environment Hardware Profile

Each environment must be utilized with resource planning appropriate to its hardware. The table below documents the hardware configuration of all three environments and guides concurrency/memory settings for backtests and test runs.

| Field | WSL (P16V) | Doris (Maxstudio) | Local (MacBook Air) |
|-------|-----------|-------------------|-------------------|
| Hardware | ThinkPad P16V (i7) | Maxstudio (M4 Max) | MacBook Air (M4) |
| Total RAM | 32 GB | 64 GB | 24 GB |
| OS | Windows + WSL2 (Ubuntu) | macOS | macOS |
| Available for NCN backtests | ~2 GB (after omlx service reserves ~30 GB) | ~34 GB (after omlx service reserves ~30 GB) | ~24 GB (dedicated to NCN) |
| CPU (logical cores) | 20 (from prior study observation) | TBD (benchmark on first use) | TBD (benchmark on first use) |
| Constraints | omlx service requires ~30 GB, leaving only ~2 GB for NCN. Keep worker count LOW (e.g. 4-8 max). Monitor closely. | omlx service requires ~30 GB, leaving ~34 GB for NCN. Can sustain higher worker counts (e.g. 12-16). | Dedicated to NCN work. Can run full local test suites without remote considerations. |
| Connectivity | Via Windows portproxy SSH. Network-dependent; falls back to local if unreachable. | Via SSH (port 56731). Network-dependent; fallback to local if unreachable. | Always available. Use for lightweight tests, single-stock scans, and CI. |
| Notes | - Prior study confirmed P16V with 8 workers sustained load ~8.00 with ~14 GB available and no swap. Current system is 32 GB total; omlx service reserves ~30 GB, leaving ~2 GB. Adjust worker count accordingly. - Do NOT run signal hit-rate studies on this host without adjusting for omlx memory reservation. | - Maxstudio provides Doris data layer via SSH (port 56731). Best suited for backtests requiring Doris data access. - Has headroom for omlx service + NCN backtest workloads. | - Ideal for local scan, single-stock analysis, unit tests, and small-scale backtests that do not require Doris. - Limited to 24 GB; do not run large parallel studies that exceed available memory. |

### Concurrency Guidelines

- **WSL (P16V)**: Confirmed that 8 workers sustains load ~8.00 with ~14 GB available and no swap (prior study observation). With omlx active (~30 GB reserved, ~2 GB remaining for NCN), 8 workers is still feasible because NCN backtests are CPU-bound with modest per-worker memory footprints; however, set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1` and verify no swap pressure before running memory-heavy tasks (e.g. full signal hit-rate study on 400 stocks). If omlx is not running, capacity is ~30 GB total usable. Always check `free -h` before launching.
- **Doris (Maxstudio)**: With ~34 GB available after omlx, workers up to 12-16 are feasible for CPU-bound tasks. For memory-bound tasks (large data loading), cap at 8-10 workers to leave headroom for omlx service stability. Always verify omlx service remains responsive during backtests.
- **Local (MacBook Air)**: With 24 GB available, workers up to 8 are safe for most tasks. For memory-heavy operations (e.g. full signal study on 400 stocks), limit to 4-6 workers. Local scans (single-stock) can use full concurrency.

### Backtest Resource Planning Rules

- Before launching any backtest, check the target environment's current memory pressure (`free -h` on Linux, `memory_pressure` / Activity Monitor on macOS).
- If the target environment is running the omlx service, subtract ~30 GB from available RAM before calculating worker counts and per-worker memory budgets.
- For signal hit-rate studies (400 stocks, 5-day sampling, 2018+ data), prefer Doris (Maxstudio) or local machine. Do NOT run on WSL (P16V) with omlx active unless memory is confirmed sufficient.
- Record the actual environment used, worker count chosen, and observed peak memory usage in `HANDOFF.md` for every backtest run.

## Scheduling

- Scheduled runs require a reviewed `.env.edge_scout_schedule` copied from `config/edge_scout_schedule.env.example`; it must provide `EDGE_SCOUT_CALENDAR`, `EDGE_SCOUT_CALENDAR_SHA256`, and `EDGE_SCOUT_CALENDAR_APPROVAL`.
- The macOS LaunchAgent is `com.vartw.stock-ncn.edge-scout`, installed with `./scripts/install_edge_scout_launchd.sh`; it runs weekdays at 18:30 in the logged-in user session.
