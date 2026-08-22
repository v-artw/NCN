# Reviewer Handoff

## Task: Continue SMC+News prospective maturity check

### Changed Files
- `HANDOFF.md`: recorded the continuation check and current maturity/data-update state.
- Generated ignored audit output: `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T082251Z.json`.

### Behavior / Logic Changes
- No scanner, SMC selector, news review, replay, or prospective archive behavior changed.
- Continued the newest unfinished handoff direction: check whether SMC+News prospective evidence has matured before making any selector/watchlist decision.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` entries before continuing.
- WSL primary environment check succeeded: `./scripts/remote_test_env.sh check` reached `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- `./main.sh update` was requested but rejected by the user/tool approval, so no data update was run and the same command was not retried.
- Local maturity audit ran: `./main.sh audit-smc-news`; output `smc-news-audit-20260820T082251Z.json` reports canonical snapshots 1, mature_all_smc 0, `evidence_sufficient=false`.
- Audit details remain all pending for archive `smc-news-20260820_152025`: all_smc pending 25, standard_review pending 18, risk_excluded pending 4, ai_unavailable pending 2, insufficient_evidence pending 1, priority_review 0.
- Read-only local data date check found 7,351 Parquet files; latest available research date max is still `2026-08-19`, so data has not advanced beyond the archive signal date.

### Risks / Review Notes
- Current evidence still does not support changing SMC admission, ranking, thresholds, risk exclusions, news-review states, or production behavior.
- Do not rerun `select-review` solely on the same stale signal date to create duplicate prospective archives; wait for data to advance or for the user to approve a data update path.
- Next exact action when continuing: run data freshness/update after user approval or after new BaoStock/local rows are available, then run `./main.sh select-review` to collect a new automatic prospective cohort and `./main.sh audit-smc-news` to recheck maturity.
- Keep replay separate as simulation-only artifact audit; do not use replay or historical backfill as prospective win-rate evidence.

## Task: Assess whether 7-day SMC news window is enough

### Changed Files
- `HANDOFF.md`: recorded the current recommendation for SMC news lookback length.

### Behavior / Logic Changes
- No code or scanner behavior changed.
- User asked whether the current 7-day news window is sufficient.

### Validation
- Used previously verified config/code facts: `yaml/news_ai_review.yaml` has `news.days: 7`; `news_ai_review.py` enforces 7-day retention and writes immutable `news_reviews` artifacts separately from mutable cache.
- No new tests or data fetches were run for this methodological answer.

### Risks / Review Notes
- Current recommendation: keep 7 days for the default SMC short-cycle AI review because SMC target-touch horizon is short and stale news can add noise.
- If longer context becomes necessary, add a separate immutable long-horizon event/risk archive for公告/业绩/减持/诉讼/解禁等, not by simply extending `.runtime/news_cache`.
- Do not use longer historical news windows to backfill win-rate evidence unless point-in-time visibility is frozen.

## Task: Clarify SMC news retention and modification need

### Changed Files
- `HANDOFF.md`: recorded the retention distinction and current recommendation.

### Behavior / Logic Changes
- No code or scanner behavior changed.
- User asked how long SMC news is saved and whether the program needs modification.

### Validation
- Read `yaml/news_ai_review.yaml`: news cache retention is configured as `days: 7`, `refresh_hours: 6`, `per_source_limit: 100`, cache dir `.runtime/news_cache`.
- Read `src/ashare_edge_scout/news_ai_review.py`: cache keeps only recent 7-day items and writes `retention_days: 7`; config loader currently requires `news.days == 7`.
- Existing immutable news review outputs under `output/edge_scout/news_reviews/<run-id>/` preserve `news.json`, `reviews.json`, `summary.json`, and `manifest.json` until manually deleted.

### Risks / Review Notes
- Do not confuse mutable `.runtime/news_cache` retention with immutable review/prospective evidence retention.
- No program change is recommended for evidence collection: daily `select-review` freezes raw `items`, filtered `ai_evidence_items`, and `technical_context` in immutable output.
- Extending mutable cache retention is not useful as proof and could increase noise/disk usage; if longer historical news evidence is needed, prefer a separate immutable archive contract, not changing cache days.

## Task: Clarify daily interactive menu usage for SMC evidence collection

### Changed Files
- `HANDOFF.md`: recorded the recommended daily/weekly usage cadence for menu items.

### Behavior / Logic Changes
- No code or scanner behavior changed.
- User asked when to use menu items for SMC automatic selection, prospective audit, and simulation-only replay.

### Validation
- No tests or commands were run; this was an operational usage clarification.

### Risks / Review Notes
- Daily default after close/new data: run `仅更新研究数据` if needed, then `SMC 选股（自动更新数据）` to collect a new prospective SMC+News archive.
- Run `SMC+新闻前瞻成熟度审计` after data updates, especially once at least 6 trading rows after earlier signal dates should exist; it is safe to run daily but often remains pending early.
- Run `SMC+新闻回放检查（simulation only）` only when inspecting/debugging artifact coverage or after several new runs; it is not required every day and is not win-rate proof.

## Task: Add interactive menu entries for evidence audit/replay

### Changed Files
- `main.sh`: added interactive menu options for `SMC+新闻前瞻成熟度审计` and `SMC+新闻回放检查（simulation only）` so they can be selected with arrow keys and executed with Enter.
- `tests/test_main_script.py`: added expect-based coverage that the new menu entries route to `audit-smc-news` and `replay-smc-news --dry-run` without extra typed command arguments.
- `HANDOFF.md`: recorded the UX change and validation.

### Behavior / Logic Changes
- Running `./main.sh` now exposes the SMC+News evidence audit and simulation-only replay dry-run directly in the interactive menu.
- The replay menu item uses `--dry-run` intentionally, so it prints current simulation-only counts without writing another replay output by default.
- No SMC selector, news review, prospective archive, replay core, scanner thresholds, or data-update behavior changed.

### Validation
- Local menu/routing tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_main_script.py -q --tb=short` (`8 passed`).
- Local replay/menu regression passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_smc_news_replay.py tests/test_smc_news_prospective.py tests/test_news_ai_review.py tests/test_main_script.py -q --tb=short` (`41 passed`).
- Shell syntax passed: `bash -n main.sh`.
- Whitespace passed: `git diff --check -- main.sh tests/test_main_script.py`.

### Risks / Review Notes
- These menu options are convenience UX only; they do not imply any evidence is mature or sufficient.
- `SMC+新闻前瞻成熟度审计` is the formal prospective audit path; `SMC+新闻回放检查（simulation only）` is descriptive replay only and must not be used as win-rate proof.
- Continue using `SMC 选股（自动更新数据）` from the menu to collect new prospective archives after data updates.

## Task: Decide whether SMC+News replay supports main-program changes

### Changed Files
- `HANDOFF.md`: recorded the current evidence-based decision boundary.

### Behavior / Logic Changes
- No scanner, SMC selector, news review, prospective archive, or replay code changed.
- User asked whether the current SMC+News replay/prospective evidence helps improve win rate and whether the main program should be modified.

### Validation
- Used the latest verified replay/prospective state from handoff: replay `output/edge_scout/smc_news_replay/replay-20260820_155422/` has 50 observations, 2 valid current-schema news-review runs, and mature_count 0; SMC+News prospective archive `smc-news-20260820_152025` has 25 observations, all pending.
- No new tests, scans, or backtests were run for this judgment.

### Risks / Review Notes
- Current evidence does not support changing SMC admission, ranking, thresholds, risk exclusions, or production behavior.
- Replay remains simulation-only and not point-in-time/prospective evidence; prospective archive is pending and cannot yet estimate precision lift.
- If continuing, only consider non-selection UX/reporting changes that preserve read-only boundaries, or wait for matured prospective audits before any selector decision.

## Task: Add simulation-only SMC+News replay from existing artifacts

### Changed Files
- `src/ashare_edge_scout/smc_news_replay.py`: added independent simulation-only replay builder, artifact validation, target-touch/path-quality labels, descriptive cohorts, immutable publish, and strict namespace guardrails.
- `scripts/replay_smc_news.py`: added CLI for dry-run and immutable publish of SMC+News replay outputs.
- `scripts/edge_scout_scan.sh`: added manual `replay-smc-news` route that checks local data but does not call `auto_update_data`, news fetch, AI, prospective archive, or prospective audit.
- `main.sh`: added top-level `replay-smc-news` command and help text labeling it as simulation-only and not prospective evidence.
- `tests/test_smc_news_replay.py`: added replay contract tests for manual/non-prospective selections, hash rejection, binding mismatch, news time diagnostics, outcome labels, manifest output, and prospective namespace refusal.
- `tests/test_main_script.py`: added `replay-smc-news` help/delegation coverage.
- `HANDOFF.md`: recorded completed replay implementation and validation.
- Generated ignored simulation output: `output/edge_scout/smc_news_replay/replay-20260820_155422/`.

### Behavior / Logic Changes
- Added a new, isolated `ncn_smc_news_replay_v1` output path under `output/edge_scout/smc_news_replay/`.
- Replay consumes existing immutable `news-review-*` artifacts and their bound `select-*` artifacts by manifest/source hash validation.
- Replay accepts manual/non-prospective selection sources because it is explicitly `simulation_only`; it does not write to or depend on `smc_news_prospective`.
- Replay includes flags `simulation_only=true`, `not_prospective_evidence=true`, `prospective_evidence_claimed=false`, `research_only=true`, `classification_only=true`, and `production_enabled=false`.
- Replay computes descriptive target-touch/path-quality outcome labels using adjusted local research bars: next stock-tradable T open, +3% target, T+1 through T+5 highs, T high excluded, plus -3% risk-first, drawdown, and excursion. It does not compute returns, P&L, fills, fees, orders, broker state, or position sizing.
- No SMC selector masks, thresholds, ranking, diagnostics, `evaluate_stock`, `yaml/edge_scout_v1.yaml`, prospective archive semantics, news fetching, AI calls, or cache mutation changed.

### Validation
- Metadata audit before implementation found `.runtime/news_cache` had 46 files / 284 items and existing `output/edge_scout/news_reviews` had 19 runs / 155 candidate records / 964 raw items / 429 AI evidence items; all inspected item sets had title, URL, source, `published_at`, and `retrieved_at`.
- Local focused replay tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_smc_news_replay.py -q --tb=short` (`6 passed`).
- Local boundary/regression tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_smc_news_replay.py tests/test_smc_news_prospective.py tests/test_news_ai_review.py tests/test_main_script.py -q --tb=short` (`40 passed`).
- WSL primary environment checked reachable: `./scripts/remote_test_env.sh check` succeeded on `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- WSL sync succeeded: `./scripts/remote_test_env.sh sync-code`.
- WSL boundary/regression tests passed: `./scripts/remote_test_env.sh test tests/test_smc_news_replay.py tests/test_smc_news_prospective.py tests/test_news_ai_review.py tests/test_main_script.py -q --tb=short` (`40 passed`).
- Syntax/compile passed: `bash -n main.sh scripts/edge_scout_scan.sh` and `PYTHONPATH=src .venv/bin/python -m py_compile scripts/replay_smc_news.py src/ashare_edge_scout/smc_news_replay.py`.
- Whitespace passed: `git diff --check -- main.sh scripts/edge_scout_scan.sh scripts/replay_smc_news.py src/ashare_edge_scout/smc_news_replay.py tests/test_smc_news_replay.py tests/test_main_script.py`.
- Real artifact dry-run succeeded: `./main.sh replay-smc-news --dry-run --top 5`, `candidate_count=50`, `news_review_run_count=2`, `raw_news_item_count=367`, `ai_evidence_item_count=209`, `mature_count=0`, `would_write=false`.
- Real artifact publish succeeded: `./main.sh replay-smc-news --top 5`, output `output/edge_scout/smc_news_replay/replay-20260820_155422/`; summary verified `simulation_only=true`, `not_prospective_evidence=true`, `prospective_evidence_claimed=false`, `production_enabled=false`, `no_network_fetch=true`, `no_ai_call=true`.
- Published replay included 17 invalid older news-review runs with `selection schema invalid`; only 2 latest runs matched the current `ncn_smc_stock_selector_v4` selection schema and were replayed. All 50 replay observations were pending because local data still ends at 2026-08-19.

### Risks / Review Notes
- Replay output is retrospective simulation and artifact audit only; it is not point-in-time news evidence, not prospective evidence, and not validated precision improvement.
- Do not use replay cohorts to change SMC admission/ranking or to claim news/AI review improves win rate.
- Older news-review artifacts are excluded by strict schema validation; do not loosen this unless explicitly designing a separate legacy-artifact migration/audit.
- Continue using `smc_news_prospective` only for true future evidence; keep replay under `output/edge_scout/smc_news_replay/`.
- Next useful actions: after future data matures, rerun `./main.sh replay-smc-news --dry-run` for descriptive simulation counts and keep separately running `./main.sh audit-smc-news` for real prospective evidence.

## Task: Check next SMC+News prospective maturity step

### Changed Files
- `HANDOFF.md`: recorded the maturity check and data update result.
- Generated ignored audit output: `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T073434Z.json`.

### Behavior / Logic Changes
- No scanner, SMC, news review, or archive/audit source behavior changed.
- Checked whether the first SMC+News prospective archive could mature after the operationalization work.

### Validation
- Latest SMC+News archive state: 1 canonical archive, `output/edge_scout/smc_news_prospective/smc-news-20260820_152025/`, signal date `2026-08-19`, 25 candidates.
- Maturity readiness check found local candidate data latest min/max date both `2026-08-19`; there is not yet even a next stock-tradable entry row after the signal date, so maturity cannot begin.
- `./main.sh update` succeeded and reported BaoStock remote latest trade date `2026-08-19`, local latest trade date `2026-08-19`, coverage ratio `0.9980954972112638`; data was already current and no download was performed.
- `./main.sh audit-smc-news` generated `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T073434Z.json` with canonical snapshots 1, mature_all_smc 0, `evidence_sufficient=false`.

### Risks / Review Notes
- The next useful action is time/data-gated: wait until BaoStock/local data include trading rows after `2026-08-19`; full target-touch maturity requires the next entry row plus five eligible future stock-tradable rows.
- Continue running automatic `./main.sh select-review` after new data arrives to collect more prospective cohorts; run `./main.sh audit-smc-news` after each data update.
- Do not backfill old news-review runs or manual `--as-of` selections into prospective evidence.

## Task: Operationalize SMC + News prospective archive/audit

### Changed Files
- `main.sh`: added direct `select-review` command delegation and help text for the existing SMC selection + news review + archive workflow.
- `src/ashare_edge_scout/smc_news_prospective.py`: hardened downstream archive validation for news review candidate counts, review-state counts, duplicate/empty review codes, and duplicate/empty news record codes.
- `tests/test_main_script.py`: added help/delegation coverage for direct `./main.sh select-review --top 5`.
- `tests/test_smc_news_prospective.py`: added validation coverage for news source hash mismatch, state-count mismatch, duplicate review codes, news artifact tampering, and duplicate same-signal-date archive canonicalization.
- `HANDOFF.md`: recorded completed operationalization and validation state.
- Generated ignored immutable research outputs: `output/edge_scout/selections/select-20260820_151147/`, `output/edge_scout/news_reviews/news-review-20260820_151333/`, `output/edge_scout/smc_news_prospective/smc-news-20260820_152025/`, and `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T072043Z.json`.

### Behavior / Logic Changes
- No SMC admission, masks, thresholds, ranking, diagnostics, `evaluate_stock`, or `yaml/edge_scout_v1.yaml` behavior changed.
- Existing downstream SMC+News prospective path is now reachable via `./main.sh select-review`, which delegates to existing `scripts/edge_scout_scan.sh select-review`.
- Archive validation now rejects inconsistent news-review artifacts before freezing prospective evidence.
- Existing old news-review runs from 2026-08-16 through 2026-08-20 were not prospectively archivable because their source selection summaries lacked `prospective_eligible`; this is correct failure-closed behavior for old/non-contract outputs.
- New local automatic `select-review` generated a prospectively eligible selection, ran news+K-line AI review, and froze the first SMC+News prospective archive.

### Validation
- WSL primary environment checked reachable: `./scripts/remote_test_env.sh check` succeeded on `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_smc_news_prospective.py tests/test_news_ai_review.py tests/test_stock_selector.py tests/test_main_script.py -q --tb=short` (`46 passed`).
- WSL sync succeeded: `./scripts/remote_test_env.sh sync-code`.
- WSL focused tests passed: `./scripts/remote_test_env.sh test tests/test_smc_news_prospective.py tests/test_news_ai_review.py tests/test_stock_selector.py tests/test_main_script.py -q --tb=short` (`46 passed`).
- Syntax/compile passed: `bash -n main.sh scripts/edge_scout_scan.sh` and `PYTHONPATH=src .venv/bin/python -m py_compile scripts/archive_smc_news_prospective.py scripts/audit_smc_news_prospective.py src/ashare_edge_scout/smc_news_prospective.py`.
- Whitespace passed: `git diff --check -- main.sh scripts/edge_scout_scan.sh scripts/archive_smc_news_prospective.py scripts/audit_smc_news_prospective.py src/ashare_edge_scout/smc_news_prospective.py tests/test_smc_news_prospective.py tests/test_main_script.py`.
- Initial operational smoke against old latest review failed closed as expected: `./main.sh archive-smc-news --news-run output/edge_scout/news_reviews/news-review-20260820_092340` raised `ValueError: selection is not prospectively eligible` because the source selection lacked eligibility metadata.
- Operational local smoke succeeded: `EDGE_SCOUT_AUTO_UPDATE=0 ./scripts/edge_scout_scan.sh select-review --top 5` produced selection `select-20260820_151147` for signal date `2026-08-19`, 25 candidates, news review `news-review-20260820_151333`, and archive `smc-news-20260820_152025`.
- Archive summary verified schema `ncn_smc_news_prospective_v1`, `research_only=true`, `classification_only=true`, `production_enabled=false`, source selection/news review hashes, and review states: standard 18, risk_excluded 4, ai_unavailable 2, insufficient_evidence 1, priority_review 0.
- Audit smoke succeeded: `./main.sh audit-smc-news` produced `smc-news-audit-20260820T072043Z.json` with schema `ncn_smc_news_prospective_audit_v1`, `precision_improvement_claimed=false`, canonical snapshots 1, all 25 observations pending, mature_all_smc 0, `evidence_sufficient=false`.

### Risks / Review Notes
- This is prospective evidence plumbing only; it does not prove higher precision and must not be used to change SMC ranking/admission until future audits mature and pass fixed gates.
- News review states remain publication-time human-review cohorts; never backfill historical SMC/news precision from reviews created after the fact.
- The generated 2026-08-20 archive is pending by design because signal date 2026-08-19 has not matured through the T-open + T+1..T+5 contract.
- Continue collecting future automatic `select-review` archives and run `./main.sh audit-smc-news` after data updates; do not use manual `--as-of` outputs for prospective evidence.

## Task: Read-only feasibility audit beyond daily-bar technical SMC mining

### Changed Files
- `HANDOFF.md`: recorded the feasibility audit result.

### Behavior / Logic Changes
- No scanner behavior changed.
- Audited current prospective archive/audit, SMC selection outputs, and news AI review outputs to decide the next credible improvement path.

### Validation
- Read-only file audit of `output/edge_scout` found 1 prospective snapshot: `output/edge_scout/market-20260816_084616/prospective_snapshot.json`, as-of `2026-08-07`, 6 selected rows, 395 baseline rows, eligible true.
- Existing prospective audit `output/edge_scout/prospective_audits/audit-20260816T004911Z.json` has `evidence_sufficient=false`; all 6 selected rows are still pending, with 0 mature observations.
- Recent SMC selection outputs exist for 2026-08-14 (5 candidates), 2026-08-17 (7), 2026-08-18 (23), and 2026-08-19 (25), but these are selection-run archives, not all prospective snapshots under the current market-scan snapshot contract.
- News AI review coverage is operational: latest `output/edge_scout/news_reviews/news-review-20260820_092340/summary.json` reviewed 25 candidates, 24 had news items, 23 AI successes, states were priority 1, standard 18, risk_excluded 4, ai_unavailable 2.
- `news.json` preserves raw `items`, filtered `ai_evidence_items`, and `technical_context` per candidate; however the review summary explicitly says `news_visible_at_review_publication_only; never backfill historical selection precision`.
- Prospective audit code only evaluates market `prospective_snapshot.json` watchlists, not SMC `selections/` or news-review states.

### Risks / Review Notes
- Prospective unchanged evidence is currently the cleanest path but has insufficient mature data; keep collecting automatic snapshots/audits before claiming precision improvement.
- News/AI review is feasible operationally but cannot be backfilled into historical SMC precision because news visibility is at review publication time and LLM output is non-reproducible; use it only prospectively or as UX assistance until enough future outcomes mature.
- Do not change SMC selection from current evidence. The next useful code change, if any, should improve prospective capture/audit for SMC selections and news-review states so future evidence can mature under a fixed contract.
- If continuing, first decide whether to extend the prospective archive to SMC selection/news-review outputs, or simply keep running current automatic workflows until enough snapshots mature.

## Task: WSL fixed SMC quality-score validation

### Changed Files
- `HANDOFF.md`: recorded the completed fixed quality-score validation result.
- `.runtime/evaluate_smc_quality_score.py`: local ignored one-off script used only to copy/run on WSL; no repository source behavior changed.
- Remote one-off script/result under WSL: `/home/adminwsl/NCN/.runtime/evaluate_smc_quality_score_20260820_134233.py` and `/home/adminwsl/NCN/.runtime/smc_quality_score_20260820_134233.json`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Tested one pre-registered fixed additive economic quality score inside current SMC parent; no optimized weights, no threshold tuning, no combination mining.
- Score components: +1 each for EMA stack, EMA slope, close above EMA20, controlled SMC gap, strong close/body, healthy volume, structure break, strong 60-day position, controlled prior 20-day return; -1 each for existing risk warning, long upper shadow, extreme extension.
- Evaluated daily top 20%, top 30%, and top 40% of SMC parent by score, tie-broken by amount and code.
- Used canonical SMC target-touch contract: next stock-tradable T open anchor, +3% target, T+1 through T+5 highs, T high excluded, with -3% risk-first/path-quality metrics.

### Validation
- WSL primary environment used on `10.20.98.161`; check succeeded with 20 CPU, 19Gi memory, project ready.
- Local one-off script syntax passed: `.venv/bin/python -m py_compile .runtime/evaluate_smc_quality_score.py`.
- WSL run completed with 12 workers; output schema `ncn_smc_fixed_quality_score_v1`, 3,196 all-current-main-board codes, code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`, 1,352 valid baseline entry dates.
- Parent SMC matched canonical result: 100,893 mature valid observations, win rate 59.74%, admitted baseline lift +6.18pp, risk-first 46.04%.
- No score group passed; all daily top fractions underperformed same-entry-date SMC parent.
- Daily top 20%: 20,729 observations, win rate 59.32%, SMC parent baseline 59.78%, lift -0.46pp, risk-first 46.27%; selection lift -0.48pp, audit lift -0.44pp; annual lifts mostly negative.
- Daily top 30%: 30,895 observations, win rate 59.45%, parent baseline 59.77%, lift -0.33pp, risk-first 46.26%; selection lift -0.30pp, audit lift -0.34pp.
- Daily top 40%: 40,900 observations, win rate 59.70%, parent baseline 59.76%, lift -0.06pp, risk-first 46.15%; selection lift -0.02pp, audit lift -0.08pp; 2023 and 2024 annual lifts negative.
- Score distribution on SMC mature rows: min -1, p20 3, median 5, p80 6, max 9.

### Risks / Review Notes
- Do not implement this fixed quality score as an SMC ranking/priority rule; it did not improve target-touch precision or risk-first.
- The failed result suggests naive technical-quality composites may select visually stronger but already-efficient/overcrowded SMC names rather than better +3% target-touch candidates.
- At this point, historical in-sample SMC enhancement using existing daily-bar technical labels has low expected value. Stop mining existing 2021-present daily-bar features unless a genuinely new hypothesis/data source is introduced.
- Remaining credible routes: prospective unchanged observation, new revision-safe information source (news/公告/industry/breadth) with fixed future validation, or improving human review UX without claiming higher precision.

## Task: WSL SMC positive-quality priority validation

### Changed Files
- `HANDOFF.md`: recorded the completed positive-quality priority validation result.
- `.runtime/evaluate_smc_quality_priority.py`: local ignored one-off script used only to copy/run on WSL; no repository source behavior changed.
- Remote one-off script/result under WSL: `/home/adminwsl/NCN/.runtime/evaluate_smc_quality_priority_20260820_132122.py` and `/home/adminwsl/NCN/.runtime/smc_quality_priority_20260820_132122.json`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Tested single existing SMC diagnostic labels and single bullish candlestick masks as positive-quality/priority groups inside current SMC parent.
- Did not mine multi-group combinations and did not change SMC thresholds.
- Used canonical SMC target-touch contract: next stock-tradable T open anchor, +3% target, T+1 through T+5 highs, T high excluded, with -3% risk-first/path-quality metrics.
- Pre-registered priority gate required retention >=5%, selection/audit n >=300, entry_dates >=120, codes >=50, selection/audit lift vs same-entry-date SMC parent >=+3pp, Wilson lower 95% above parent, and all annual lifts positive.

### Validation
- WSL primary environment used on `10.20.98.161`; check succeeded with 20 CPU, 19Gi memory, project ready.
- Local one-off script syntax passed: `.venv/bin/python -m py_compile .runtime/evaluate_smc_quality_priority.py`.
- Initial SSH launch timed out locally after printing remote PID, but WSL process continued and completed; result file was verified at `/home/adminwsl/NCN/.runtime/smc_quality_priority_20260820_132122.json`.
- WSL run completed with 12 workers; output schema `ncn_smc_quality_priority_v1`, 3,196 all-current-main-board codes, code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`, 1,352 valid baseline entry dates.
- Parent SMC matched canonical result: 100,893 mature valid observations, win rate 59.74%, admitted baseline lift +6.18pp, risk-first 46.04%.
- No positive-quality group passed the pre-registered gate.
- Best non-tiny full-sample positive group was `diag_high_position_chase`: 40,045 observations / retention 39.69%, win rate 60.82%, same-entry-date SMC parent baseline 59.46%, lift +1.36pp, risk-first 46.84%; selection lift +0.74pp, audit lift +1.80pp, all far below +3pp gate.
- `diag_any_classified`: 45,556 observations / retention 45.15%, win rate 60.35%, baseline 59.47%, lift +0.88pp; 2023 annual lift negative (-0.07pp), gate failed.
- `diag_pullback_reacceleration`: 5,511 observations / retention 5.46%, win rate 56.90%, baseline 59.49%, lift -2.59pp; reject as priority group.
- `diag_base_breakout_start` had 0 mature valid observations in SMC parent because the current diagnostic logic yielded only 4 total base-breakout rows before valid/mature filtering.
- Bullish candlestick groups were too tiny or unstable: `candle_inverted_hammer` had 216 rows and +3.11pp full lift but failed retention/sample/stability gates; `candle_bullish_engulfing` had only 14 rows; most others had <=6 or 0 rows.

### Risks / Review Notes
- Do not promote any tested quality group as an SMC priority filter; none passes the frozen gate.
- `diag_high_position_chase` is directionally interesting and contradicts the naive risk-exclusion idea, but its lift is too small and selection/audit lifts are below gate. At most keep it as a visible diagnostic for human review, not as a validated high-priority selector.
- `diag_pullback_reacceleration` appears harmful under the canonical target-touch contract and should not be used as a priority group.
- Bullish candlestick single-pattern confirmation has insufficient coverage inside SMC and should not be promoted.
- If continuing, avoid more single-label tests on the same history. The next credible route requires genuinely new information, prospective unchanged evidence, or a pre-registered small set of economically motivated composite quality scores with strict holdout/prospective validation.

## Task: WSL single-risk SMC exclusion validation

### Changed Files
- `HANDOFF.md`: recorded the completed single-risk exclusion validation result.
- `.runtime/evaluate_smc_risk_exclusion.py`: local ignored one-off script used only to copy/run on WSL; no repository source behavior changed.
- Remote one-off script/result under WSL: `/home/adminwsl/NCN/.runtime/evaluate_smc_risk_exclusion_20260820_131216.py` and `/home/adminwsl/NCN/.runtime/smc_risk_exclusion_20260820_131216.json`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Tested only single existing risk/diagnostic flags as exclusion candidates inside current SMC parent; did not mine multi-flag combinations or change SMC thresholds.
- Used canonical SMC target-touch contract: next stock-tradable T open anchor, +3% target, T+1 through T+5 highs, T high excluded, with -3% risk-first/path-quality metrics.
- Pre-registered gate required retention >=70%, selection/audit n >=300, entry_dates >=120, codes >=50, selection/audit lift vs same-entry-date SMC parent >=+3pp, Wilson lower 95% above parent, and all annual lifts positive.

### Validation
- WSL primary environment used on `10.20.98.161`; check succeeded with 20 CPU, 19Gi memory, project ready.
- Local one-off script syntax passed: `.venv/bin/python -m py_compile .runtime/evaluate_smc_risk_exclusion.py`.
- WSL run completed with 12 workers; output schema `ncn_smc_single_risk_exclusion_v1`, 3,196 all-current-main-board codes, code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`, 1,352 valid baseline entry dates.
- Parent SMC matched canonical result: 100,893 mature valid observations, win rate 59.74%, admitted baseline 53.56%, lift +6.18pp, risk-first 46.04%.
- No single exclusion passed the pre-registered gate.
- Best full-sample precision lift was excluding `existing_risk_warning`: kept 86,639 / retention 85.87%, kept win rate 60.18% vs SMC parent baseline 59.94%, lift only +0.24pp; selection lift +0.23pp, audit lift +0.24pp, 2021 annual lift was negative.
- Excluding `candle_tweezer_top`: kept 96,302 / retention 95.45%, kept win rate 60.00% vs parent 59.78%, lift +0.22pp; still far below +3pp and Wilson gates failed.
- Excluding `high_position_chase` hurt performance: kept 60,848 / retention 60.31%, kept win rate 59.03% vs parent 59.93%, lift -0.90pp; flagged high-position rows themselves were stronger than parent in full sample (60.82%, lift +1.36pp), so do not treat high-position as a simple exclusion.
- Other single flags had negligible, zero, or negative kept lift: `mkf_bearcluster` ~+0.00pp full and negative audit; `dxbd_clear_cross_78` +0.03pp; `candle_shooting_star` -0.16pp; many rare flags had too few rows.

### Risks / Review Notes
- Do not add any tested single risk exclusion to SMC production; none clears the stability/precision gate.
- Existing risk warnings and tweezer-top are useful display warnings, but not enough to justify automatic exclusion because lift is only about +0.2pp and gates fail.
- Do not exclude `high_position_chase`; contrary to intuition, the flagged rows are stronger than the kept rows under this SMC target-touch contract.
- If continuing win-rate work, the next credible route is not single-risk exclusion. Consider pre-registering a positive-quality ranking/priority test inside SMC, or prospective unchanged evidence, but avoid threshold/combination mining on the same 2021-present history.

## Task: WSL SMC-with-DXBD+GDING annotation validation

### Changed Files
- `HANDOFF.md`: recorded the completed SMC subset validation result.
- `.runtime/evaluate_smc_dxbd_gding_target_touch.py`: local ignored one-off script used only to copy/run on WSL; no repository source behavior changed.
- Remote one-off script/result under WSL: `/home/adminwsl/NCN/.runtime/evaluate_smc_dxbd_gding_target_touch_20260820_130046.py` and `/home/adminwsl/NCN/.runtime/smc_dxbd_gding_target_touch_20260820_130046.json`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Validated same-day `DXBD+GDING` only as an annotation/subset inside existing SMC candidates, not as an admission gate or standalone selector.
- Used canonical SMC target-touch contract: next stock-tradable T open anchor, +3% target, T+1 through T+5 highs, T high excluded, with -3% risk-first/path-quality metrics.
- Correct comparison used `SMC ∩ DXBD+GDING` versus same-entry-date SMC parent candidates, weighted by subset count; admitted-market baseline was also reported only as context.

### Validation
- WSL primary environment used on `10.20.98.161`; check succeeded with 20 CPU, 19Gi memory, project ready.
- Local one-off script syntax passed: `.venv/bin/python -m py_compile .runtime/evaluate_smc_dxbd_gding_target_touch.py`.
- WSL run completed with 12 workers; output schema `ncn_smc_dxbd_gding_t_open_target_touch_v1`, 3,196 all-current-main-board codes, code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`, 1,352 valid baseline entry dates, 1,670,275 mature admitted baseline observations.
- Parent SMC matched known canonical result: 100,893 mature valid observations, 60,277 +3% hits, win rate 59.74%, admitted baseline 53.56%, lift +6.18pp, risk-first -3% rate 46.04%.
- `SMC ∩ DXBD+GDING`: 6,297 mature valid observations, 3,661 hits, win rate 58.14%, same-entry-date SMC parent baseline 59.79%, lift -1.65pp, risk-first 45.58%, median drawdown -4.01%, median excursion +4.03%, median first-touch day 1.
- Selection 2021-2023: 2,742 observations, win rate 57.51%, SMC parent baseline 59.30%, lift -1.79pp, risk-first 49.05%.
- Audit 2024-present: 3,555 observations, win rate 58.62%, SMC parent baseline 60.17%, lift -1.55pp, risk-first 42.90%.
- Annual lifts versus SMC parent were all non-positive: 2021 -1.16pp, 2022 -1.02pp, 2023 -3.20pp, 2024 -0.07pp, 2025 -1.26pp, 2026 -4.61pp.
- Against admitted-market baseline only, the subset still looked positive (+4.95pp full sample), confirming the importance of comparing to SMC parent rather than all admitted stocks.

### Risks / Review Notes
- Do not add `DXBD+GDING` as an SMC filter or ranking boost; it underperforms same-entry-date SMC parent in full sample, selection, audit, and every individual year.
- The lower risk-first rate is not enough to justify promotion because target-touch precision is worse than parent SMC and annual lift is consistently non-positive.
- Do not cite admitted-market lift as evidence for SMC improvement; SMC parent is the correct baseline for this question.
- If continuing, stop this annotation direction or only investigate it as a possible risk/path-quality descriptive tag after a separate pre-registered path-quality gate, not as a precision enhancer.

## Task: WSL 10-trading-day Futu confluence target-touch backtest

### Changed Files
- `HANDOFF.md`: recorded the completed 10-trading-day validation result.
- `.runtime/evaluate_futu_pair_confluence_10d_retry.py`: local ignored one-off script used only to copy/run on WSL; no repository source behavior changed.
- Remote one-off script/result under WSL: `/home/adminwsl/NCN/.runtime/evaluate_futu_pair_confluence_10d_20260820_104921.py` and `/home/adminwsl/NCN/.runtime/futu_pair_confluence_10d_20260820_104921.json`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Reran the same Futu confluence contract as the prior 5-day validation, changing only the observation window to T+1 through T+10.
- Frozen event definitions: MKF all three lines exit green zone (`<=20` prior tradable row and `>20` current row), DXBD prior in `(-60, 0]` then current `>0`, and GDING fast line crossing above signal.
- Contract remained read-only: next stock-tradable T open anchor, +3% target, T high excluded, no execution/fill/fees/slippage/P&L modeling.

### Validation
- WSL primary environment used on `10.20.98.161`; check succeeded with 20 CPU, 19Gi memory, project ready.
- Local one-off script syntax passed: `.venv/bin/python -m py_compile .runtime/evaluate_futu_pair_confluence_10d_retry.py`.
- `./scripts/remote_test_env.sh sync-code` succeeded before the run.
- WSL run completed with 12 workers; output schema `ncn_futu_pair_confluence_t_open_target_touch_v2`, 3,196 all-current-main-board codes, code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`, 1,347 valid baseline entry dates, 1,662,860 mature admitted baseline observations.
- Event counts: DXBD 257,830; GDING 214,860; MKF 3,079. Signal counts: `DXBD+GDING` 87,780; same-day 2-of-3 88,525; `MKF+DXBD` 700; `MKF+GDING` 563; all3 259; window3 185,687; window5 202,707.
- `DXBD+GDING same day`: 31,126 mature valid observations, +3% T+10 hits 20,380, win rate 65.48%, same-entry-date baseline 64.34%, lift +1.14pp, risk-first -3% rate 47.47%, median drawdown -5.01%, median excursion +5.16%, median first-touch day 2.
- `same_day_2of3`: 31,380 observations, win rate 65.48%, baseline 64.33%, lift +1.14pp, risk-first 47.48%, median drawdown -5.01%, median excursion +5.16%.
- `MKF+DXBD`: 262 observations, win rate 62.60%, baseline 63.90%, lift -1.31pp, risk-first 49.24%.
- `MKF+GDING`: 148 observations, win rate 62.84%, baseline 64.04%, lift -1.20pp, risk-first 47.30%.
- `all3`: 78 observations, win rate 57.69%, baseline 63.74%, lift -6.05pp, risk-first 48.72%.
- `window3_2of3`: 64,613 observations, win rate 65.44%, baseline 64.87%, lift +0.58pp, risk-first 47.03%; 2025 lift negative (-0.60pp).
- `window5_2of3`: 70,589 observations, win rate 65.45%, baseline 64.87%, lift +0.58pp, risk-first 47.03%; 2025 lift negative (-0.41pp).

### Risks / Review Notes
- Do not compare the 10-day hit rate directly against prior 5-day hit rates as a strategy improvement; the longer window mechanically raises both signal and baseline target-touch rates.
- Result does not justify standalone promotion. `DXBD+GDING` remains the carrier of the same-day 2-of-3 effect, but lift is only about +1.14pp over an already higher 10-day baseline and risk-first worsens to ~47.5% with median drawdown around -5.0%.
- MKF-inclusive pairs and all-three confluence remain rejected/unsupported: small sample and negative lift.
- 3-day/5-day confluence windows remain diluted and unstable, including negative 2025 lift.
- If continuing, the bounded next action is to test `DXBD+GDING` only as a weak annotation/ranking feature inside the existing SMC candidate set, not as a standalone selector.

## Task: WSL pair breakdown for Futu MKF4/DXBD/GDING confluence

### Changed Files
- `HANDOFF.md`: recorded the pair-breakdown validation result.
- No repository source files were intentionally changed; the pair-breakdown script was written and run remotely under `/home/adminwsl/NCN/.runtime/evaluate_futu_pair_confluence_20260820_101742.py`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Split the prior same-day 2-of-3 Futu confluence into exact pair signals: `MKF+DXBD`, `MKF+GDING`, `DXBD+GDING`, and all three same day.
- Used the same WSL T-open +3% target-touch / -3% risk-first path-quality contract as the prior confluence run.

### Validation
- WSL primary environment used with 12 workers in background.
- Output: `/home/adminwsl/NCN/.runtime/futu_pair_confluence_20260820_101742.json`; schema `ncn_futu_pair_confluence_v1`.
- Event admitted counts matched prior confluence run: `dxbd_replenish_to_control` 92,519; `gding_up_arrow` 76,261; `mkf4_green_exit_cross20` 924.
- `DXBD+GDING same day`: 31,305 mature valid observations, +3% hits 17,383, win rate 55.53%, same-entry-date baseline 54.03%, lift +1.50pp, risk-first -3% rate 43.82%, median drawdown -3.43%, median excursion +3.61%. This accounts for almost all of the prior same-day 2-of-3 signal.
- `MKF+DXBD same day`: 262 mature valid observations, win rate 49.62%, baseline 52.91%, lift -3.29pp, risk-first 44.66%; selection 2021-2023 lift -10.32pp, audit 2024-present lift +2.56pp.
- `MKF+GDING same day`: 148 mature valid observations, win rate 50.00%, baseline 53.38%, lift -3.38pp, risk-first 41.22%; audit 2024-present lift -4.37pp.
- `all3 same day`: 78 mature valid observations, win rate 42.31%, baseline 53.05%, lift -10.74pp, risk-first 39.74%; negative in both selection and audit periods.

### Risks / Review Notes
- The user's broad “three events, any two coincide” idea is mostly carried by `DXBD+GDING`; MKF-inclusive pairs are small-sample and underperform overall.
- Do not promote MKF-inclusive confluence or all-three confluence.
- `DXBD+GDING` has broad sample and consistent positive lift, but the lift is only about +1.5pp and risk-first remains high (~43.8%), so it is not strong enough as a standalone selector. It may be considered only as a weak annotation/ranking feature after additional stability/risk filtering.
- If continuing, the next bounded test should evaluate whether `DXBD+GDING` improves the existing SMC or A-class review set as an annotation, not as a standalone buy/selection rule.

## Task: WSL full-market validation for Futu MKF4/DXBD/GDING confluence

### Changed Files
- `HANDOFF.md`: recorded the WSL validation result for the user's Futu indicator-confluence hypothesis.
- No repository source files were intentionally changed for this validation; the validation script was written and run remotely under `/home/adminwsl/NCN/.runtime/evaluate_futu_confluence_20260820_100856.py`.

### Behavior / Logic Changes
- No scanner behavior changed.
- Tested a read-only Futu confluence hypothesis from the user's chart: MKF4 green-zone exit / all three MKF lines cross above 20, DXBD replenish-to-control transition, and GDING up-arrow proxy.
- Event definitions used in WSL script:
  - `mkf4_green_exit_cross20`: `mkf_momentum`, `mkf_inter`, and `mkf_near` were all `<=20` on the prior tradable row and all `>20` on the signal row.
  - `dxbd_replenish_to_control`: DXBD crosses above `0` into 控盘 from the `(-60, 0]` 回补-to-control transition zone.
  - `gding_up_arrow`: `gding_fast` crosses above `gding_signal`, matching the existing project `gding_bbuy` / up-arrow proxy.
  - `same_day_2of3`: at least two of the three events happen on the same signal date.
  - `window3_2of3` / `window5_2of3`: at least one event occurs today and at least two event types occurred in the current/prior 2 or 4 tradable rows.
- Validation used the read-only T-open target-touch/path-quality contract: next stock-tradable T open anchor, +3% target, observe T+1 through T+5 highs, exclude entry-day high; also report -3% risk-first rate, median drawdown, and median excursion.

### Validation
- WSL primary environment used with 12 workers in background.
- Output: `/home/adminwsl/NCN/.runtime/futu_confluence_20260820_100856.json`; schema `ncn_futu_mkf_dxbd_gding_confluence_v1`; 3,196 all-current-main-board codes; 1,352 valid baseline entry dates.
- Event admitted counts: `dxbd_replenish_to_control` 92,519; `gding_up_arrow` 76,261; `mkf4_green_exit_cross20` 924.
- `same_day_2of3`: 31,559 mature valid observations, +3% hits 17,521, win rate 55.52%, same-entry-date baseline 54.02%, lift +1.50pp, risk-first -3% rate 43.83%, median drawdown -3.43%, median excursion +3.61%.
- `window3_2of3`: 65,062 mature valid observations, win rate 55.13%, baseline 54.44%, lift +0.69pp, risk-first 43.09%, median drawdown -3.33%, median excursion +3.56%.
- `window5_2of3`: 71,120 mature valid observations, win rate 55.06%, baseline 54.39%, lift +0.68pp, risk-first 43.08%, median drawdown -3.33%, median excursion +3.55%.
- Annual stability was weak: for `window3_2of3`, 2025 lift was negative (-0.47pp); for `window5_2of3`, 2025 lift was negative (-0.31pp). `same_day_2of3` annual lifts were positive but small, from about +1.01pp to +2.33pp in later years.

### Risks / Review Notes
- Do not claim this proves higher profitability. It is target-touch/path-quality classification only: no buy fill, sell fill, fees, slippage, exit, returns, P&L, or personalized advice.
- Result does not justify immediate scanner promotion. Same-day confluence is the best of the tested variants but only improves +3% target-touch by about +1.5pp over same-entry-date admitted baseline while risk-first remains high at 43.83%.
- The broader 3-day and 5-day windows dilute the signal and show negative 2025 lift, so they should not be promoted.
- If continuing, the smallest next action is not threshold tuning; first inspect same-day confluence by pair type (`MKF+DXBD`, `MKF+GDING`, `DXBD+GDING`) to see whether one pair is carrying or hurting the result.

## Task: Add independent read-only A-class base-breakout selector

### Changed Files
- `src/ashare_edge_scout/a_class_selector.py`: added independent A-class low-position base-breakout selector and immutable publication schema `ncn_a_class_selector_v1`.
- `scripts/select_a_class_stocks.py`: added CLI for A-class candidate scan and display-only `--top` table.
- `src/ashare_edge_scout/research_a_class_target_touch.py`: added A-class T-open +3% target-touch and -3% risk-first path-quality validation.
- `scripts/evaluate_a_class_target_touch.py`: added multiprocessing JSON validator for A-class historical statistics.
- `main.sh` and `scripts/edge_scout_scan.sh`: added `select-a-class` / `select-a-class-local` without changing existing SMC `select`, `select-local`, `select-review`, or `review-news` behavior.
- `scripts/remote_test_env.sh`: added rsync excludes for `Key/` and `__pycache__/` so WSL sync does not resend key material or bytecode.
- `tests/test_a_class_selector.py`, `tests/test_research_a_class_target_touch.py`, `tests/test_main_script.py`: added focused selector, validation, CLI, and command delegation coverage.
- `HANDOFF.md`: recorded this task state.

### Behavior / Logic Changes
- A-class selection is a separate read-only candidate source under `output/edge_scout/a_class_selections`; it does not write to or read from SMC `output/edge_scout/selections`.
- A-class V1 requires existing hard gates, low/mid-low 20/60/120-day range position, controlled prior 20-day return, prior 20-day box breakout, healthy volume ratio, strong close, and no long upper-shadow risk; it never requires `smc_medium_buy`.
- A-class CLI prints `selector=a_class_base_breakout_v1` and `historical_validation=not_run_in_selection_command`; historical stats are produced only by the separate validator.
- A-class validator uses the same read-only T-open target-touch contract as SMC: next stock-tradable T open anchor, +3% target, observe T+1 through T+5 highs, exclude entry-day high; it also reports whether -3% risk touched first, median drawdown, and median excursion.
- User's image/Futu hypothesis was not implemented in this A-class rule: MKF4 green-zone ending / three lines crossing above 20, DXBD replenish-to-control, and GDING up-arrow two-of-three confluence is a separate unvalidated Futu-indicator-confluence hypothesis that must be defined from `futu.md` and WSL-tested before promotion.

### Validation
- Local focused tests passed: `.venv/bin/python -m pytest tests/test_a_class_selector.py tests/test_research_a_class_target_touch.py tests/test_main_script.py tests/test_research_target_touch.py tests/test_research_barrier_quality.py -q` (`32 passed`).
- Local compile passed: `.venv/bin/python -m py_compile scripts/select_a_class_stocks.py scripts/evaluate_a_class_target_touch.py src/ashare_edge_scout/a_class_selector.py src/ashare_edge_scout/research_a_class_target_touch.py`.
- Local shell syntax passed: `bash -n main.sh scripts/edge_scout_scan.sh scripts/remote_test_env.sh`.
- Local whitespace passed: `git diff --check -- main.sh scripts/edge_scout_scan.sh scripts/remote_test_env.sh scripts/select_a_class_stocks.py scripts/evaluate_a_class_target_touch.py src/ashare_edge_scout/a_class_selector.py src/ashare_edge_scout/research_a_class_target_touch.py tests/test_a_class_selector.py tests/test_research_a_class_target_touch.py tests/test_main_script.py`.
- Local A-class smoke succeeded with automatic local latest signal date `2026-08-19`, 7,351 files evaluated, `candidate_count=0`, output `output/edge_scout/a_class_selections/a-class-select-20260820_094837/`.
- WSL primary validation environment was reachable: `./scripts/remote_test_env.sh check` succeeded on `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- Initial `./scripts/remote_test_env.sh sync-code` was blocked because `Key/*.key` could be synced; after adding `Key/` exclude, WSL sync succeeded and sync output no longer listed `Key/`.
- WSL focused tests passed after sync: `./scripts/remote_test_env.sh test tests/test_a_class_selector.py tests/test_research_a_class_target_touch.py tests/test_main_script.py -q` (`22 passed`).
- WSL A-class automatic-date smoke succeeded with signal date `2026-08-11`, 7,342 files evaluated, `candidate_count=0`, output `/home/adminwsl/NCN/output/edge_scout/a_class_selections/a-class-select-20260820_095303/`.
- WSL 12-process A-class historical validation completed, output `/home/adminwsl/NCN/.runtime/a_class_target_touch_2021_present.json`: schema `ncn_a_class_t_open_target_touch_v1`, workers `12`, mature valid A-class observations `7`; full sample `5/7` +3% hits (`71.43%`), same-entry-date baseline `39.64%`, lift `31.79pp`, risk-first -3% rate `28.57%`, median max drawdown `-2.77%`, median max excursion `7.28%`; selection 2021-2023 `3/3` hits, audit 2024-present `2/4` hits.

### Risks / Review Notes
- Do not promote A-class V1 yet: WSL historical validation has only 7 mature valid observations, far below the project's sample/stability gates despite a high point estimate.
- Current automatic-date A-class scans produced zero candidates locally (`2026-08-19`) and on WSL (`2026-08-11`), confirming the first rule is very strict; do not relax thresholds post-hoc without a new frozen validation plan.
- Existing SMC selector remains unchanged in intent; A-class is additive and separate. Do not merge A-class candidates into SMC review/news flow without explicit validation and user direction.
- The Futu indicator-confluence idea from the image is plausible but separate: define exact MKF4/DXBD/GDING event masks from `futu.md`, then validate as an independent read-only hypothesis before coding it into scanner output.
- Repository working tree has many pre-existing modified/untracked files. If committing, stage only intended A-class files and never include `Key/`, `.runtime/`, `output/`, pycache, or credential-like files.

## Task: Add read-only SMC A/B/high-position diagnostic labels

### Changed Files
- `src/ashare_edge_scout/stock_selector.py`: added annotation-only SMC start diagnostics and schema `ncn_smc_stock_selector_v4`.
- `scripts/select_stocks.py`: displays a `diag` column in the SMC CLI table.
- `tests/test_stock_selector.py`: added focused diagnostic, schema, causality, sorting, and CLI display coverage.
- `HANDOFF.md`: recorded this task state.

### Behavior / Logic Changes
- SMC selection now annotates already-selected candidates as `A` (`base_breakout_start`), `B` (`pullback_reacceleration`), `高位追涨` (`high_position_chase`), or `未分类` (`unclassified_start_diagnostic`).
- Added scalar diagnostic metrics to `candidates.csv` / `candidates.json`: 20/60/120-day range position, prior/current 20-day return, distance to 60-day high, recent pullback from high, and 20-day volume ratio.
- Diagnostics are computed causally from tradable rows through the signal date only and reuse existing `compute_candle_confirmation_features` / `tradable_indicator_values`.
- Diagnostics do not affect admission, `smc_medium_buy`, risk warning count, saved candidate count, or review sort order (`risk_warning_count`, `-amount_cny`, `code`).
- `summary.json` includes `diagnostic_annotation` showing the label is read-only and does not affect selection/ranking.

### Validation
- Local smoke passed: `.venv/bin/python -m pytest tests/test_stock_selector.py -q` (`12 passed`).
- Local compile passed: `.venv/bin/python -m py_compile scripts/select_stocks.py src/ashare_edge_scout/stock_selector.py`.
- Local shell syntax passed: `bash -n scripts/edge_scout_scan.sh main.sh`.
- Local whitespace passed: `git diff --check -- src/ashare_edge_scout/stock_selector.py scripts/select_stocks.py tests/test_stock_selector.py`.
- WSL was used as primary validation environment: `./scripts/remote_test_env.sh check` succeeded on `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- WSL focused tests passed: `./scripts/remote_test_env.sh test tests/test_stock_selector.py -q` (`12 passed`).
- WSL related regression passed: `./scripts/remote_test_env.sh test tests/test_edge_scout_scanner.py tests/test_edge_scout_publisher.py tests/test_edge_scout_scan_cli_output.py tests/test_news_ai_review.py -q` (`42 passed`).
- WSL automatic-date SMC diagnostic scan succeeded with 39 candidates for signal date `2026-08-11`; schema `ncn_smc_stock_selector_v4`, sort order unchanged, diagnostic distribution: `未分类` 21, `高位追涨` 17, `B` 1.
- WSL 12-process diagnostic target-touch backtest completed for 2026-01-01 through 2026-08-11, output `.runtime/diag_backtest_2026.json`: 12,929 mature SMC observations; `高位追涨` 5,546 / 3,633 hits / 65.51%, `B` 694 / 424 hits / 61.10%, `未分类` 6,689 / 4,218 hits / 63.06%; no `A` observations in this 2026 slice.

### Risks / Review Notes
- This is an annotation-only change. Do not treat `A` or `B` as promoted filters until a frozen validation gate passes.
- `高位追涨` is deliberately high-priority in classification, so a stock near the 60-day high can be labeled high-position even if it also resembles a breakout.
- A previous slow single-process WSL diagnostic summary was stopped; the active/appropriate run is the 12-process WSL background run.
- Remote `sync-code` output showed `Key/` files were synced to WSL; review `scripts/remote_test_env.sh sync_code` excludes if this is not intended. Do not delete remote files without explicit approval.

## Task: Create reusable AI assistant rule template

### Changed Files
- `../../AI_Temp/CLAUDE.md`: created a generic Claude Code rule template.
- `../../AI_Temp/AGENTS.md`: created a generic agent/OpenCode-compatible rule template.
- `../../AI_Temp/.opencode/agent/github-pusher.md`: created a restricted optional OpenCode GitHub push agent template.
- `../../AI_Temp/HANDOFF.md`: created and updated template handoff state.
- `HANDOFF.md`: recorded this NCN-side task summary.

### Behavior / Logic Changes
- The template captures the project practices from NCN/US in generic form: startup continuity, Problem Steelman Gate, implementation discipline, research/experiment discipline, evidence quality, validation priority, internet citation rules, safe git behavior, handoff requirements, and model routing guidance.
- The Problem Steelman Gate is scoped to complex, ambiguous, high-risk, or direction-setting tasks and explicitly skipped for simple mechanical work.
- The GitHub pusher agent template stays intentionally mechanical and does not include the steelman gate.

### Validation
- Passed file-level validation for `/Users/artx/Local/Git/AI_Temp/CLAUDE.md`, `AGENTS.md`, `HANDOFF.md`, and `.opencode/agent/github-pusher.md`: all files read successfully and had no trailing whitespace.
- Confirmed final files under `/Users/artx/Local/Git/AI_Temp`.

### Risks / Review Notes
- The template contains bracketed placeholders such as `[PROJECT_NAME]`, `[PROJECT_DOMAIN]`, `[PROJECT_TEST_COMMAND]`, and `[LOW_COST_TOOL_USING_MODEL]`; replace them before copying into a real project.
- During setup, files were initially written to `/Users/artx/Local/AI_Temp` due to path confusion; those temporary copies were removed after copying to the requested `../../AI_Temp` path.

## Task: Add problem-steelman gate to Claude Code and OpenCode rules

### Changed Files
- `CLAUDE.md`: added a complex-task Problem Steelman Gate for Claude Code startup behavior.
- `AGENTS.md`: added the same gate for OpenCode/project-level agents.
- `HANDOFF.md`: recorded this rule maintenance.
- `../US/CLAUDE.md` and `../US/AGENTS.md`: updated from this NCN task as the user requested cross-project rule alignment.

### Behavior / Logic Changes
- Complex, ambiguous, high-risk, or direction-setting work should now first surface unstated assumptions, answer-changing missing information, the common mistake for the question type, and the risk of acting on plausible but unverified answers.
- Agents should then ask one situation-specific clarifying question before giving the recommendation, reasoning, validation target, what not to do yet, and the smallest next action.
- The gate explicitly applies to research strategy, scanner/watchlist logic, validation/backtest methodology, architecture changes, ambiguous bugs, and research-conclusion-impacting changes.
- The gate is explicitly skipped for simple bug fixes, mechanical edits, formatting, git inspection, focused validation, and tasks with already-explicit success criteria.
- The dedicated NCN `.opencode/agent/github-pusher.md` was intentionally not changed because it is a mechanical git-push agent and should not be slowed by research/strategy clarification behavior.

### Validation
- Passed: `git diff --check -- CLAUDE.md AGENTS.md`.
- Passed: `git -C ../US diff --check -- CLAUDE.md AGENTS.md`.
- Passed file-level check that all four rule files contain `Problem Steelman Gate` and have no trailing whitespace.
- Confirmed `../US/AGENTS.md` section numbering was repaired after inserting the new section.

### Risks / Review Notes
- This is rule/documentation maintenance only; no scanner, data, runtime, or tests were changed.
- `CLAUDE.md` is currently untracked in NCN's git status snapshot, so commit preparation must stage it deliberately if this rule should be versioned.

## Task: Document remote server access for shared AI-tool use

### Changed Files
- `remote-server.md`: added a credential-free operational guide for WSL, Doris, and justified local fallback.
- `HANDOFF.md`: recorded the documentation addition.

### Behavior / Logic Changes
- No runtime or scanner behavior changed.
- The new guide defines remote environment priority, verified endpoints, connection/test/sync examples, resource limits, WSL recovery constraints, and safeguards for credentials and destructive operations.
- The guide now requires a project-local virtual environment built from a compatible interpreter when remote system Python is unsupported; all remote tests and backtests must use that environment's `bin/python`.

### Validation
- Documentation was cross-checked against `scripts/remote_test_env.sh`, the WSL bootstrap scripts, `AGENTS.md`, and the current handoff's recent remote status.
- Verified the new Doris setup example uses `python3.14 -m venv .venv-doris` and executes package installation, tests, and backtests through `.venv-doris/bin/python` rather than unsupported system `python3`.

### Risks / Review Notes
- Endpoint availability, remote project paths, and supported virtual environments remain runtime facts and must be rechecked before each use.
- `Doris` system `python3` was recently unsupported (`3.9.6`); use only a verified compatible isolated interpreter such as the previously observed `.venv-doris/bin/python`.

## Task: Add visible progress during SMC selection and AI review

### Changed Files
- `src/ashare_edge_scout/stock_selector.py`: added optional progress callback during full-universe selection, emitted every 500 processed files and at completion.
- `scripts/select_stocks.py`: prints SMC selection start and `已评估 done/total，当前候选 selected` progress lines.
- `src/ashare_edge_scout/news_ai_review.py`: added optional progress callback for each candidate at fetch/K-line, AI-call, and final review-state stages.
- `scripts/review_smc_news.py`: prints visible AI review progress per candidate so the terminal no longer appears black/idle while waiting.
- `tests/test_stock_selector.py`, `tests/test_news_ai_review.py`: added progress callback coverage.
- `HANDOFF.md`: recorded progress-output behavior and validation.

### Behavior / Logic Changes
- Running `./main.sh` and choosing automatic SMC now shows SMC scan progress during the 7,000+ file selection loop.
- AI review now prints lines such as `AI复核进度：1/5 sh.603236 - 获取新闻/公告并构建K线摘要`, `调用AI综合分析`, and final bucket completion.
- Library APIs remain backward-compatible because progress callbacks are optional.

### Validation
- Focused tests passed: `.venv/bin/python -m pytest tests/test_stock_selector.py tests/test_news_ai_review.py tests/test_main_script.py -q` (`31 passed`).
- Compile check passed: `.venv/bin/python -m py_compile scripts/select_stocks.py scripts/review_smc_news.py src/ashare_edge_scout/stock_selector.py src/ashare_edge_scout/news_ai_review.py`.
- Real local review rerun confirmed visible progress output: `./main.sh review-news --selection-run output/edge_scout/selections/select-20260817_092922 --top 2`, output `output/edge_scout/news_reviews/news-review-20260817_102821/`.

### Risks / Review Notes
- Progress lines are informational only and do not alter selection or AI review rules.
- AI review outputs remain non-deterministic model interpretations; review immutable JSON before acting on any research conclusion.

## Task: Make AI news/K-line review terminal output watchlist-friendly

### Changed Files
- `scripts/review_smc_news.py`: replaced the truncated one-line table with grouped Chinese watchlist cards. Each row now shows review bucket, Chinese assessment label, confidence, event risk, and separate `技术 / 新闻 / 风险 / 结论` lines.
- `src/ashare_edge_scout/news_ai_review.py`: tightened the AI prompt so `summary`, `evidence`, and `risk_flags` must use Simplified Chinese.
- `tests/test_news_ai_review.py`: added coverage for the watchlist-card formatter.
- `HANDOFF.md`: recorded the output-format change and validation.

### Behavior / Logic Changes
- Terminal output now groups rows by review bucket: `优先观察`, `谨慎观察`, `风险暂缓`, `证据不足`, and `AI不可用`.
- The display is optimized for manual review: technical candlestick interpretation, news/announcement evidence, risk flags, and final conclusion are printed as readable multi-line Chinese notes.
- JSON/CSV immutable outputs remain unchanged in structure; this is a CLI presentation change plus stricter Chinese prompt wording.

### Validation
- Focused tests passed: `.venv/bin/python -m pytest tests/test_news_ai_review.py -q` (`17 passed`).
- Compile check passed: `.venv/bin/python -m py_compile scripts/review_smc_news.py src/ashare_edge_scout/news_ai_review.py`.
- Whitespace check passed: `git diff --check -- scripts/review_smc_news.py src/ashare_edge_scout/news_ai_review.py tests/test_news_ai_review.py`.
- Real local review rerun succeeded: `./main.sh review-news --selection-run output/edge_scout/selections/select-20260817_092922 --top 5` produced `output/edge_scout/news_reviews/news-review-20260817_101839/` and printed grouped Chinese watchlist cards.

### Risks / Review Notes
- The terminal grouping is still experimental human-review assistance; it does not prove higher target-touch precision or provide buy/sell instructions.
- AI output can vary between runs. In the latest run `sz.001210` moved from prior `risk_excluded` to `standard_review` despite `mkf_bearcluster`; reviewers should treat the printed risk flags and immutable JSON evidence as audit inputs, not final truth.
- If deterministic risk treatment for `mkf_bearcluster` is desired, implement a code-level review-state override separately rather than relying on model judgment.

## Task: Fix SMC auto-review visibility and add K-line candlestick AI context

### Changed Files
- `main.sh`: automatic SMC menu route now calls underlying `select-review` instead of composing `select && review-news` only at menu level.
- `scripts/edge_scout_scan.sh`: added `select-review`, which runs SMC selection then clearly starts `SMC 新闻 AI 二次复核：开始分析最新选股结果...` on success; review calls pass `--data-root` for K-line context.
- `scripts/review_smc_news.py`: added `--data-root` and changed console heading to `新闻 + 日K线 AI 二次复核（参考日本蜡烛图技术，未经胜率验证）`.
- `src/ashare_edge_scout/news_ai_review.py`: AI input now includes filtered news/announcement evidence plus local daily K-line candlestick context through the signal date.
- `tests/test_news_ai_review.py`, `tests/test_main_script.py`: covered K-line context reaching AI and the menu route delegating to `select-review`.
- `README.md`, `HANDOFF.md`: documented the news +日K线 AI review behavior.

### Behavior / Logic Changes
- `SMC 选股（自动更新数据）` now delegates to `edge_scout_scan.sh select-review`, so a fresh menu process should print SMC output and then immediately print the news+K-line AI review output.
- If a terminal menu was already running before this code change, it may still show old behavior; exit with `q` and relaunch `./main.sh` to load the new script.
- AI review no longer depends on news alone. For each candidate it loads local adjusted daily bars from `PFrontStockData` through `signal_date`, sends the last up-to-8 daily OHLCV bars, signal-bar body/shadow/close-location metrics, objective candlestick patterns, and existing risk warnings to the model.
- The prompt now explicitly asks AI to combine news/announcements with Japanese-candlestick-style structure review: entity, shadows, close location, volume confirmation, reversal/continuation patterns, and top-risk patterns.
- If filtered news is empty but K-line context is available, AI still runs and can produce a technical review. If both are unavailable, it remains failure-closed as `insufficient_evidence`.

### Validation
- Focused local suite passed: `.venv/bin/python -m pytest tests/test_news_ai_review.py tests/test_main_script.py -q` (`23 passed`).
- `bash -n main.sh && bash -n scripts/edge_scout_scan.sh` passed.
- Python compile check passed for `scripts/review_smc_news.py` and `src/ashare_edge_scout/news_ai_review.py`.
- `git diff --check -- main.sh scripts/edge_scout_scan.sh scripts/review_smc_news.py src/ashare_edge_scout/news_ai_review.py tests/test_news_ai_review.py tests/test_main_script.py` passed.
- Real local review command succeeded: `./main.sh review-news --selection-run output/edge_scout/selections/select-20260817_092922 --top 5` produced `output/edge_scout/news_reviews/news-review-20260817_100031/`, heading `新闻 + 日K线 AI 二次复核`, `priority_review_count=0`, `risk_excluded_count=2`.

### Risks / Review Notes
- K-line context uses local adjusted daily research bars only through `signal_date`; it is not an execution feed and does not prove fills, returns, or personalized trading advice.
- The AI review is still experimental human-review assistance, not validated precision improvement. Do not tune SMC rules from this five-candidate output.
- Preserve `ai_evidence_items` and `technical_context` in `news.json` when auditing what AI saw.

## Task: Compressed continuation state after SMC/news-AI workflow fixes

### Changed Files
- `HANDOFF.md`: compressed the prior 2,096-line chronological log into a concise continuation handoff.
- Current working-tree context also includes the recent SMC/news-AI changes in `main.sh`, `README.md`, `tests/test_main_script.py`, `src/ashare_edge_scout/news_ai_review.py`, `tests/test_news_ai_review.py`, and `yaml/news_ai_review.yaml`.

### Behavior / Logic Changes
- Interactive `SMC 选股（自动更新数据）` now runs `select` and, only if it succeeds, immediately runs `review-news` on the latest immutable selection output.
- Interactive `SMC 选股（仅本地数据）` remains selection-only to preserve an offline/no-provider path.
- Direct CLI `./main.sh select` remains selection-only for automation; direct `./main.sh review-news` remains the explicit manual/rerun path.
- News AI review now filters model input before calling AI:
  - Google News items are sent to AI only when the title directly mentions the candidate code or candidate/company name.
  - Eastmoney announcement metadata remains eligible because it is fetched by stock code.
  - Weak market-flow /行情快报 titles such as `主力资金`, `净买入`, `净卖出`, `资金流入`, `资金流出`, and related flow summaries are not sent to AI.
  - If filtering leaves no material candidate-specific evidence, the review fails closed as `insufficient_evidence`.
  - `news.json` preserves both raw fetched `items` and filtered `ai_evidence_items`, so reviewers can audit exactly what the model saw.
- `yaml/news_ai_review.yaml` currently uses the verified DeepSeek provider (`deepseek-v4-flash`) with ignored local key file `Key/deepseek.key`; key contents must never be written into output or Git.
- BaoStock freshness checking now avoids no-op pre-18:00 downloads by checking the latest complete daily research bar date. Before 18:00 Shanghai time it checks through yesterday; at/after 18:00 it may check through today.

### Validation
- Latest focused validation after auto-chain change: `.venv/bin/python -m pytest tests/test_main_script.py tests/test_news_ai_review.py -q` passed (`22 passed`).
- `bash -n main.sh` passed.
- `git diff --check -- main.sh tests/test_main_script.py README.md src/ashare_edge_scout/news_ai_review.py tests/test_news_ai_review.py` passed.
- Latest cached live news review after filtering: `output/edge_scout/news_reviews/news-review-20260817_092559/`, `priority_review_count=0`, `risk_excluded_count=1`.
  - Filtered AI inputs: `sh.601728` only earnings-briefing announcement; `sh.600885` only unpledge announcement; `sz.001210` zero material items and `insufficient_evidence`.
  - The generic QFII industry headline and all fund-flow headlines were excluded from AI input.
- Latest observed automatic SMC selection completed without data download: `output/edge_scout/selections/select-20260817_092922/`, timestamped CSV `smc_candidates_20260817_093110.csv`, candidates `sh.603236`, `sh.601728`, `sh.600885`, `sh.601825`, `sz.001210`.
- Remote-first validation context from recent runs: WSL SSH to `10.20.98.161` timed out or closed during banner exchange; Doris at `ts.dorisw.kdns.fr:56731` was reachable but default `python3` is unsupported `3.9.6`, so local supported `.venv` was used for recent focused tests.

### Risks / Review Notes
- AI review output is headline/announcement-metadata interpretation only. It is not a validated precision lift, probability, order, fill, return estimate, or personalized recommendation.
- If the AI provider fails during the chained menu workflow, the SMC selection output should remain published while the AI review fails closed or publishes a partial status.
- Raw cached headlines remain in `items` for audit; use `ai_evidence_items` to inspect what the model actually received.
- `sz.001210` has technical warning `mkf_bearcluster`; that warning is independent of AI and is based on local daily-bar Futu-derived fields (`mkf_momentum`, `mkf_inter`, `mkf_near` all at least 80 on signal date). It is a review annotation, not a sell instruction.
- Do not treat `standard_review`, `priority_review`, `risk_excluded`, or `insufficient_evidence` as proven target-touch probabilities. They only organize read-only human review.

## Stable Product State

### NCN Boundaries
- NCN remains a standalone, read-only A-share research scanner.
- Do not add broker login, orders, leverage, paper trading, portfolio accounting, return/P&L calculation, or live-trading behavior.
- Keep `yaml/edge_scout_v1.yaml` with `production_enabled: false`.
- `PFrontStockData/` contains adjusted research data only; never use it as execution, matching, or return input.
- Runtime imports must stay project-local to `ashare_edge_scout` or declared third-party dependencies; do not depend on `Stock/CN`, `CNstock`, or `a_share_short_swing`.
- `config/research_watchlist.json` is an ignored codes-only research watchlist. Do not add cost, quantity, cash, transactions, P&L, personalized buy/sell instructions, or portfolio semantics.

### Current SMC Phase-1 Contract
- Phase 1 objective is selected-stock precision / false-positive reduction for read-only human review, not profit proof.
- Fixed selector workflow: after T-1 closes, select unchanged `smc_medium_buy` candidates passing existing Main Board, non-ST, listing-age, price, liquidity, trading-status, suspension, and near-limit-up hard gates.
- Later entry reference is the next stock-tradable T open. Target-touch contract is `T_open * 1.03`, observed only on T+1 through T+5.
- Selector output does not fetch T open, place or simulate a buy, place a sell, model fills, track P&L, or calculate returns.
- Ranking is deterministic human-review order: fewer warning annotations first, then higher T-1 amount, then code. Warnings do not remove primary candidates. `--top` limits display only; saved output contains all candidates.
- Historical Phase-1 result: 100,893 mature candidates, 60,277 target touches, 40,616 non-touches, 59.7435% target-touch rate, Wilson 95% 59.4405%-60.0457%, same-entry-date admitted baseline 53.5627%, lift +6.1808 points.
- Stability summary: selection 2021-2023 was 60.0024%; audit 2024-present was 59.5638%; frozen stability gates passed.
- Evidence file retained: `docs/research/results/full-history/t-open-plus3-five-day-win-rate-2021-present.json`; final result SHA-256 `4f25a889c3081c558873048a7086d5e26aa3def7725664c79f30392b2e575355`; code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`.
- Interpretation boundary: 59.74% is a historical daily-high target-touch classification rate, not realized profit. T open is not proof of a buy fill, and daily high is not proof that a queued +3% sell filled. Fees, taxes, slippage, limit-state execution, and T+5 fallback exits are not modeled.
- Do not retune SMC thresholds, target, horizon, warning exclusions, or gates from the inspected result.

### News AI Review Contract
- `./main.sh review-news --top N` reviews the latest immutable SMC selection by default; `--selection-run DIR` selects one explicitly.
- Review output is immutable under ignored `output/edge_scout/news_reviews/<run-id>/` and bound to the source `candidates.json` hash.
- News cache is `.runtime/news_cache/<code>.json`, seven-day retention, six-hour refresh, per-source cap 100. Fresh cache is reused without network; refresh merges/deduplicates and removes older items.
- AI result states are `priority_review`, `standard_review`, `risk_excluded`, `insufficient_evidence`, and `ai_unavailable`.
- Favorable AI cannot bypass SMC and cannot become a buy recommendation. API/news/model failures fail closed and never produce priority.
- `priority_review` is an experimental human-review order only. Prospective promotion gates remain: unchanged future SMC candidates, at least 300 mature reviewed observations, at least 120 publication dates, at least 50 codes, at least 20% parent-candidate retention, at least +3 percentage points target-touch precision versus same-date parent SMC, priority Wilson lower 95% above parent precision, and positive annual lifts.
- If these gates miss, reject the priority filter without prompt/threshold mining.

### Prospective Watchlist Archive
- Every successful market publication can freeze `prospective_snapshot.json` with selected rows, scored baseline rows, source/config hashes, visible-data-through date, and publication timestamp.
- Only automatic-date scans are prospectively eligible. Manual `--as-of` snapshots are permanently excluded from prospective evidence.
- For repeated signal dates, only the earliest valid publication is canonical; later runs cannot replace it.
- Existing primary cohort is `all_watch`; descriptive subcohorts include `confirmed_watch`, `setup_watch`, `cnstock_pool_watch`, and `discovery_watch`. Same-date baseline is every scored stock frozen in that scan.
- Fixed prospective label: from archived T close, among the next five tradable closes at least one reaches +3% and none closes below -3%. Fewer than five is `pending`; archived/current T-close mismatch is `data_revision` and excluded.
- First valid snapshot: `output/edge_scout/market-20260816_084616/prospective_snapshot.json` with 395 frozen scored-baseline rows and 6 selected rows.
- First valid audit: `output/edge_scout/prospective_audits/audit-20260816T004911Z.json`, all 6 selected observations pending, `evidence_sufficient=false`.
- Recurring action: after normal automatic market scans, preserve immutable run directories; run `./main.sh audit` after data updates. Do not use `--as-of` when collecting prospective evidence.

### Web / Data Runtime
- Web server remains stdlib serial `HTTPServer`; avoid reintroducing threaded PyArrow reads because Python 3.14 concurrent reads caused native crashes.
- `/api/health` exists and should be used by the managed Web control script instead of `/api/dashboard`, so liveness does not require a publication.
- Sina/Eastmoney intraday data have no exchange latency SLA; preserve provider/source timestamps, freshness, forming-bar state, warnings, bounded retry/cache behavior, and explicit last-observation fallback.
- Manage Web only through `./scripts/edge_scout_web_control.sh start|stop|restart|status` or `main.sh`; it owns `.runtime/edge_scout_web.pid`, logs, PID validation, and HTTP health checks.

## Strategy Research Decisions Not To Repeat

### Rejected or Stopped Directions
- Do not port Astock formula weights, reported Sharpe, hard-coded 65% values, `WinRate_V2`, stockAI model probabilities, CNstock market-state labels, branch thresholds, AI/news scores, portfolio rules, or execution logic into NCN.
- Local reference projects (`AlphaGPT`, `Astock`, `stock`, `stock1`, `stockAI`, `CNstock`, `CNstock-branches`) did not provide credible directly transferable evidence for improving NCN selected-stock precision.
- Main issues in those projects: same-date cross-section used as time series, YAML profile renames bypassing intended filters, OHLCV formula mining, hard-coded/uncalibrated win-rate labels, and stock-block `TimeSeriesSplit` rather than global-date/purged validation.
- RSRS/MHPG, strict MkF green-zone exit, Shengbei+KDJ, Futu indicator ranking/combination, Nison candlestick variations, bullish engulfing confirmation, rising-three-methods, share-repurchase count, Dragon-Tiger institutional net buying, and CNInfo earnings forecast/express PDF coverage were all studied or probed and did not meet frozen gates or coverage requirements. Do not re-mine these same historical windows for threshold variants.
- Walk-forward adaptive strategy evaluation (2023-2026) selected rules on 508 of 868 dates but produced 31.57% selected-candidate precision versus 32.01% admitted baseline; do not promote adaptive selector, `mhpg`, `mhpg_regime`, or `setup` from that result.
- Full-universe joint strategy study from 2021 found no candidate passing eligibility gates. `mhpg` and current `setup` had some holdout lift but failed validation/stability gates, so neither was promoted.
- Corrected gate-parity study still found no eligible optimum. Do not promote benchmark regime gates, `mhpg`, or `setup` without a new versioned study using fixed candidates and untouched/prospective data.

### Research Requirements Going Forward
- Before each new strategy study, state one actionable hypothesis, fixed candidate set, success/failure thresholds, maximum compute/data budget, and the implementation decision for pass/fail.
- Stop failed directions when pre-registered precision/stability thresholds miss. Do not expand candidate combinations merely to produce a positive result.
- Require genuinely new revision-safe point-in-time information or unchanged prospective evidence for further win-rate work.
- A 70% target precision claim requires pre-registered minimum sample, annual coverage, out-of-sample stability, and confidence-bound gates; never lower gates just to end the search.

## Test Environment And Resource Priority

### Required Order
1. WSL: host `10.20.98.161`, port `22`, user `adminwsl`. First choice when reachable and set up. Use `scripts/remote_test_env.sh` when applicable.
2. Doris: host `ts.dorisw.kdns.fr`, port `56731`, user `chinaadmin`. Second choice, especially for Doris data layer/backtests.
3. Local MacBook Air: last resort only, after WSL and Doris are unavailable or unsuitable.

### Current Practical Status
- Recent WSL attempts timed out or closed during SSH banner exchange.
- Recent Doris direct checks reached SSH but default `python3` was `3.9.6`, below supported `>=3.12,<3.15`; use a managed/isolated supported Python there only when available.
- Recent focused tests therefore used local `.venv` as justified fallback.

### Hardware Guidance
- WSL/P16V: 32 GB total but omlx may reserve ~30 GB, leaving ~2 GB for NCN. Keep worker count low, set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and check memory before heavy work.
- Doris/Maxstudio: 64 GB total, about 34 GB available after omlx; 12-16 workers can be feasible for CPU-bound tasks, 8-10 for memory-bound.
- Local MacBook Air: 24 GB dedicated; up to 8 workers safe for most local tasks, 4-6 for memory-heavy studies.
- Record environment, worker count, and observed memory/pressure in handoff for every backtest or substantive validation.

## Commands To Remember
- Environment setup: `./scripts/setup.sh` creates `.venv` and installs supported Python package/test dependencies.
- Default suite: `.venv/bin/python -m pytest -q`.
- Focused tests: `.venv/bin/python -m pytest tests/test_news_ai_review.py -q` or specific files/nodes.
- Interactive menu: `./main.sh`.
- Automatic SMC + chained AI review: choose `SMC 选股（自动更新数据）` from menu.
- CLI selection-only automation: `./main.sh select` or `./main.sh select-local`.
- Manual AI review/rerun: `./main.sh review-news [--selection-run DIR] [--top N]`.
- Web management: `./scripts/edge_scout_web_control.sh start|stop|restart|status`.
- Prospective maturity audit: `./main.sh audit`.
- After Web changes, run focused Python tests, `node --check src/ashare_edge_scout/web_static/app.js`, and `git diff --check`.

## Current Next Actions
- If user runs the menu again, verify `SMC 选股（自动更新数据）` prints SMC output and then immediately prints news AI review output without asking for an extra confirmation.
- If reviewing AI output, inspect `output/edge_scout/news_reviews/<run-id>/news.json` and prefer `ai_evidence_items` over raw `items` for what influenced the model.
- If preparing to commit, inspect the full working tree carefully because this repository currently has many modified/untracked files from prior sessions; stage only intended files and never include `Key/`, `.runtime/`, `output/`, or credential-like files.
- If continuing strategy work, do not tune on the historical SMC result or the latest five-candidate AI review. Use prospective/unchanged evidence gates.
