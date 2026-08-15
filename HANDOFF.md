# Reviewer Handoff

## Task: State the practical economic objective without weakening NCN boundaries

### Changed Files
- `AGENTS.md`: states that the user's ultimate objective is profitable decision support and that all strategy work must improve practical candidate quality rather than produce academic research.
- `HANDOFF.md`: recorded the objective clarification.

### Behavior / Logic Changes
- Time, data, and compute are explicitly treated as economic resources; failed directions must stop quickly.
- NCN's direct measurable objective remains selected-stock precision and false-positive reduction because it has no valid execution, cost, portfolio, or account model.
- Profit is an ultimate user objective, not a guaranteed scanner output or authorization for trading functionality.

### Validation
- Static guidance update only; no runtime behavior changed.

### Risks / Review Notes
- Optimizing historical profit without point-in-time execution and cost data would be misleading and likely overfit; do not replace the precision/stability acceptance gates with retrospective return maximization.

## Task: Bound strategy research around practical scanner decisions

### Changed Files
- `AGENTS.md`: added decision-oriented study limits, pre-registered success/failure criteria, compute budgets, and stop rules.
- `HANDOFF.md`: recorded the operating principle.

### Behavior / Logic Changes
- Future strategy work must begin with one actionable hypothesis and end with a clear keep, reject, or implement decision.
- Repeated post-hoc mining of the same historical period is prohibited after a candidate misses its pre-registered threshold.
- NCN remains a read-only research scanner; practical candidate usefulness does not authorize orders, portfolio/P&L, return optimization, or profit promises.

### Validation
- Static guidance update only; no runtime behavior changed.

### Risks / Review Notes
- Selected-stock precision is only a proxy for real-world usefulness and cannot establish profitability without execution/portfolio assumptions that remain outside NCN.

## Task: Add daily leakage-safe walk-forward strategy evaluation

### Changed Files
- `scripts/evaluate_walk_forward_strategy.py`: added daily historical prediction, matured-label strategy selection, prediction-versus-actual records, calibration metrics, and confusion-matrix summaries.
- `scripts/evaluate_joint_strategy.py`: added scalable per-strategy signal-date and fifth-future-bar maturity-date aggregation reused by walk-forward evaluation.
- `tests/test_walk_forward_strategy.py`: added leakage-boundary, future-isolation, abstention, deterministic-selection, calibration, confusion-matrix, and empty-candidate coverage.
- `walk-forward-strategy-2023-2026.json`: recorded the complete daily walk-forward result.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Historical outcomes accumulate from 2021-01-01; daily simulated predictions start on 2023-01-01.
- For prediction date D, strategy choice uses only observations whose fifth future stock bar is strictly before D, within a trailing 730-calendar-day window.
- A strategy needs at least 800 matured observations, 120 active maturity dates, and historical precision above the same-window admitted baseline; otherwise the evaluator abstains.
- Each daily record stores the selected rule, prior probability evidence, candidates, realized hits, false positives, false negatives, and comparison-universe counts.
- No production scanner criteria or YAML strategy parameters changed. This remains classification-only research without orders, positions, returns, execution, or personalized advice.

### Validation
- Full local study: 3,196 current main-board files, 4,157,182 stock-date observations, 6 workers, batch size 32, single-threaded BLAS.
- Walk-forward period: 868 prediction dates; rule selected on 508 dates, actual candidates on 368 dates, zero candidates on 140 selected-rule dates, and strategy-level abstention on 360 dates.
- Aggregate selected-candidate precision: 31.57% (1,123/3,557), below the 32.01% admitted baseline on the same selected-rule dates. Recall was 0.44%; the adaptive selector did not improve overall selected-stock quality.
- `mhpg` achieved 32.08% versus 30.96% contemporaneous baseline on its 54 selected dates (n=770, +1.12 points). `mhpg_regime` achieved 48.71% versus 41.14% on only 16 selected dates (n=349), which is too concentrated for promotion.
- Local full suite: `154 passed, 3 skipped`; `git diff --check` and Python compile checks passed.
- Remote-first attempts remained unavailable: WSL closed SSH after TCP acceptance; Doris only provided unsupported Python 3.9.6.
- Result SHA-256: `2a297e307579f6522343b30e45d214f9612f15489854e359609501c37976feac`.

### Risks / Review Notes
- Candidate strategies were designed after earlier historical inspection, so this is retrospective walk-forward evidence, not a pristine untouched prospective test.
- The adaptive selector is regime-unstable: 2024 precision exceeded baseline, while 2023, 2025, and 2026 did not show consistent improvement.
- Current-file survivorship, historical-membership, forward-adjustment-vintage, overlapping-label, and multiple-testing biases remain.
- Do not promote the adaptive selector, `mhpg`, `mhpg_regime`, or `setup`. Next validation should freeze a small candidate set and evaluate later untouched data or a genuinely prospective paperless observation period.

## Task: Preserve state and align scanner behavior with configuration

### Changed Files
- `src/ashare_edge_scout/signal_scoring.py`: made configured universe gates enforceable and removed misleading unimplemented score-component narration.
- `src/ashare_edge_scout/scanner.py`: made automatic T and post-T observation dates skip suspension rows.
- `src/ashare_edge_scout/candle_timing.py`, `src/ashare_edge_scout/config.py`, `yaml/edge_scout_v1.yaml`: separated stock trend from non-enforcing market-regime research metadata and rejected unsupported configuration.
- `src/ashare_edge_scout/reference_prices.py`, `docs/2026-08-01-edge-scout-usage.md`: clarified research-only display and suspension/near-limit-up filtering boundaries.
- `scripts/evaluate_joint_strategy.py`: aligned the historical admitted baseline with production universe gates.
- `tests/test_edge_scout_config.py`, `tests/test_edge_scout_signal_scoring.py`, `tests/test_edge_scout_scanner.py`, `tests/test_edge_scout_candle_confirm.py`, `tests/test_joint_strategy_gate_parity.py`: added configuration, gate, date, and research/production parity coverage.
- `joint-strategy-2021-2026.json`: regenerated under the corrected gate contract.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Preserved the complete pre-correction working state (excluding Git metadata, market data, virtual environments, runtime output, and published output) at `/Users/artx/Local/Git/Stock/NCN-snapshots/NCN-before-corrections-20260815T105631.tar.gz`; SHA-256 `d74538d7613c81ed074338d806d6baebab134909843f2629ef5d542918ebf800`.
- Scanner hard gates now honor configured prefixes, ST exclusion, listing-bar minimum, price range, ADV20, recent trading-day count, signal-date suspension, and near-main-board-limit-up filtering with structured rejection codes.
- T/T+1/T+2 date handling skips `tradestatus=0` rows. Historical ST status remains point-in-time at T.
- Individual-stock MA slope now belongs to `setup.trend.ma_slope_lookback`; benchmark fields are explicitly non-enforcing `research_market_regime` metadata.
- Removed unsupported `ranking.score_weights` and unused holding/portfolio-style risk-management fields. Config validation rejects `read_only_paper`, legacy `market_regime`, score weights, and enforcing a benchmark regime in V1.
- No signal was promoted, no production tier was enabled, and `production_enabled: false` remains unchanged.

### Validation
- Remote-first attempts: WSL accepted TCP then closed SSH; Doris was reachable but only provided unsupported Python 3.9.6. Local MacBook Air was used as fallback.
- Local full suite: `147 passed, 3 skipped`; `git diff --check` and Python compile checks passed.
- Production/research universe-gate parity tests cover admitted and low-ADV20 cases.
- Local end-to-end scan: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh single-local sh.600004` admitted the stock and published an explainable `near_miss`; `sh.600000` correctly failed existing strict data validation for a missing historical `turn` value.
- Corrected full study: 3,196 current main-board files, 4,157,182 stock-date observations, local 6 workers with single-threaded BLAS. No candidate passed the pre-registered stability gates.
- Regenerated result SHA-256: `89d1b9324c9411972f7d0bb9456ff5b2fbb1547cd14186498bb5887e7457ed49`.

### Risks / Review Notes
- Near-limit-up detection is an explicit 9.5% main-board approximation from adjusted close/preclose; it is a conservative research gate, not exchange matching logic.
- Listing age remains a bar-count approximation. Current-file universe membership, forward-adjusted history, and overlapping five-day labels retain known research biases.
- The benchmark regime remains intentionally non-enforcing because no candidate passed stability validation; adding a hard market-regime gate requires a new versioned study.
- The corrected study changed the holdout admitted baseline to 32.13% through stricter gate parity, but still found no eligible optimum. Do not promote `mhpg` or `setup` from this result.

## Task: Run full-universe joint strategy precision study from 2021

### Changed Files
- `scripts/evaluate_joint_strategy.py`: added a leakage-aware, classification-only joint-rule study over all current main-board files and eligible dates from 2021.
- `tests/test_joint_strategy_study.py`: added coverage for Wilson-bound selection, minimum coverage, and cross-year stability rejection.
- `joint-strategy-2021-2026.json`: recorded the complete study result.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- No scanner selection criteria or production configuration changed; `production_enabled: false` remains unchanged.
- Study split is fixed at 2021-2022 calibration, 2023-2024 validation, and 2025-2026 untouched holdout.
- Strategy eligibility requires minimum validation coverage, positive lift in both validation years, and nonnegative aggregate calibration lift; holdout results never select the winner.
- No candidate passed all eligibility gates. `mhpg` was the closest stable candidate but missed the 2024 gate by 0.23 percentage points; its holdout hit rate was 33.49% versus 32.36% admitted baseline (n=9,927, +1.13 points).
- Current `setup` reached 34.31% on holdout (n=1,603, +1.95 points) but failed the 2023 validation gate, so it was not selected or promoted.

### Validation
- Full study: 3,196 current main-board files, all eligible dates from 2021-01-01, 4,157,182 stock-date observations considered, local MacBook Air, 6 workers, BLAS threads limited to one.
- WSL was attempted first but closed SSH after TCP connection; Doris was attempted second but only had Python 3.9.6 and its uv download did not complete. Local was used as the required fallback.
- Local full suite: `139 passed, 3 skipped`.
- `git diff --check`: passed.
- Result SHA-256: `dda4e53225b4cc86f9947315495962762dc99a5d0eb2a57837bcdc40f69f35fa`.

### Risks / Review Notes
- This is selected-stock classification evidence, not an order, portfolio, P&L, execution, or return backtest.
- Current-file universe membership and forward-adjusted prices retain survivorship, historical-membership, and adjustment-vintage bias; overlapping five-day labels are correlated.
- The research baseline applies configured ADV20 and trading-day gates that the current scanner does not fully enforce; align scanner gates only after a separately reviewed implementation and regression study.
- Next study should freeze `mhpg` and `setup` as candidates, use date-clustered uncertainty or non-overlapping signal dates, and add point-in-time market/sector breadth before considering a versioned scanner change.

## Task: Add OpenCode custom model-routing commands

### Changed Files
- `/Users/artx/.config/opencode/opencode.json`: added custom commands for low-cost Ornith summaries/handoffs and GPT 5.6 Sol strategy/debug/architecture work.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Added `gpt-strategy`, `gpt-debug`, and `gpt-architecture` commands using `gsykj/gpt-5.6-sol`.
- Added `cheap-summary` and `cheap-handoff` commands using `openai/Ornith-1.0-35B-4bit`.
- OpenCode default model remains `openai/Ornith-1.0-35B-4bit`.

### Validation
- `opencode debug config` parsed successfully.
- Verified command names and assigned models from resolved config without printing API keys.

### Risks / Review Notes
- This enables command-level model routing; arbitrary natural-language prompts still use the default model unless a command or model override is chosen.

## Task: Define persistent test environment priority order (and add hardware profile)

### Changed Files
- `AGENTS.md`: added "Test Environment Resource Priority" section and "Test Environment Hardware Profile" section before Scheduling.

### Behavior / Logic Changes
- Establishes permanent priority order for all backtest and test runs (REMOTE-FIRST):
  1. **WSL** - host `10.20.98.161`, port `22`, user `adminwsl`. FIRST choice when the network is reachable and the remote environment is set up. Use when code changes can be synced via `scripts/remote_test_env.sh`.
  2. **Doris (ts.dorisw.kdns.fr)** - host `ts.dorisw.kdns.fr`, port `56731`, user `chinaadmin`. SECOND choice when the above two are unavailable or when backtests specifically require the Doris data layer.
  3. **Local** (本地环境) - LAST resort only. Only use local `.venv` and `PFrontStockData` when both WSL and Doris are unavailable (network unreachable, environment not set up, or dependency conflict).
- Always attempt resources in the order 1→2→3. Do NOT skip WSL or Doris in favor of local unless they are genuinely unreachable. The default behavior is REMOTE-FIRST: try WSL first, then Doris, and only fall back to local when remote options fail.
- Record which environment was actually used for a given test/backtest run in `HANDOFF.md` so reviewers can track consistency across runs.
- This order is permanent unless the user explicitly updates it.

### Test Environment Hardware Profile

Three environments documented with hardware specs, concurrency guidance, and backtest planning rules:

| Field | WSL (P16V) | Doris (Maxstudio) | Local (MacBook Air) |
|-------|-----------|-------------------|-------------------|
| Hardware | ThinkPad P16V (i7) | Maxstudio (M4 Max) | MacBook Air (M4) |
| Total RAM | 32 GB | 64 GB | 24 GB |
| Available for NCN | ~2 GB (omlx reserves ~30 GB) | ~34 GB (omlx reserves ~30 GB) | ~24 GB (dedicated to NCN) |
| CPU (logical cores) | 20 (from prior study) | TBD (benchmark on first use) | TBD (benchmark on first use) |
| Constraints | omlx reserves ~30 GB, leave ~2 GB for NCN. Limit workers to 4 or fewer. Monitor closely. | omlx reserves ~30 GB, leave ~34 GB for NCN. Up to 12-16 workers for CPU-bound, 8-10 for memory-bound. | Dedicated to NCN. Up to 8 workers safe for most tasks; 4-6 for memory-heavy ops (full signal study on 400 stocks). |

### Concurrency Guidelines
- **WSL (P16V)**: With ~2 GB after omlx, limit workers to 4 or fewer. Set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`. Do NOT run full signal hit-rate studies unless omlx is stopped and ~30 GB total usable is confirmed.
- **Doris (Maxstudio)**: With ~34 GB after omlx, 12-16 workers for CPU-bound; 8-10 for memory-bound (large data loading). Always verify omlx remains responsive during backtests.
- **Local (MacBook Air)**: 8 workers for most tasks; 4-6 for memory-heavy operations (full signal study on 400 stocks). Single-stock scans can use full concurrency.

### Backtest Resource Planning Rules
- Before launching any backtest, check the target environment's current memory pressure (`free -h` on Linux, `memory_pressure` / Activity Monitor on macOS).
- If the target environment is running the omlx service, subtract ~30 GB from available RAM before calculating worker counts and per-worker memory budgets.
- For signal hit-rate studies (400 stocks, 5-day sampling, 2018+ data), prefer Doris (Maxstudio) or local machine. Do NOT run on WSL (P16V) with omlx active unless memory is confirmed sufficient.
- Record the actual environment used, worker count chosen, and observed peak memory usage in `HANDOFF.md` for every backtest run.

### Validation
- `AGENTS.md` updated with both "Test Environment Resource Priority" and "Test Environment Hardware Profile" sections.
- Static validation: no runtime tests required; this is a process guideline.

### Risks / Review Notes
- The existing `scripts/remote_test_env.sh` currently only supports the WSL host `10.20.98.161`. If tests ever need to use the Doris host, a new remote target (e.g. `--doris` flag or separate script) will need to be added to support `ts.dorisw.kdns.fr:56731` with user `chinaadmin`.
- Reviewers should check `HANDOFF.md` entries for each test run to verify the priority order and hardware-appropriate worker counts were followed.

## Task: Fetch and assess the completed historical signal study

### Changed Files
- `scripts/remote_test_env.sh`: corrected `study-fetch` to use the SCP-specific port option and explicit SSH identity options.
- `signal-study-2018-2026.json`: fetched the completed 400-code study result from the remote WSL host.
- `HANDOFF.md`: recorded the result assessment and validation.

### Behavior / Logic Changes
- No scanner selection criteria or YAML parameters were changed.
- The result supports pruning weak standalone evidence, but does not yet measure the scanner's actual joint candidate rules.
- In 2025-2026, `mhpg_buy` was the strongest observed standalone feature (35.57% versus 30.53% baseline, n=402); `start_count >= 3` and `dxbd_up` had only small positive deltas.
- Generic candle matching, `hammer`, `mfk4_triggered`, `dingdi_safe_up`, `start_count >= 2`, and the current `setup` did not improve the 2025-2026 holdout hit rate.

### Validation
- `bash -n scripts/remote_test_env.sh`: passed.
- Local JSON SHA-256: `11cfec598e33e109f7558a87645cfdaa7670edf8cb62cf7328908e137410804d`.
- JSON parsed successfully with 147,192 observations across 2018-2026.
- Weighted train (2018-2024) and holdout (2025-2026) feature rates were independently summarized from the fetched JSON.

### Risks / Review Notes
- The study uses 400 deterministically sampled codes and every fifth eligible date; it is not the full main-board universe or every trading day.
- Standalone feature rates are not conditional on universe gates, market regime, liquidity, discovery eligibility, T+1 confirmation, or final rank, so direct score-weight changes would be premature.
- Add joint-rule evaluation, rolling-year stability, confidence intervals, and candidate-precision/coverage reporting before changing production research criteria.

## Task: Add low-cost OpenCode model auto-routing guideline

### Changed Files
- `AGENTS.md`: refined OpenCode model routing so routine work defaults to `openai/Ornith-1.0-35B-4bit` and escalates to `gsykj/gpt-5.6-sol` for high-judgment work.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Compact/summarize, handoff compression, git inspection, simple discovery, formatting checks, and routine documentation now route to low-cost Ornith by default.
- Strategy, win-rate, A-share signal/risk, architecture, complex debugging, test design, and non-obvious correctness work escalate to GPT 5.6 Sol.
- Repeated failures, conflicting evidence, unclear root cause, suspected correctness risk, or internet research changing the approach are explicit escalation triggers.

### Validation
- `AGENTS.md` OpenCode Model Routing section updated with default-low-cost and escalation rules.
- This is a guidance/configuration change only; no runtime tests were run.

### Risks / Review Notes
- This documents routing behavior for OpenCode/agents; it is not proof that OpenCode's built-in `/compact` command can directly specify a separate model.
- For stronger enforcement, set OpenCode's global default model to Ornith and use explicit GPT 5.6 Sol agents/commands for high-judgment tasks.

## Task: Deploy .wslconfig directly and make installer self-contained

### Changed Files
- `scripts/install_p16v_wslconfig.bat`: now writes the P16v `.wslconfig` directly and no longer depends on a sibling `config` directory.
- `HANDOFF.md`: recorded the deployment and installer correction.

### Behavior / Logic Changes
- Directly deployed the configuration to `C:\Users\admin\.wslconfig` through the authenticated WSL mount.
- The installer still backs up an existing file and rejects an incorrectly created `.wslconfig` directory.

### Validation
- Remote file exists at `/mnt/c/Users/admin/.wslconfig`, contains the expected nine lines, and has SHA-256 `3a7cc35fc9acd054ba38721f1636d00812c78a8324067074e7bd7b2a2db3d679`.
- `wsl --shutdown` was not run; the active study continued and had reached 290/400 codes.
- Static validation pending after edit.

### Risks / Review Notes
- The configuration will not take effect until all WSL distributions are stopped with `wsl --shutdown` and Ubuntu is restarted.
- Do not apply it until the current checkpointed study completes or is intentionally paused.

## Task: Detect invalid .wslconfig directory during install

### Changed Files
- `scripts/install_p16v_wslconfig.bat`: now fails with a clear message when `%USERPROFILE%\.wslconfig` is a directory instead of a file.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The installer no longer attempts to back up or overwrite a mistakenly created `.wslconfig` directory.

### Validation
- Static validation and `git diff --check`: pending after edit.

### Risks / Review Notes
- The user must remove or rename the directory manually before installation; the installer does not delete it because it may contain user files.

## Task: Add ThinkPad P16v WSL2 resource configuration

### Changed Files
- `config/windows-p16v.wslconfig`: added a WSL2 template for 20 GB RAM, 20 logical CPUs, 4 GB swap, localhost forwarding, gradual memory reclaim, and sparse VHD support.
- `scripts/install_p16v_wslconfig.bat`: added a Windows installer that backs up an existing `%USERPROFILE%\.wslconfig` before installing the template.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The template keeps standard NAT networking, preserving the existing Windows-to-WSL SSH portproxy design.
- The installer deliberately does not run `wsl --shutdown`, so it cannot unexpectedly terminate the active checkpointed study.

### Validation
- `git diff --check -- config/windows-p16v.wslconfig scripts/install_p16v_wslconfig.bat HANDOFF.md`: passed.
- Static review confirmed standard NAT/localhost forwarding remains compatible with the existing Windows SSH portproxy.
- Runtime validation requires applying the file on Windows after the current study is stopped or complete.

### Risks / Review Notes
- `.wslconfig` is global to all WSL2 distributions owned by the Windows user.
- `sparseVhd` and `autoMemoryReclaim` require a sufficiently recent WSL version; remove the `[experimental]` section if `wsl --version` is old or reports unsupported settings.
- Apply only at a planned checkpoint because `wsl --shutdown` terminates all running WSL distributions and background processes.
- At the time of review, the active study had reached 250/400 codes and 90,955 observations; do not apply the configuration mid-run.

## Task: Correct dedicated remote host hardware profile

### Changed Files
- `HANDOFF.md`: recorded the confirmed laptop model and physical memory.

### Behavior / Logic Changes
- None.

### Validation
- User-confirmed host: ThinkPad P16v, Intel Core i7-13700H, 32 GB physical RAM.
- WSL currently exposes approximately 15 GiB, while the active 8-worker study uses only about 1.3 GiB.

### Risks / Review Notes
- Worker sizing remains CPU/thermal-bound rather than memory-bound.
- Keep the current run at 8 workers; use 12 workers as the next default and benchmark 14 before adopting it.

## Task: Size workers for the dedicated WSL study host

### Changed Files
- `HANDOFF.md`: recorded the dedicated-host worker recommendation.

### Behavior / Logic Changes
- None.

### Validation
- Remote CPU: Intel Core i7-13700H, 20 logical CPUs visible to WSL, 24 MiB L3 cache, one NUMA node.
- Current 8-worker study sustained load average near 8.00 with 8 worker processes and ample memory.

### Risks / Review Notes
- Use 12 workers as the next default for this dedicated host, with BLAS/NumPy threads kept at one per worker.
- Keep the currently running study at 8 workers; benchmark 8/10/12 on an identical subset before considering 14 or more.

## Task: Recommend remote study worker count

### Changed Files
- `HANDOFF.md`: recorded the hardware-based worker recommendation.

### Behavior / Logic Changes
- None.

### Validation
- Remote WSL reports 20 logical CPUs and 15 GiB memory.
- With 8 workers, observed load was approximately 8.00, about 14 GiB memory remained available, and swap use was zero.

### Risks / Review Notes
- Keep the production research study at 8 workers for sustained laptop stability.
- A separate timing benchmark may compare 8, 10, and 12 workers; more than 12 is not recommended without thermal and throughput evidence.

## Task: Check remote signal study progress

### Changed Files
- `HANDOFF.md`: recorded the current detached-study progress snapshot.

### Behavior / Logic Changes
- None.

### Validation
- Study PID `2374` is running detached with PPID 1 after approximately 44 minutes.
- Checkpoint progress: 180/400 codes, 65,691 observations, and 180 per-code shards.
- Remote load average was approximately 8.00; about 14 GiB memory remained available with no swap use.
- Final result JSON is pending; the progress log contains no errors.

### Risks / Review Notes
- At the observed rate, approximately 55 minutes remained, subject to differences in per-code history length.
- Checkpoint state is current through 180 completed codes and can resume after interruption.

## Task: Add internet research and citation guideline

### Changed Files
- `AGENTS.md`: added an Internet Research And Citations guideline for Claude and OpenCode.
- `HANDOFF.md`: added this reviewer summary.
- Claude memory: recorded the user's preference to research blockers online and cite URLs.

### Behavior / Logic Changes
- Agents should search authoritative internet sources when blocked, encountering unfamiliar errors, ambiguous external tool behavior, version-specific issues, or repeated failed attempts.
- Agents should cite URLs used in final answers or handoff notes when internet research influenced the solution.
- If internet access fails or a source is blocked, agents should state that clearly and ask the user for pasted content or another accessible source.

### Validation
- `AGENTS.md` updated with a dedicated guideline section.
- Memory index updated with `feedback_internet_research_citations.md`.

### Risks / Review Notes
- Internet research should prefer official docs/upstream sources; community posts should be supporting evidence unless they contain the exact working procedure being evaluated.

## Task: Deploy and start the remote historical signal study on the current Ubuntu

### Changed Files
- `HANDOFF.md`: recorded current-instance deployment, validation, and study checkpoint state.

### Behavior / Logic Changes
- Synchronized the NCN project and 7,342 Parquet files (approximately 973 MiB) to the current `DESKTOP-N47H7QJ` Ubuntu instance.
- Recreated `/home/adminwsl/NCN/.venv` with Python 3.14 and installed project/test dependencies.
- Started the detached, checkpointed T-day signal hit-rate study with 400 deterministic codes, five-day sampling, data from 2018 onward, and 8 workers.
- No production, order, portfolio, P&L, or execution functionality was enabled.

### Validation
- Remote Linux core suite: `132 passed, 3 skipped`.
- Study PID: `2374`, detached with PPID 1.
- Checkpoint manifest confirmed 10/400 completed codes and 4,097 observations; 16 per-code shards were already present at inspection time.
- Host load was approximately 7.32 with about 14 GiB memory available and no swap use.

### Risks / Review Notes
- This is a new WSL instance; the prior instance's checkpoints were unavailable, so the study restarted from the synchronized local data.
- Keep `/home/adminwsl/NCN/.runtime/signal-study-2018-2026.json.checkpoint` intact. `study-start` resumes from it after interruption or Windows restart.
- The account password appeared in conversation history and should be rotated after remote access is stable.

## Task: Redeploy SSH key login to the current WSL instance

### Changed Files
- `scripts/remote_test_env.sh`: fixed the Expect EOF branch so successful one-time key installation is not reported as a timeout-script error.
- `HANDOFF.md`: recorded deployment and environment identity findings.

### Behavior / Logic Changes
- Reinstalled the current Mac ED25519 public key for `adminwsl@10.20.98.161`.
- No sudo configuration, SSH password setting, or remote package was changed.

### Validation
- `BatchMode=yes` key login: passed.
- Remote permissions: `~/.ssh` is `700`; `authorized_keys` is `600`.
- Installed public-key occurrence count: exactly 1.
- Remote `sshd`: listening; remote user is `adminwsl`.
- `scripts/remote_test_env.sh check`: passed for connectivity but reported `project=not_synced`.

### Risks / Review Notes
- The endpoint now identifies as host `DESKTOP-N47H7QJ`, Linux `6.18.33.2-microsoft-standard-WSL2`, and has no `/home/adminwsl/NCN`; this differs from the prior remote instance (`DESKTOP-T2T24IQ`, Linux 6.6, project present).
- The prior project, data, and study checkpoints are not present in the WSL instance currently reached by Windows portproxy.
- The previously shared account password should be rotated because it appeared in conversation history.

## Task: Make minimal SSH startup recover WSL sshd

### Changed Files
- `scripts/enable_wsl_ssh_portproxy.ps1`: now explicitly wakes Ubuntu and starts/validates WSL OpenSSH before refreshing portproxy.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The startup task no longer assumes an independently configured WSL startup also started `sshd`.
- It invokes Ubuntu as root, validates SSH host keys/configuration, restarts `ssh`, verifies TCP 22, then refreshes the current WSL IPv4 destination.
- It still does not install packages or configure unrelated services/ports.

### Validation
- `git diff --check -- scripts/enable_wsl_ssh_portproxy.bat scripts/enable_wsl_ssh_portproxy.ps1 scripts/disable_wsl_ssh_portproxy.bat scripts/disable_wsl_ssh_portproxy.ps1 HANDOFF.md`: passed.
- Static checks confirmed root WSL invocation, SSH host-key/config validation, `service ssh restart` with direct `sshd` fallback, TCP 22 verification, and AtStartup credentialed task registration.
- Windows runtime validation requires reinstalling the task from the updated BAT/PowerShell pair.

### Risks / Review Notes
- OpenSSH must already be installed inside Ubuntu at `/usr/sbin/sshd`.
- Re-run `enable_wsl_ssh_portproxy.bat` after copying the updated files so the ProgramData task copy receives this change.

## Task: Add rollback for minimal SSH-only WSL portproxy

### Changed Files
- `scripts/disable_wsl_ssh_portproxy.bat`: added a self-elevating rollback entrypoint.
- `scripts/disable_wsl_ssh_portproxy.ps1`: removes only the minimal SSH portproxy task, TCP 22 rule, matching firewall rule, installed script, and task log.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Rollback does not stop WSL, stop WSL SSH, remove unrelated portproxy entries, change `iphlpsvc`, or modify TCP 8018.
- Repeated rollback is supported; absent task and firewall state are reported without failure.

### Validation
- `git diff --check -- scripts/enable_wsl_ssh_portproxy.bat scripts/enable_wsl_ssh_portproxy.ps1 scripts/disable_wsl_ssh_portproxy.bat scripts/disable_wsl_ssh_portproxy.ps1 HANDOFF.md`: passed.
- Static checks confirmed rollback targets only `NCN Refresh WSL SSH PortProxy`, `0.0.0.0:22`, `NCN WSL SSH`, the installed minimal script, and its log.
- Windows runtime validation requires the remote host.

### Risks / Review Notes
- The rollback deletes only `0.0.0.0:22`; manually created portproxy entries for other Windows listen addresses are left unchanged.
- `%ProgramData%\NCN` is removed only when empty, preserving unrelated NCN startup files.

## Task: Add minimal SSH-only WSL portproxy startup setup

### Changed Files
- `scripts/enable_wsl_ssh_portproxy.bat`: added a self-elevating one-click installer.
- `scripts/enable_wsl_ssh_portproxy.ps1`: added SSH-only portproxy, LocalSubnet firewall, delayed WSL IP discovery, and an AtStartup refresh task.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- This minimal path does not install packages, start WSL, manage WSL keepalive, configure TCP 8018, or change the existing WSL startup setup.
- It waits up to 120 seconds for the already-started `Ubuntu` distro, then refreshes `0.0.0.0:22 -> WSL:22`.
- The installer copies the PowerShell script to `%ProgramData%\NCN` and registers `NCN Refresh WSL SSH PortProxy` at Windows startup under the Windows account that owns Ubuntu.

### Validation
- `git diff --check -- scripts/enable_wsl_ssh_portproxy.bat scripts/enable_wsl_ssh_portproxy.ps1 HANDOFF.md`: passed.
- Static checks confirmed only TCP 22, `0.0.0.0` portproxy, `LocalSubnet` firewall scope, AtStartup trigger, bounded WSL IP wait, and credentialed highest-privilege execution.
- Windows runtime validation requires the remote host.

### Risks / Review Notes
- Task Scheduler requests the Windows account password once so the task can enumerate the user-owned WSL distribution before interactive login.
- The script assumes the user's existing startup configuration starts Ubuntu within 120 seconds; otherwise the task log records a timeout.

## Task: Persist Wi-Fi-independent WSL port forwarding

### Changed Files
- `scripts/bootstrap_remote_test_windows.ps1`: changed portproxy listeners to `0.0.0.0` and added TCP 8018 forwarding plus a LocalSubnet firewall rule.
- `scripts/register_wsl_ssh_startup_task.ps1`: starts the registered task immediately after installation.
- `scripts/enable_wsl_ssh_autostart.bat`: updated user-facing output for immediate TCP 22/8018 setup.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- TCP 22 forwards to WSL SSH port 22; TCP 8018 forwards to WSL TCP 8018.
- Listening on `0.0.0.0` makes the forwarding independent of the current Windows Wi-Fi/LAN IPv4 address.
- Firewall access remains restricted to `LocalSubnet` on all Windows network profiles.
- The existing startup task refreshes the WSL destination IP after every Windows restart and now runs once immediately when enabled.

### Validation
- `git diff --check -- scripts/bootstrap_remote_test_windows.ps1 scripts/register_wsl_ssh_startup_task.ps1 scripts/enable_wsl_ssh_autostart.bat HANDOFF.md`: passed.
- Static checks confirmed startup trigger, stored Task Scheduler credential, highest run level, immediate task start, `0.0.0.0` listeners, TCP 22/8018 rules, and `LocalSubnet` firewall scope.
- Windows runtime validation pending on the remote host.

### Risks / Review Notes
- Run `enable_wsl_ssh_autostart.bat` as Administrator and provide the Windows account password when Task Scheduler requests it.
- Port 8018 is forwarded even when no WSL service is listening; it becomes reachable only after a service binds WSL TCP 8018.
- Re-run the enable BAT after copying updated scripts so `%ProgramData%\NCN` and the scheduled task receive this version.

## Task: Adopt dbus-launch WSL keepalive with fallback

### Changed Files
- `scripts/bootstrap_remote_test_windows.ps1`: installs `dbus-x11` so `dbus-launch` is available inside WSL.
- `scripts/start_wsl_then_bootstrap_remote_test_windows.ps1`: tries `dbus-launch true` to keep WSL alive, with fallback to a marked background sleep loop.
- `scripts/check_wsl_ssh_startup_task.ps1`: reports both session dbus and fallback keepalive state.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The runner now follows the documented WSL keepalive approach using `wsl --exec dbus-launch true` semantics where available.
- If `dbus-launch` is not installed yet or does not leave a session daemon, the runner starts the existing `ncn-wsl-keepalive` fallback loop.
- Diagnostics distinguish `dbus-daemon.*session` from `ncn-wsl-keepalive` fallback state.

### Validation
- Static checks passed: `dbus-x11` installation present, `dbus-launch true` present, fallback keepalive present, dbus diagnostic check present, fallback diagnostic check present, no smart quotes.
- `git diff --check -- scripts/bootstrap_remote_test_windows.ps1 scripts/start_wsl_then_bootstrap_remote_test_windows.ps1 scripts/check_wsl_ssh_startup_task.ps1 HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Existing scheduled task definitions must be refreshed by rerunning `enable_wsl_ssh_autostart.bat` so ProgramData receives the updated runner and bootstrap.
- First run may use fallback because `dbus-x11` is installed by bootstrap after the runner attempts dbus; later runs should be able to use dbus.

## Task: Keep WSL alive after startup bootstrap

### Changed Files
- `scripts/start_wsl_then_bootstrap_remote_test_windows.ps1`: starts a WSL keepalive process before running the SSH bootstrap.
- `scripts/check_wsl_ssh_startup_task.ps1`: reports the keepalive PID or stale/missing keepalive state.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The startup runner now mirrors the manual successful state more closely by keeping the Ubuntu WSL distro alive after the task exits.
- Keepalive now uses a simpler `bash -lc` command with a `ncn-wsl-keepalive` marker and a background sleep loop, avoiding the previous `/bin/sh` pidfile quoting failure.
- Diagnostics now use a single-line `bash -lc` command and report `pgrep -af ncn-wsl-keepalive` output or `ncn_wsl_keepalive=missing`.

### Validation
- Static checks passed: `bash -lc` keepalive present, `ncn-wsl-keepalive` marker present, pidfile dependency removed, diagnostic keepalive `pgrep` present, no stdin bash heredoc, no smart quotes.
- `git diff --check -- scripts/start_wsl_then_bootstrap_remote_test_windows.ps1 scripts/check_wsl_ssh_startup_task.ps1 HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Existing scheduled task definitions must be refreshed by rerunning `enable_wsl_ssh_autostart.bat` so ProgramData receives the updated runner.
- The keepalive process is intentionally long-lived; stopping WSL or deleting `/tmp/ncn-wsl-keepalive.pid` resets it.

## Task: Fix startup task log creation and failure capture

### Changed Files
- `scripts/register_wsl_ssh_startup_task.ps1`: changed the scheduled task action to use a PowerShell encoded command that writes runner output and failures to `%ProgramData%\NCN\wsl-ssh-bootstrap.log`.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Registration now appends an install marker to the bootstrap log when scripts are copied into `%ProgramData%\NCN`.
- The scheduled task action now invokes the runner through `-EncodedCommand` and explicitly pipes all output to `Out-File -Append`.
- Task failures are caught and written as `TASK FAILED: ...` plus stack trace in the log.

### Validation
- Static checks passed: encoded command present, install log marker present, runner output redirected with `Out-File`, task failure capture present, old `*>` file redirection removed, no smart quotes.
- `git diff --check -- scripts/register_wsl_ssh_startup_task.ps1 HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Existing scheduled task definitions must be refreshed by rerunning `enable_wsl_ssh_autostart.bat` before `Start-ScheduledTask` will use the new encoded logging action.

## Task: Add administrator-run enable/disable BATs for WSL SSH autostart

### Changed Files
- `scripts/enable_wsl_ssh_autostart.bat`: added a simple administrator-run wrapper for registering the WSL SSH startup task.
- `scripts/disable_wsl_ssh_autostart.bat`: added a simple administrator-run wrapper for removing the WSL SSH startup task.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The new BATs do not auto-elevate; they assume the user explicitly runs them as Administrator.
- Enable calls `register_wsl_ssh_startup_task.ps1`, which installs the start-WSL-then-bootstrap runner and registers the startup task.
- Disable calls `unregister_wsl_ssh_startup_task.ps1`, which removes the startup task.

### Validation
- Static checks passed: CRLF line endings, expected PowerShell targets, Administrator notice, pause, no auto-elevation, no smart quotes.
- `git diff --check -- scripts/enable_wsl_ssh_autostart.bat scripts/disable_wsl_ssh_autostart.bat HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Runtime validation must be performed on Windows from an Administrator command prompt or elevated Explorer launch.

## Task: Automate WSL startup before SSH bootstrap

### Changed Files
- `scripts/start_wsl_then_bootstrap_remote_test_windows.ps1`: added a Windows runner that starts the WSL distro, waits for an IPv4 address, then runs the SSH bootstrap.
- `scripts/register_wsl_ssh_startup_task.ps1`: now installs both runner and bootstrap into `%ProgramData%\NCN` and schedules the runner.
- `scripts/register_wsl_ssh_startup_task.bat`: updated the prompt to describe the start-WSL-then-bootstrap flow.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The scheduled task now mirrors the manual successful recovery flow: start Ubuntu first, wait for WSL networking, then refresh sshd/portproxy/firewall.
- The runner defaults to distro `Ubuntu`, waits up to 60 seconds for a WSL IPv4 address, and then invokes the installed bootstrap script.
- Startup task output remains redirected to `%ProgramData%\NCN\wsl-ssh-bootstrap.log`.

### Validation
- Static checks passed: runner starts WSL, waits for IP, invokes bootstrap, register script copies/runs the runner, BAT prompt updated, no smart quotes.
- `git diff --check -- scripts/start_wsl_then_bootstrap_remote_test_windows.ps1 scripts/register_wsl_ssh_startup_task.ps1 scripts/register_wsl_ssh_startup_task.bat HANDOFF.md`: passed before this handoff insertion.
- Runtime validation requires re-registering the task on Windows and testing a restart.

### Risks / Review Notes
- Existing scheduled tasks must be re-registered so they point at the new ProgramData runner instead of directly at bootstrap.
- If Task Scheduler launches WSL under a non-interactive saved credential differently from manual login, inspect `%ProgramData%\NCN\wsl-ssh-bootstrap.log`.

## Task: Analyze WSL SSH diagnostic log and harden external portproxy

### Changed Files
- `scripts/bootstrap_remote_test_windows.ps1`: creates explicit portproxy entries for localhost and each Windows IPv4 address, and reports SSH banners per address.
- `scripts/check_wsl_ssh_startup_task.ps1`: normalizes stdin line endings for WSL bash diagnostics and tests SSH banners for each Windows IPv4 address.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Diagnostic log showed the scheduled task exists but has not run yet (`LastRunTime` default and no bootstrap log).
- WSL `sshd_config` passed and Windows localhost banner succeeded, but Mac-to-`10.20.98.161:22` still timed out before banner exchange.
- Bootstrap no longer relies only on `0.0.0.0:22`; it deletes the wildcard portproxy and creates per-address `listenaddress=<IPv4>:22 -> WSL_IP:22` mappings.
- Diagnostics now detect whether each Windows IPv4 address, including `10.20.98.161`, returns an SSH banner locally from Windows.
- The replaced log shows per-address portproxy entries exist, but only `127.0.0.1:22` returns an SSH banner; non-loopback Windows addresses connect without returning a banner.

### Validation
- Static checks passed: explicit portproxy address list, wildcard cleanup, per-address banner reporting, CRLF normalization for WSL bash, explicit empty/closed banner reporting, per-address diagnostic banner checks, no smart quotes.
- `git diff --check -- scripts/bootstrap_remote_test_windows.ps1 scripts/check_wsl_ssh_startup_task.ps1 HANDOFF.md`: passed before this handoff insertion.
- Mac-side SSH still needs a Windows rerun of the updated bootstrap and diagnostic scripts for runtime validation.

### Risks / Review Notes
- The prior log indicates Windows startup task registration exists but was not observed running; use `Start-ScheduledTask -TaskName "NCN WSL SSH Bootstrap"` or reboot to validate.
- If per-address Windows-local banner succeeds for `10.20.98.161` but Mac still times out, the remaining issue is likely external firewall/network path rather than WSL or portproxy.

## Task: Add one-click WSL SSH startup diagnostics

### Changed Files
- `scripts/check_wsl_ssh_startup_task.ps1`: added Windows-side diagnostics for the startup task, bootstrap log, WSL state, sshd, portproxy, firewall, listeners, addresses, and SSH banner.
- `scripts/check_wsl_ssh_startup_task.bat`: added a one-click wrapper to run the diagnostic PowerShell script.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The diagnostic script is read-only and does not modify WSL, firewall, portproxy, or scheduled tasks.
- The BAT wrapper writes full diagnostic output to `wsl-ssh-diagnostics.log` in the same directory as the BAT file, then prints the last 20 lines for quick review.
- WSL sshd checks are passed through stdin to `bash -s` to avoid PowerShell quoting issues with shell regex characters.

### Validation
- Static checks passed: task check, log tail, WSL state, sshd state, portproxy, banner checks, stdin-based WSL bash invocation, BAT log redirection to script directory, and no smart quotes.
- `git diff --check -- scripts/check_wsl_ssh_startup_task.ps1 scripts/check_wsl_ssh_startup_task.bat HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Runtime validation must be performed on Windows because the current Mac cannot inspect Windows Task Scheduler or WSL service state locally.

## Task: Diagnose Windows-to-WSL SSH reset after BAT bootstrap

### Changed Files
- `scripts/bootstrap_remote_test_windows.ps1`: added Windows port listener conflict detection and local SSH banner validation.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- The bootstrap now fails if TCP port 22 is already owned by a non-portproxy process on a non-localhost address before creating portproxy.
- Localhost-only listeners such as WSL's `wslrelay` on `127.0.0.1` or `::1` are no longer treated as portproxy conflicts.
- The bootstrap now verifies that `127.0.0.1:<port>` returns an SSH banner after portproxy setup, rather than only checking that the TCP port opens.
- The success output now includes the local SSH banner for easier Windows-side validation.

### Validation
- Static checks passed: banner test present, port listener check present, non-`svchost` conflict check present, no smart quotes.
- `git diff --check -- scripts/bootstrap_remote_test_windows.ps1 HANDOFF.md`: passed before this handoff insertion.
- Mac-side SSH currently reaches `10.20.98.161:22` but times out or resets before SSH key exchange, so Windows-side rerun output is required.

### Risks / Review Notes
- The likely failure mode is a Windows port 22 conflict or portproxy accepting TCP without forwarding to a valid WSL SSH banner.
- Re-run the updated BAT on Windows and confirm it prints `Local SSH banner: SSH-...` before retrying Mac SSH.

## Task: Add one-click BAT wrappers for WSL SSH setup

### Changed Files
- `scripts/bootstrap_remote_test_windows.bat`: added a one-click wrapper for the WSL SSH bootstrap.
- `scripts/register_wsl_ssh_startup_task.bat`: added a one-click wrapper for registering the logon Scheduled Task.
- `scripts/unregister_wsl_ssh_startup_task.bat`: added a one-click wrapper for removing the logon Scheduled Task.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Each BAT wrapper resolves the matching `.ps1` from the same directory.
- Each wrapper requests Administrator elevation when not already elevated.
- Each wrapper preserves the PowerShell script exit code and pauses so Windows users can read success or failure output.

### Validation
- Static checks passed: CRLF line endings, PowerShell invocation present, elevation path present, pause present, no smart quotes.
- `git diff --check -- scripts/*.bat HANDOFF.md`: passed before this handoff insertion.

### Risks / Review Notes
- Runtime validation must be performed on Windows because BAT elevation and Scheduled Task registration cannot be executed from the current Mac.

## Task: Add Windows startup task for pre-login WSL SSH bootstrap

### Changed Files
- `scripts/register_wsl_ssh_startup_task.ps1`: registers the WSL SSH bootstrap as an elevated Windows startup Scheduled Task using a saved Task Scheduler credential.
- `scripts/unregister_wsl_ssh_startup_task.ps1`: removes the Scheduled Task.
- `HANDOFF.md`: updated this reviewer summary.

### Behavior / Logic Changes
- The registered task defaults to `NCN WSL SSH Bootstrap` and runs at Windows startup with highest privileges, whether the user is logged on or not.
- The registration prompts for the Windows password of the account that owns the WSL distro; Task Scheduler stores the credential, and the repo/log files do not store the password.
- The bootstrap script is copied to `%ProgramData%\NCN\bootstrap_remote_test_windows.ps1` so it does not depend on RDP mapped drives before login.
- Bootstrap output is redirected to `%ProgramData%\NCN\wsl-ssh-bootstrap.log`.
- Environment overrides are supported for task name, run user, bootstrap path, install directory, and log directory.
- Registration now uses the Windows PowerShell-compatible `Register-ScheduledTask -User ... -Password ... -RunLevel Highest` parameter set and defaults the credential user prompt to the current Windows user (`$env:USERDOMAIN\$env:USERNAME`).

### Validation
- Static checks passed: AtStartup trigger present, credential prompt present, ProgramData bootstrap copy present, no `-Principal`/`-User` parameter-set conflict, default credential user is auto-detected from the current Windows user, no smart quotes.
- `git diff --check -- scripts/register_wsl_ssh_startup_task.ps1 scripts/register_wsl_ssh_startup_task.bat HANDOFF.md`: passed before this handoff insertion.
- Runtime validation must be performed from elevated Windows PowerShell because the current Mac cannot register Windows Scheduled Tasks.

### Risks / Review Notes
- The Windows account password must be updated in Task Scheduler if that password changes.
- Pre-login startup depends on Windows allowing that account to run scheduled tasks and on WSL being launchable for that user in a non-interactive scheduled task.

## Task: Add resumable detached signal study execution

### Changed Files
- `scripts/evaluate_signal_hit_rates.py`: added per-stock atomic checkpoint shards, manifest checkpoints, resume support, completion-order persistence, and bounded worker/thread settings.
- `scripts/remote_test_env.sh`: added detached `study-start`, `study-status`, `study-stop`, and `study-fetch` commands; study startup resumes from the remote checkpoint directory.
- `HANDOFF.md`: recorded restart-readiness status.

### Behavior / Logic Changes
- The remote signal study runs under `nohup` with PPID 1, so SSH disconnects do not terminate it.
- Each completed stock writes an atomic JSON shard; the manifest is atomically refreshed every 10 completed stocks.
- Restarting Windows/WSL terminates the process, but rerunning `study-start` with the same arguments skips completed shards and continues the remaining stocks.
- The study uses bounded NumPy/BLAS threads and 8 workers for stable resource usage on the WSL host.

### Validation
- Remote checkpoint confirmed: 20/400 stocks completed and 8,257 observations saved.
- Remote process was running as PID `17424` before the restart test.
- `bash -n scripts/remote_test_env.sh`, Python compile, and `git diff --check`: passed.

### Risks / Review Notes
- Windows restart is now safe to test because the first checkpoint is present.
- The result JSON is published only after all pending stocks complete; partial work is retained in `.runtime/signal-study-2018-2026.json.checkpoint`.
- Do not delete the remote `.runtime/signal-study-2018-2026.json.checkpoint` directory between restarts.

## Task: Configure and test the remote Windows/WSL environment

### Changed Files
- `scripts/remote_test_env.sh`: made macOS rsync invocation portable by replacing unsupported `--info=progress2` with `--progress`.
- `HANDOFF.md`: recorded remote setup and test results.

### Behavior / Logic Changes
- Synchronized source/configuration and approximately 993 MiB of `PFrontStockData` to `/home/adminwsl/NCN`.
- Created the remote Python 3.14 virtual environment and installed the editable package plus test dependencies.
- Remote service smoke test confirmed the Web process starts and returns the expected `503 publication_missing` when no published `output/edge_scout/latest.json` exists.

### Validation
- Remote full suite: `134 passed, 3 skipped, 2 failed`.
- Remote core suite excluding platform/runtime-state tests: `132 passed, 3 skipped`.
- `tests/test_edge_scout_scheduler.py` requires macOS `plutil`, unavailable on Ubuntu/WSL.
- `tests/test_edge_scout_web_control.py` requires a published `output/edge_scout/latest.json`; output is intentionally excluded from synchronization and the service correctly returns `publication_missing` without it.

### Risks / Review Notes
- The remote environment is ready for the read-only historical signal study, but the two excluded tests should be validated on macOS or with a fixture publication before claiming a platform-independent full-suite pass.
- No production or execution behavior was enabled.

## Task: Recheck the Windows/WSL remote test environment

### Changed Files
- `HANDOFF.md`: recorded the latest remote connectivity and readiness check.

### Behavior / Logic Changes
- None.
- SSH is reachable at `adminwsl@10.20.98.161:22`; the host is WSL2 with 20 logical CPUs and approximately 15 GiB visible memory.
- The remote project directory, `.venv`, and `PFrontStockData` are not present yet.

### Validation
- `scripts/remote_test_env.sh check`: passed.
- Remote identity: `uid=1000(adminwsl)` with home `/home/adminwsl`.
- `sshd`: listening on `0.0.0.0:22` and `[::]:22`.
- Remote Python: `Python 3.14.4`.

### Risks / Review Notes
- The endpoint is reachable but not ready to run NCN tests until code, data, and dependencies are synchronized.
- No remote files were changed during this check.

## Task: Review and harden the Windows WSL SSH bootstrap

### Changed Files
- `scripts/bootstrap_remote_test_windows.ps1`: hardened the elevated Windows bootstrap for WSL OpenSSH, Mac public-key installation, port forwarding, and firewall setup.
- `HANDOFF.md`: updated this reviewer summary.

### Behavior / Logic Changes
- The bootstrap defaults to WSL distribution `Ubuntu` and Windows TCP port `22`, while auto-detecting the default WSL user unless `NCN_WSL_USER` is set.
- It uses the detected WSL user's real home directory instead of assuming `/home/<user>`.
- It passes the public key and WSL home through base64 placeholders to avoid quoting breakage in the PowerShell-to-bash boundary.
- It installs only SSH/test prerequisites, disables WSL SSH password login, installs the existing Mac public key, and stores no Windows or WSL password.
- It now prints the failing WSL bootstrap command on errors, generates SSH host keys, validates `sshd_config`, and falls back to direct `/usr/sbin/sshd` startup if `service ssh restart` fails.
- It starts `iphlpsvc`, refreshes Windows portproxy to the current WSL IPv4 address, and limits the firewall rule to `LocalSubnet`.

### Validation
- Static text checks passed: no smart quotes, no NUL bytes, balanced quote counts, expected bootstrap safeguards present.
- `git diff --check -- scripts/bootstrap_remote_test_windows.ps1 HANDOFF.md`: passed.
- PowerShell parser/runtime validation is pending because `pwsh` is not installed on the current Mac; final validation must run on the Windows host.

### Risks / Review Notes
- The script must be run once from an elevated PowerShell window through the existing RDP session.
- WSL addresses can change after restart; rerunning this idempotent bootstrap refreshes the Windows portproxy target.
- If Windows cannot reach apt repositories from WSL, the package installation step will fail before exposing SSH.

## Task: Add a secure Windows/WSL remote test environment entrypoint

### Changed Files
- `scripts/remote_test_env.sh`: added SSH key installation, code/data synchronization, remote setup, pytest, and shell commands for the WSL test host.
- `HANDOFF.md`: added this reviewer summary.

### Behavior / Logic Changes
- Defaults target `adminwsl@10.20.98.161:22` and `/home/adminwsl/NCN`; all values can be overridden with environment variables.
- The supplied password is not stored. `install-key` accepts it only through `NCN_REMOTE_TEST_PASSWORD` for one-time public-key installation.
- Runtime output, secrets, local virtual environments, Git metadata, and watchlist state are excluded from code synchronization.

### Validation
- `bash -n scripts/remote_test_env.sh`: passed.
- `scripts/remote_test_env.sh --help`: passed.
- `git diff --check`: passed.
- `scripts/remote_test_env.sh check`: correctly fails closed because `10.20.98.161:22` is unreachable from the current Mac.
- Remote setup later exposed an old macOS rsync incompatibility with `--info=progress2`; the wrapper now uses portable `--progress`.

### Risks / Review Notes
- Windows must expose the WSL SSH service on the configured address and permit TCP port 22 before remote initialization can complete.
- The script deliberately uses the WSL Linux filesystem rather than `/mnt/c` for Parquet-heavy research evaluation.

## Task: Review selection precision against Futu and candlestick references

### Changed Files
- `HANDOFF.md`: added this reviewer summary only.

### Behavior / Logic Changes
- None. Scanner code and `yaml/edge_scout_v1.yaml` were intentionally unchanged.
- Reviewed `futu.md`, Steve Nison's 330-page candlestick reference, current candle rules, setup confirmation, scoring, and Futu-derived start signals.
- Ran a read-only historical signal hit-rate study on a deterministic 200-stock main-board sample. The primary label required a close at least 3% above T within T+1..T+5 and no close more than 3% below T in that window; T+5 close above T was reported as sensitivity.
- Stable validation evidence favored `start_signal_count >= 2`; `dxbd_up`, `gding_up`, and `dingdi_safe_up` were individually positive. `mfk4_triggered` did not validate, and `start_signal_count >= 4` was unstable with low sample counts.
- Bullish patterns alone had limited precision. Pattern plus T+1 confirmation was strong, but T+1 is part of the future-label window and must not be presented as an unbiased T-day win rate.

### Validation
- `pdftotext`/`pdfinfo`: PDF text and metadata inspected successfully.
- Ephemeral scripts outside the repository evaluated 10,003 spaced observations plus an all-eligible-day candle census of 210,211 observations.
- Chronological split: calibration through 2023-12-31; validation from 2024-01-01 through available 2026 data.
- No repository tests were run because no application behavior changed.

### Risks / Review Notes
- Current files are a present-day universe, so results retain survivorship and historical-membership bias.
- Nearby labels overlap and no cluster-adjusted confidence intervals were computed.
- Multiple correlated thresholds were inspected; lifts are not corrected for multiple testing.
- Recommended next implementation is a versioned, reproducible T-only signal evaluation harness before changing production parameters. Keep `production_enabled: false`.
