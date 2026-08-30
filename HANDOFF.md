# Reviewer Handoff

## Current Task: Save main checkpoint before AI4Finance production-integration branch (2026-08-30)

### Changed Files
- `HANDOFF.md`: added this checkpoint note before committing current working state to `main`.
- All currently tracked and untracked project changes in the working tree are intended to be committed as a main checkpoint before creating the AI4Finance integration branch.

### Behavior / Logic Changes
- User asked to create a branch based on the AI4Finance production-integration discussion, but first save the current state to the `main` branch.
- This checkpoint is only a git state-management step; it does not add live broker login, live order submission, leverage, unattended real-money execution, or new trading advice behavior.
- The planned branch should discuss/design phased production integration of AI4Finance ideas into NCN as evidence, review, evaluation, risk, and audit architecture—not direct BUY/HOLD/AVOID prompt escalation or live execution.

### Validation
- Inspected current git branch and working tree before committing: current branch is `main` with tracked modifications and untracked MKF research artifacts/`mkf.sh`.
- `git diff --check -- HANDOFF.md yaml/mkf_ai_review.yaml` had no whitespace errors before this checkpoint note; rerun broader checks after the commit/branch if needed.

### Risks / Review Notes
- Commit all current working tree content to `main` as the requested checkpoint, then create/switch to a new AI4Finance production-integration branch from that commit.
- Do not treat branch creation as authorization for real-money trading or live broker integration; current governance still allows production-adjacent/paper/demo/human-review work only.

## Current Task: Preliminary MKF AI prompt effectiveness evaluation (2026-08-30)

### Changed Files
- `.runtime/mkf-prompt-eval-20260830/old-default-config.yaml`: temporary evaluation config omitting `prompt.system` so the code default prompt is used.
- `.runtime/mkf-prompt-eval-20260830/current-production-readable-config.yaml`: temporary copy of current MKF AI YAML for evaluation.
- `.runtime/mkf-prompt-eval-20260830/evaluate_prompt_change.py`: temporary static/read-only evaluator; it does not call AI and does not modify production files.
- `.runtime/mkf-prompt-eval-20260830/compare_ab_top8.py` and `compare_ab_full23_v2.py`: temporary comparators for old/current review rows.
- `.runtime/mkf-prompt-eval-20260830/prompt_eval_preliminary.*`, `ab_top8_*`, and `ab_full23_*`: evaluation outputs and final markdown reports.
- `.runtime/mkf-prompt-eval-20260830/ab-runs/current-production-readable-full23-20260830-180746-205545/`: completed current-prompt full23 replay output.
- `HANDOFF.md`: updated this evaluation handoff entry.

### Behavior / Logic Changes
- No prompt, runtime code, selector logic, YAML business config, watchlist, provider config, broker, order path, leverage, or live execution behavior changed during this evaluation step.
- User requested a comprehensive evaluation of whether the changed MKF AI committee prompt is more effective, using prior scan data, internet information, and judgment, while explicitly saying not to change the prompt.
- User also allowed internet information and analyst judgment as evaluation references, including a stricter short-swing analyst style prompt that asks for real data/sentiment, no fabricated numbers, score 1-10, BUY/HOLD/AVOID, core reasons, and BUY only for the highest-quality candidates. Treat that as an evaluation benchmark only; do not copy BUY/HOLD/AVOID into the production MKF prompt because current NCN boundaries forbid operation labels.
- Evaluation scope was fixed to old code default prompt vs current production-readable `yaml/mkf_ai_review.yaml` prompt.
- Internet research was used only for evaluation methodology: official Anthropic guidance says to define success criteria/evals before prompt refinement and to make prompts clear/direct with structured instructions. It was not fed back into the production prompt.
- Static prompt comparison: old default prompt has 902 chars, 1 line, 0 section headings, hard-codes day 1/2 lag, and lacks YAML lag wording; current prompt has 1066 chars, 28 lines, 9 section headings, retains `MKF AI委员会`, removes day 1/2 hard-coding, and uses YAML lag wording.
- Existing old-prompt review baseline: `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260830_180924`, source selection `mkf-select-20260830_180746`, status partial, candidate_count 23, ai_success_count 22, state_counts standard_research=18/risk_attention=4/ai_unavailable=1.
- Completed current-prompt full23 replay in background task `bytjd2eu8`: output directory `.runtime/mkf-prompt-eval-20260830/ab-runs/current-production-readable-full23-20260830-180746-205545/`, status success, rows=23, AI effective=23, state_counts standard_research=17/risk_attention=6.
- Full23 comparison found persisted row schema stable: 0 missing persisted required fields and 0 forbidden response-key violations for both old and current. Note: raw model `committee` is intentionally persisted as `committee_summary` and `committee_roles` in reviews rows.
- Current prompt scored all 23 candidates; old baseline had `sh.605020` as `ai_unavailable`, while current classified it as `standard_research` with confidence 0.75.
- Current prompt moved `sh.605305` and `sh.603668` from `standard_research` to `risk_attention`, reflecting stricter treatment of technical/fundamental or funds-flow conflicts.
- TopN overlap: Top5 overlap 3/5, Top8 overlap 6/8, Top10 overlap 8/10, Top15 overlap 13/15. Ranking changed mainly because current run filled `sh.605020` and downgraded riskier `sh.603668`/`sh.605305`.
- Blunt operation-term scan: old 5 rows, current 6 rows. Current is slightly worse on this crude metric, mostly because outputs quote/describe evidence phrases such as main-fund net buy/sell or MKF buy signal; this is not automatically confirmed trading advice but remains a production-reading risk.
- Historical return-term scan: 7 rows in old and current, mainly historical return descriptions, not return promises.
- Latest 2026-08-28 signal set is not mature for T+20 target-timeout outcome as of 2026-08-30; do not use it to claim hit-rate improvement.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, current `yaml/mkf_ai_review.yaml`, provider config, review CLI, and MKF review flow excerpts.
- Ran local static evaluator: `PYTHONPATH=src .venv/bin/python .runtime/mkf-prompt-eval-20260830/evaluate_prompt_change.py`.
- A/B replay initial attempts required fixing temporary config path/key-file handling; final replay used command-scoped `EDGE_SCOUT_LOCAL_AI_API_KEY="$(tr -d '\r\n' < Key/ts.key)"` and did not change production provider config.
- Current prompt full23 replay command completed successfully with local `.venv` and `PFrontStockData` because this was provider replay/tooling validation rather than a data-heavy backtest; remote WSL/Doris target-timeout validation remains pending.
- Ran full23 comparator: `PYTHONPATH=src .venv/bin/python .runtime/mkf-prompt-eval-20260830/compare_ab_full23_v2.py`; wrote `ab_full23_comparison_v2.json` and `ab_full23_final_report_v2.md`.
- Prior focused MKF AI tests from the prompt replacement step passed: `.venv/bin/python -m pytest tests/test_mkf_ai_review.py -q` -> `21 passed in 0.40s`.

### Risks / Review Notes
- Current evidence supports production-readability, output-contract stability, and more conservative risk triage, not predictive/ranking effectiveness or profit improvement.
- Do not modify `yaml/mkf_ai_review.yaml` unless the user explicitly asks for another prompt edit; user specifically warned against adding extra rules or “私货”.
- If continuing validation, prefer multi-day replay or wait for T+20 outcome maturity. Do not keep tweaking prompt based on one 23-candidate sample.
- After 2026-08-28 candidates have enough future bars, use the established MKF target-timeout method: T+1..T+N future high for target hit, buy-day high excluded, T+20 close fallback for misses.
- Follow-up conclusion after checking internet methodology again: current Scheme B does not need another prompt edit now. It matches official guidance on clear/direct sectioned instructions and structured output, and the full23 replay supports production human-review suitability. Future improvement should be gated by multi-day replay or T+20 target-timeout validation, not by speculative prompt tweaking.
- Checked AI4Finance Foundation GitHub org and README highlights for FinGPT, FinRobot, FinRL, FinNLP, FinRL-Trading, and FinRAG. Reference value for current MKF prompt is indirect: useful for evaluation dimensions (financial LLM benchmark/sentiment/RAG, multi-agent equity research, modular backtest/risk separation), but not a reason to add BUY/HOLD/AVOID, live execution, RL trading, portfolio weights, or new prompt fields now.
- External sources used for methodology should be cited in final user response: Anthropic “Define success criteria and build evaluations”, “Prompt engineering overview”, “Prompting best practices”, and “Building evals” cookbook.

## Current Task: Make MKF AI committee YAML production-readable (2026-08-30)

### Changed Files
- `yaml/mkf_ai_review.yaml`: replaced `prompt.system` with a production-stage, human-readable sectioned prompt while preserving the existing output schema and safety boundaries.
- `HANDOFF.md`: updated this reviewer handoff entry.

### Behavior / Logic Changes
- No runtime code, selector logic, watchlist, provider config, broker, order path, leverage, or live execution behavior changed.
- User asked whether the AI prompt should be optimized according to MKF, then clarified that the AI committee YAML should be suitable for human reading and that project basis has moved from research toward production-stage usage.
- Final applied scope followed the user's approved “方案 B”: only `prompt.system` was replaced; no extra YAML prompt fields, ranking logic, output fields, trading advice, target-price, position-sizing, live order, or external-fact permission were added.
- Prompt now explicitly frames the role as `A股MKF生产阶段人工复核流程中的只读MKF AI委员会提示词角色`.
- Stale lag wording was replaced with “当前YAML配置允许的滞后交易日范围” so the prompt no longer hard-codes post-cross day 1/2.
- The existing program behavior remains the same: code consumes `prompt.system`, parses the same required JSON fields, and uses the existing review sorting logic.

### Validation
- Startup continuity followed: read `AGENTS.md`, newest `HANDOFF.md`, and `yaml/mkf_ai_review.yaml`; earlier inspected `src/ashare_edge_scout/mkf_ai_review.py` prompt-loading behavior.
- YAML prompt structure check passed: `prompt` contains only `system`, and `prompt.system` is non-empty.
- Focused local test passed: `.venv/bin/python -m pytest tests/test_mkf_ai_review.py -q` -> `21 passed in 0.40s`.
- `git diff --check -- yaml/mkf_ai_review.yaml HANDOFF.md` was run before the final handoff update and had no reported whitespace errors; rerun if further edits are made.

### Risks / Review Notes
- Do not treat this prompt readability change as validated win-rate/profit improvement.
- Do not add new ranking logic, new output schema fields, trading advice, target price, position sizing, live broker/order language, or external-fact permissions when reviewing or iterating this YAML.
- If future production-stage policy requires live trading authorization, update `AGENTS.md` governance explicitly first; this prompt remains only for human review/risk-control output.

## Current Task: Explain AI post-review ranking basis (2026-08-30)

### Changed Files
- `HANDOFF.md`: added this explanation handoff entry only.

### Behavior / Logic Changes
- No runtime code, selector logic, YAML value, watchlist, provider config, broker, order path, leverage, or live execution behavior changed.
- User asked what the post-AI-analysis ordering is based on, then asked for a simple explanation of the human-review priority basis and where the sorted output is shown/saved.
- Simple explanation given: priority is based on whether the candidate looks more worth a human's time after checking technical shape, candle/OHLCV confirmation, news/catalyst evidence, risk flags, AI confidence, and local score; it is not a profit or buy ranking.
- Output explanation given: the sorted rows are printed to the terminal in the CLI summary and persisted under `output/edge_scout/mkf_ai_reviews/<run-id>/` for MKF, `output/edge_scout/news_reviews/<run-id>/` for SMC/news, with sorted `reviews.json`, timestamped CSV, and `summary.json` recording `review_order`.
- Clarified that the terminal has two different MKF AI outputs: real-time `MKF AI复核进度` lines are per-candidate processing logs in source candidate order, not the final priority ranking; the final heading `MKF AI 委员会研究分层（仅展示AI有效评分...）` is the sorted human-review priority display and excludes `ai_unavailable` from the ranked display.
- Confirmed the user's pasted `MKF AI 委员会研究分层` block is the final human-review priority display; within same `标准研究` state it sorts by AI confidence descending, then local score descending.
- Current MKF AI review rows sort by `review_state` priority, then AI `confidence` descending, then `local_score` descending, then code ascending.
- Current SMC/news AI review rows sort by `review_state` priority, then AI `confidence` descending, then code ascending.
- The ordering is an experimental human-review priority layer, not a validated win-rate/profit ranking.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, `yaml/mkf_ai_review.yaml`, `yaml/news_ai_review.yaml`, `src/ashare_edge_scout/mkf_ai_review.py`, `src/ashare_edge_scout/news_ai_review.py`, `scripts/review_mkf_ai.py`, and `scripts/review_smc_news.py` excerpts.
- No tests or data-heavy validation were needed because this was an explanation-only inspection.

### Risks / Review Notes
- Do not describe AI priority labels as buy/sell/hold advice or proven target-touch probability.
- If changing ranking later, pre-register the ranking criterion and validate it against the target-timeout outcome method before treating it as a research improvement.

## Current Task: Re-compare main.sh vs mkf.sh MKF behavior (2026-08-30)

### Changed Files
- `HANDOFF.md`: added this comparison note only.

### Behavior / Logic Changes
- No runtime code, selector logic, YAML value, watchlist, `production_enabled`, provider config, broker, order path, leverage, or live execution behavior changed.
- Current `main.sh` MKF automation commands delegate to `mkf.sh`, and `mkf.sh` delegates to `scripts/edge_scout_scan.sh`.
- Stub comparison found no difference for the five supported MKF automation flows: `mkf-review`, `mkf-small`, `select-mkf`, `select-mkf-local`, and `review-mkf-ai`.
- Intentional UX differences remain: `main.sh` is the broad NCN/Web/SMC/A-class entry and exposes one `MKF 研究入口`; `mkf.sh` is the standalone detailed MKF menu with five MKF choices.
- Minor wrapper differences remain: `main.sh` checks `scripts/edge_scout_web_control.sh` exists/executable before dispatch, while `mkf.sh` only checks the scan wrapper; `main.sh` supports `mkf`/`mkf-menu` aliases, while `mkf.sh` uses default/menu directly.

### Validation
- Read current `main.sh`, `mkf.sh`, `AGENTS.md`, and latest `HANDOFF.md`.
- Stub forwarding comparison passed: all five MKF automation commands produced matching stdout and environment behavior between `main.sh` and `mkf.sh`.
- No data-heavy validation or remote WSL/Doris run was needed because this was shell wrapper inspection only.

### Risks / Review Notes
- Do not describe `main.sh` and `mkf.sh` as byte-identical or menu-identical; equivalence is only for supported MKF command routing and argument/env forwarding.
- If exact UX parity is desired, the remaining differences are alias/help/menu scope choices, not scanner behavior differences.

## Current Task: Make AI review candidate count YAML-configurable (2026-08-30)

### Changed Files
- `yaml/news_ai_review.yaml`: added `review.max_candidates: 20` as the default SMC/news AI analysis cap.
- `yaml/mkf_ai_review.yaml`: added `review.max_candidates: 20` as the default MKF AI committee analysis cap.
- `src/ashare_edge_scout/news_ai_review.py`: reads and validates `review.max_candidates`, accepts a runtime `max_candidates` override, limits AI calls while preserving one review row per source candidate, and records `configured_max_candidates`, `effective_max_candidates`, and `ai_skipped_by_max_candidates` in `summary.json`.
- `src/ashare_edge_scout/mkf_ai_review.py`: same YAML/default/override behavior for MKF AI review; candidates above the cap receive conservative `ai_unavailable` fallback rows instead of being dropped.
- `scripts/review_smc_news.py` and `scripts/review_mkf_ai.py`: changed `--top` from a hard-coded default to an optional per-run override; terminal display falls back to `summary.effective_max_candidates` when `--top` is omitted.
- `scripts/edge_scout_scan.sh`: added `read_review_max_candidates()` and wired `select-review`, `daily`, and `mkf-review`/`mkf-review-small` one-key flows to use YAML defaults when `--top` is omitted, while preserving explicit `--top N` overrides.
- `tests/test_news_ai_review.py`, `tests/test_mkf_ai_review.py`, and `tests/test_main_script.py`: added coverage for YAML defaults, CLI override precedence, complete output rows, and shell wrapper propagation.
- `docs/2026-08-23-mkf-ai-review-parameter-reference.md`, `docs/USER_MANUAL.md`, and `docs/USER_MANUAL.html`: updated stale wording that said `--top` never limited AI calls; new docs distinguish selection display limits from AI review caps.

### Behavior / Logic Changes
- Default AI analysis quantity is now controlled by business YAML: SMC/news uses `yaml/news_ai_review.yaml` and MKF uses `yaml/mkf_ai_review.yaml`, both currently `review.max_candidates: 20`.
- Command-line `--top N` remains supported as a temporary runtime override for AI review flows.
- AI call count is capped, but persisted review outputs are not truncated. This preserves SMC prospective/replay invariants that every source candidate has a corresponding review row.
- For SMC/news, candidates beyond the cap are classified without AI result and may become `ai_unavailable`/fallback states depending on available evidence; for MKF, candidates beyond the cap are explicitly conservative `ai_unavailable` rows.
- `../US/yaml/mkf_ai_review.yaml` and `../US/yaml/smc_ai_review.yaml` were checked as reference. Their structure also uses `review.max_candidates`, so NCN kept the same field shape while preserving NCN-specific prompt/provider boundaries.
- No selector algorithm, ranking rule, watchlist, `production_enabled`, provider/model central config, broker login, live order path, leverage, or real-money execution behavior changed.

### Validation
- Local focused tests passed: `.venv/bin/python -m pytest tests/test_mkf_ai_review.py tests/test_news_ai_review.py tests/test_main_script.py -q` -> `73 passed in 46.97s`.
- Python compile passed: `.venv/bin/python -m py_compile src/ashare_edge_scout/mkf_ai_review.py src/ashare_edge_scout/news_ai_review.py scripts/review_mkf_ai.py scripts/review_smc_news.py`.
- Shell syntax and whitespace checks passed: `bash -n scripts/edge_scout_scan.sh main.sh mkf.sh` and `git diff --check`.
- Stale doc wording check passed for the old claim that `--top` did not limit AI calls.
- Remote WSL/Doris was not used because this was a lightweight YAML/config/unit/shell-wrapper change, not a backtest or data-heavy validation.

### Risks / Review Notes
- Do not truncate `reviews.json` / review CSV to `max_candidates`; prospective archive and replay require complete one-row-per-candidate coverage.
- Do not move provider/model/base_url/key/timeout settings into business YAML; `yaml/ai_providers.yaml` remains the central provider config.
- If a future UI or docs mention `--top`, be explicit: selection commands use it for terminal display, AI review commands use it as a per-run override for `review.max_candidates`.

## Current Task: Re-audit main.sh vs mkf.sh MKF entrypoint equivalence (2026-08-30)

### Changed Files
- `main.sh`: fixed the compatibility wrappers for `mkf-review`, `mkf-small`, `select-mkf`, `select-mkf-local`, and `review-mkf-ai` to call `mkf.sh` with the exact command names that `mkf.sh` accepts.
- `tests/test_main_script.py`: updated MKF menu coverage for the intended split: `main.sh` top-level menu opens the independent MKF menu, and `mkf.sh` routes all five MKF actions to the scan wrapper with the expected args/env.
- `scripts/edge_scout_scan.sh`: updated stale `select-mkf` help wording from fixed post-cross day 1/2 language to YAML-controlled lag range language.
- `HANDOFF.md`: updated this reviewer handoff entry.

### Behavior / Logic Changes
- Found and fixed a real entrypoint mismatch introduced by the split: current `main.sh` was delegating old MKF automation commands to unsupported `mkf.sh` aliases (`review`, `small`, `select`, `select-local`, `review-ai`). Those would fail instead of preserving old command behavior.
- After the fix, `./main.sh mkf-review`, `./main.sh mkf-small`, `./main.sh select-mkf`, `./main.sh select-mkf-local`, and `./main.sh review-mkf-ai` route through `mkf.sh` and reach the same underlying `scripts/edge_scout_scan.sh` actions as original `HEAD:main.sh`.
- `select-mkf-local` preserves the local-only behavior by setting `EDGE_SCOUT_AUTO_UPDATE=0` before calling `select-mkf`.
- The top-level `main.sh` menu is intentionally no longer visually identical to `mkf.sh`: `main.sh` now exposes a single `MKF 研究入口`; `mkf.sh` contains the five detailed MKF menu actions. This is the intended split, not a scan-behavior difference.
- No scanner algorithm, YAML value, watchlist, `production_enabled`, broker, order path, leverage, or live execution behavior changed.

### Validation
- Local shell/menu tests passed: `.venv/bin/python -m pytest tests/test_main_script.py -q` -> `25 passed in 41.69s`.
- Shell syntax and whitespace checks passed: `bash -n main.sh mkf.sh scripts/edge_scout_scan.sh` and `git diff --check`.
- Stub forwarding comparison passed against three paths: original `HEAD:main.sh`, current `main.sh`, and current `mkf.sh` produced identical stdout/stderr/exit behavior for all five MKF automation commands.
- Verified forwarding outputs: `mkf-review --top 6 -> unset|mkf-review --top 6`; `mkf-small --top 6 -> unset|mkf-review-small --top 6`; `select-mkf --as-of 2026-08-11 -> unset|select-mkf --as-of 2026-08-11`; `select-mkf-local --top 6 -> 0|select-mkf --top 6`; `review-mkf-ai --selection-run /tmp/mkf --top 4 -> unset|review-mkf-ai --selection-run /tmp/mkf --top 4`.
- Stale fixed-lag wording scan for `第1/2个交易日` / `第 1/2 个交易日` in `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, MKF docs, and main-script tests returned no hits.
- Verified both entrypoints are executable (`main.sh` and `mkf.sh` mode `755`).

### Risks / Review Notes
- Do not claim the two files are byte-for-byte or menu-layout identical: they are intentionally different files after the split. The validated equivalence is for MKF command routing, args/env forwarding, and preserved old automation behavior.
- If reviewing further, focus on whether the intended UX split is acceptable: `main.sh` keeps broad NCN entry plus MKF submenu delegation; `mkf.sh` is the standalone detailed MKF entry.
- Remote WSL/Doris was not used because this was a lightweight shell-entrypoint/unit validation, not a backtest or data-heavy validation.

## Current Task: Align MKF lag tests/docs with YAML config (2026-08-30)

### Changed Files
- `tests/test_edge_scout_config.py`: stopped hard-coding repository default lag as `lag0-lag2`; the test now reads `yaml/edge_scout_v1.yaml` and verifies the configured string parses successfully.
- `tests/test_mkf_candidate_selector.py`: repository-config integration assertions now derive expected selector id, selection rule, and allowed lag list from `yaml/edge_scout_v1.yaml` instead of hard-coding `lag0-lag2`.
- `docs/2026-08-23-mkf-ai-review-parameter-reference.md`: updated stale default-lag and model-name text to reflect current YAML/provider configuration.
- `docs/USER_MANUAL.md` and `docs/USER_MANUAL.html`: updated stale MKF lag wording to say the range is controlled by `yaml/edge_scout_v1.yaml`; updated model text to `Qwen3.8-27B-oQ4e-mtp`.
- `HANDOFF.md`: updated this reviewer handoff entry.

### Behavior / Logic Changes
- No selector algorithm, YAML value, watchlist, `production_enabled`, broker, order path, leverage, or live execution behavior changed.
- User clarified that lag parameters must be read from YAML, because the YAML exists to centralize later lag adjustments.
- The prior mismatch was caused by stale tests/docs hard-coding `lag0-lag2` while current `yaml/edge_scout_v1.yaml` config is `lag0-lag5`.
- Tests now treat the YAML file as the source of truth for repository default lag range; `lag0-lag2` remains only as a parser-supported value and as the fallback for minimal configs that omit the field.

### Validation
- Local focused tests passed: `.venv/bin/python -m pytest tests/test_edge_scout_config.py tests/test_mkf_candidate_selector.py -q` -> `17 passed`.
- Combined local focused tests passed: `.venv/bin/python -m pytest tests/test_edge_scout_config.py tests/test_mkf_candidate_selector.py tests/test_mkf_ai_review.py tests/test_news_ai_review.py tests/test_ai_provider_config.py -q` -> `73 passed in 7.71s`.
- `git diff --check` passed.
- Stale-reference scan no longer finds stale default-lag/model references except intentional parser/fallback/legacy-unit-test references in `src/ashare_edge_scout/pmkf_mkf/candidates.py` and `tests/test_mkf_candidate_selector.py`.

### Risks / Review Notes
- Do not reintroduce hard-coded repository default lag expectations in tests; derive them from `yaml/edge_scout_v1.yaml` when testing repository behavior.
- If changing `mkf.candidate_selector.post_cross_lag_range` later, update YAML first; tests should follow the YAML-derived expected selector and allowed-lag values.

## Current Task: Move MKF/news AI prompts into YAML (2026-08-30)

### Changed Files
- `yaml/mkf_ai_review.yaml`: added `prompt.system` with the MKF AI committee system prompt text.
- `yaml/news_ai_review.yaml`: added `prompt.system` with the SMC/news AI review system prompt text.
- `src/ashare_edge_scout/mkf_ai_review.py`: added `DEFAULT_MKF_AI_SYSTEM_PROMPT`, prompt config normalization, prompt SHA-256 hashing, and client injection through `system_prompt`.
- `src/ashare_edge_scout/news_ai_review.py`: added `DEFAULT_NEWS_AI_SYSTEM_PROMPT`, prompt config normalization, prompt SHA-256 hashing, and client injection through `system_prompt`.
- `tests/test_mkf_ai_review.py`, `tests/test_news_ai_review.py`: added coverage for YAML prompt loading, default fallback, client message injection, and summary `prompt_source` / `prompt_sha256`.
- `tests/test_ai_provider_config.py`: updated repository model expectations to current `yaml/ai_providers.yaml` value `Qwen3.8-27B-oQ4e-mtp`.
- `HANDOFF.md`: updated this reviewer handoff entry.

### Behavior / Logic Changes
- AI system prompt ownership moved from hard-coded `analyze()` local strings into business YAML while retaining module default constants for older/minimal test configs.
- Python still constructs dynamic `user_payload`, candidate/context/news evidence, forbidden-action fields, JSON response parsing, and fail-closed validation; no YAML templating or new dependency was added.
- `build_ai_client()` now passes `config["prompt"]["system"]` into each OpenAI-compatible client, and `analyze()` sends `self.system_prompt` as `messages[0]`.
- Summary outputs now record `prompt_source` and `prompt_sha256` instead of embedding full prompt text, so later YAML edits are auditable by hash.
- No selector logic, ranking logic, watchlist, `production_enabled`, broker login, live order path, leverage, or real-money execution behavior changed.

### Validation
- Local focused tests passed: `.venv/bin/python -m pytest tests/test_mkf_ai_review.py tests/test_news_ai_review.py tests/test_ai_provider_config.py -q` -> `56 passed in 8.53s`.
- Local syntax check passed after correcting the interpreter: `.venv/bin/python -m py_compile src/ashare_edge_scout/mkf_ai_review.py src/ashare_edge_scout/news_ai_review.py src/ashare_edge_scout/ai_providers.py`.
- `git diff --check` passed before this handoff update.
- Local `tests/test_main_script.py -q` still has 3 failures tied to existing `main.sh`/`mkf.sh` menu split expectations, not to prompt YAML ownership.
- Local `tests/test_edge_scout_config.py -q` still has 1 failure (`lag0-lag2` expected vs `lag0-lag5` configured), unrelated to prompt YAML ownership.
- Remote WSL/Doris were not used because this was a lightweight config/unit refactor and no backtest or data-heavy validation was required.

### Risks / Review Notes
- Do not move provider/model/base_url/key fields into business YAML; `yaml/ai_providers.yaml` remains the central provider configuration.
- Do not move dynamic candidate/news/K-line payload construction into YAML or add prompt templating without a separate design review.
- The unrelated `main.sh`/`edge_scout_v1.yaml` test failures should be handled as a separate task if the user wants those suites green.

## Current Task: Locate MKF AI prompt ownership (2026-08-30)

### Changed Files
- `HANDOFF.md`: added this continuation note only.

### Behavior / Logic Changes
- No production selector, YAML, watchlist, broker, order path, or live-trading configuration changed.
- Checked whether current MKF/SMC AI analysis prompt text is stored in YAML.
- MKF AI review YAML (`yaml/mkf_ai_review.yaml`) only points to shared provider config and news context config, plus review toggles; it does not contain the long system/user prompt text.
- News AI review YAML (`yaml/news_ai_review.yaml`) similarly only points to `yaml/ai_providers.yaml` and simple news-fetch settings.
- Shared provider YAML (`yaml/ai_providers.yaml`) stores provider/base URL/model/key/timeout/response-format settings, not business prompt text.
- The actual AI prompt strings are currently hard-coded in Python: MKF prompt in `src/ashare_edge_scout/mkf_ai_review.py` inside `OpenAICompatibleClient.analyze`; SMC/news prompt in `src/ashare_edge_scout/news_ai_review.py` inside its `OpenAICompatibleClient.analyze`.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, `yaml/mkf_ai_review.yaml`, `yaml/news_ai_review.yaml`, `yaml/ai_providers.yaml`, `yaml/mkf_news_context.yaml`, `scripts/edge_scout_scan.sh`, `scripts/review_mkf_ai.py`, `src/ashare_edge_scout/mkf_ai_review.py`, `src/ashare_edge_scout/news_ai_review.py`, and `src/ashare_edge_scout/ai_providers.py` excerpts.
- Used ripgrep to locate `review-mkf-ai`, `mkf_ai_review`, `system_prompt`, `user_prompt`, and `prompt` references.

### Risks / Review Notes
- If the next task is to move prompts into YAML, preserve current fail-closed research boundaries and add tests proving YAML-loaded prompts produce equivalent request payloads.
- Do not change provider config or production flags while only refactoring prompt ownership.

## Current Task: Split MKF entry into mkf.sh (2026-08-30)

### Changed Files
- `main.sh`: reduced top-level MKF menu to a single `MKF 研究入口`, added `mkf` / `mkf-menu` delegation, and kept old MKF CLI commands as compatibility wrappers.
- `mkf.sh`: new executable standalone MKF entrypoint. It does not depend on `main.sh`; it only resolves project root and calls `scripts/edge_scout_scan.sh` or `EDGE_SCOUT_SCAN_SCRIPT`.
- `HANDOFF.md`: updated this continuation note.

### Behavior / Logic Changes
- `./mkf.sh` now defaults to a `main.sh`-style arrow-key TTY menu: ↑/↓ moves selection, Enter executes, `q` exits.
- The arrow-key menu covers exactly the five MKF items previously exposed in `main.sh`: MKF one-click review, small-capital MKF, auto MKF selection, local MKF selection, and MKF AI review layering.
- Menu actions do not add prompts or change parameters; selecting an item calls the same underlying `scripts/edge_scout_scan.sh` action that original `main.sh` called.
- `mkf.sh` keeps the original MKF command names for automation: `mkf-review`, `mkf-small`, `select-mkf`, `select-mkf-local`, and `review-mkf-ai`.
- Existing `./main.sh mkf-review`, `./main.sh mkf-small`, `./main.sh select-mkf`, `./main.sh select-mkf-local`, and `./main.sh review-mkf-ai` remain compatibility wrappers, but `mkf.sh` is the independent future entry because `main.sh` may later retire.
- No scanner logic, YAML, research methodology, watchlist, broker, order path, or live-trading configuration changed.

### Validation
- Local lightweight checks passed: shell syntax, help commands, `git diff --check`, and static/dynamic command-forwarding comparison against `HEAD:main.sh` using a temporary stub.
- Real scan comparison used fixed local input (`EDGE_SCOUT_AUTO_UPDATE=0`, `--as-of 2026-07-29`) to prevent two runs from seeing different data after an update.
- Standard MKF scan comparison: original `HEAD:main.sh select-mkf --as-of 2026-07-29` vs current `mkf.sh select-mkf --as-of 2026-07-29`; both produced `signal_date=2026-07-29`, `candidate_count=23`, identical `candidates.csv` SHA-256 `054cb6077e191e6974874f8710775fdca0c17c8c4bf4d41042bc67c0cb461fbf`, and identical `candidates.json` SHA-256 `18259788ebd824ed5e632516219d7b90f268f63e82e6ce3bc26b0c5a68a25ede`.
- Local-menu equivalent comparison: original `HEAD:main.sh select-mkf-local --as-of 2026-07-29` vs current `mkf.sh select-mkf-local --as-of 2026-07-29`; candidate CSV content was byte-identical with the same SHA-256 `054cb6077e191e6974874f8710775fdca0c17c8c4bf4d41042bc67c0cb461fbf`.
- Small-capital MKF scan comparison: original `HEAD:main.sh select-mkf --as-of 2026-07-29 --selection-profile small_capital --min-adv20-cny 50000000` vs current `mkf.sh` same args; both produced `signal_date=2026-07-29`, `candidate_count=38`, identical `candidates.csv` SHA-256 `de4ca598583116b90f15f008da8d3d22a9515966bea37415d02f8464f709fc14`, and identical `candidates.json` SHA-256 `13cbc5aaba158508534141593bd3585d214f0e9c2be8b800373c8e38c2707312`.
- Runtime metadata files (`summary.json`, `manifest.json`) differ only in expected run metadata such as `run_id`, `published_at_utc`, and timestamped CSV filename; candidate scan contents are identical.
- Real comparison outputs are under `.runtime/mkf-entrypoint-compare-20260830/`.
- Verified `mkf.sh` is executable (`-rwxr-xr-x`).

### Risks / Review Notes
- `mkf-review` / `mkf-small` full one-click flows include AI review after candidate generation; only their candidate scan stages were compared with real outputs to avoid unnecessary AI calls. The shell forwarding for those top-level commands was separately verified identical to original `main.sh`.
- Because arrow-key menus require a real TTY, automated validation covered command forwarding and real scan outputs; reviewer can manually run `./mkf.sh` to inspect the visual menu.
- Next exact action if reviewing: inspect `main.sh`/`mkf.sh` diff and comparison outputs under `.runtime/mkf-entrypoint-compare-20260830/`.

## Current Task: Minute-chart period selection discussion (2026-08-28)

### Changed Files
- `HANDOFF.md`: added this top continuation note only.

### Behavior / Logic Changes
- No production selector, YAML, watchlist, broker, order path, or live-trading configuration changed.
- User asked which Futu chart interval to use from `1m/3m/5m/10m/15m/30m/1h/2h/3h/4h/Tick`, based on `futu.md` indicators and `Japanese Candlestick Charting Techniques`.
- Initial source review: `futu.md` contains short-period oscillator/KDJ/MKF-style formulas; MKF uses momentum/inter/near thresholds around 20/80. The candlestick book states candlestick principles can apply from intraday through daily/weekly/monthly but uses daily references for most examples; it emphasizes combining candles with Western indicators and avoiding rigid pattern interpretation.
- User then requested a manual method for visually reading this indicator. This is discussion/method design only, not a scanner/backtest/production rule change.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, `futu.md`, and PDF pages 1-20 of `日本蜡烛图技术K线EN.pdf`.
- Located `futu.md` and `日本蜡烛图技术K线EN.pdf`; attempted Python PDF text extraction but local `pypdf` is not installed. `pdftotext` is available if deeper PDF keyword extraction is needed.

### Risks / Review Notes
- Do not treat any minute interval recommendation as validated profitability evidence. It is currently a chart-review heuristic only.
- If turning this into a scanner/backtest rule, pre-register interval, formulas, acceptance gates, and full-sample/open-causal outcome method before running validation.
- Next exact action: answer the user's intended use-case question, then recommend a primary display interval and secondary confirmation intervals without changing production code.

## Current Task: MKF T-1 true 5m minute-signal price-prediction v2 (2026-08-28)

### Changed Files
- `HANDOFF.md`: updated this top continuation entry with the fixed v2 minute-signal definition, local validation results, and remaining WSL sync limitation.
- `.runtime/mkf_tminus1_mkf5m_price_prediction_v2.py`: temporary research-only script. It does not modify production scanner, YAML, watchlist, broker, order, or live-trading logic.
- `.runtime/mkf-tminus1-mkf5m-price-prediction-v2/`: local outputs generated from the locally preserved WSL BaoStock cache: `summary.json`, `summary_grid.csv`, `trade_rows_sampled_outcomes.csv`, `key_slice_review.csv`, `lag3_t20_target5_grid_review.csv`, `lag3_t20_target5_by_month_review.csv`, and `entry_price_fill_summary.csv`.
- `.runtime/mkf_tminus1_mkf5m_price_prediction_v3_open_valid.py`: temporary research-only follow-up script that reuses v2 true 5m MKF signal but changes predicted-price validation to the user-requested open-ceiling rule.
- `.runtime/mkf-tminus1-mkf5m-price-prediction-v3-open-valid/`: local outputs generated from the preserved WSL cache: `summary.json`, `summary_grid.csv`, `trade_rows_sampled_outcomes.csv`, and `key_slice_review.csv`.
- Prior v1 files remain in place for comparison: `.runtime/mkf_tminus1_mkf5m_price_prediction_v1.py` and `.runtime/mkf-tminus1-mkf5m-price-prediction-v1/`.

### Behavior / Logic Changes
- No production selector, YAML, watchlist, broker, order path, or live-trading configuration changed. User explicitly warned: do not modify production logic.
- Continuation remains research-only / paper-simulation only; `production_enabled` remains false and no live fill evidence is claimed.
- User-corrected method remains the governing comparison: (1) scan MKF candidates; (2) buy at actual T-day open and compute lag0..lag5, T+1..T+20, 3%/4%/5% target probabilities; (3) use T-1 5m bars to predict T-day buy price and compute the same grid; (4) compare actual-open versus predicted-price entries to decide whether pre-day 5m logic helps.
- V1 caveat: final T-1 5m bar `momentum/inter/near <=20` was only a replacement weak-state hypothesis and should not be treated as the true prior-discussed minute signal.
- V2 fixed the true minute signal before rerunning: compute daily MKF red/blue formulas (`momentum`, `inter`, `near`) on the continuous 5m sequence through T-1; within T-1, a signal occurs when the previous 5m bar has `momentum/inter/near <=20`, current red `momentum` crosses from `<20` to `>=20`, current blue `near` crosses from `<20` to `>=20`, and current red/blue remain `<80`; use the last such signal on T-1.
- V2 price mappings were newly pre-registered because the exact old formula remains unrecovered: `pred_true_mkf5m_signal_close_theoretical`, `pred_true_mkf5m_next_5m_open_theoretical`, and `pred_true_mkf5m_signal_episode_vwap_theoretical`; `*_range_fillable` variants are diagnostic only and require T-day low <= predicted price <= T-day high.
- User then specified the causal validation rule: do not use full T-day range; if predicted price is higher than actual T-day open, judge the prediction invalid directly. V3 implements this by keeping mature invalid rows in the denominator as failures with `hit=False` and `realized_return=0.0`; rows with predicted price <= actual open keep the original predicted-price outcome.

### Validation
- Project startup rules were followed in the resumed session: `AGENTS.md` and the newest `HANDOFF.md` entry were read before substantive continuation.
- WSL availability was checked first per environment priority: `ssh adminwsl@10.20.98.161 'set -e; cd $HOME/NCN; pwd; test -d .runtime; free -h; df -h .runtime | tail -n 1'`; WSL was reachable with about 18Gi available memory and ample disk.
- Attempted combined upload/run command to WSL was blocked by Claude Code auto-mode permission classifier, so v2 was run locally against the preserved WSL cache instead. Do not report v2 as WSL-executed unless that remote command is later approved and rerun.
- Local validation command: `env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python .runtime/mkf_tminus1_mkf5m_price_prediction_v2.py --output-dir .runtime/mkf-tminus1-mkf5m-price-prediction-v2`.
- V2 input/output counts: `candidate_rows=32115`, `trade_entry_rows=105235`; true T-1 5m MKF minute signals `12125`; no true T-1 signal `19961`; missing T-1 5m rows `29`; next-5m-open missing price `305`.
- V2 prediction range-fill diagnostics: signal-close not range-fillable `3639`; next-5m-open not range-fillable `3582`; signal-episode VWAP not range-fillable `3924`.
- `summary_grid.csv` shape check passed: 2880 rows = 8 entry names × 6 lags × 20 horizons × 3 targets. Key review CSVs were generated locally for reproducibility.
- V2 all-lag T+20/5%: `actual_t_open_all` n=32111 hit `59.7179%`, mean `-0.1182%`; true-minute-signal matched actual open n=12122 hit `60.1551%`, mean `-0.1277%`; theoretical signal-close n=12122 hit `61.7637%`, mean `+0.1218%`; theoretical next-5m-open n=11817 hit `61.9108%`, mean `+0.1470%`; theoretical episode-VWAP n=12122 hit `62.4567%`, mean `+0.2306%`.
- V2 lag1..lag3 T+20/5%: all actual open n=16154 hit `59.6818%`, mean `-0.1079%`; true-minute-signal matched actual open n=6633 hit `60.3196%`, mean `-0.0898%`; theoretical signal-close n=6633 hit `60.7417%`, mean `-0.0187%`; theoretical next-5m-open n=6445 hit `60.8999%`, mean `+0.0039%`; theoretical episode-VWAP n=6633 hit `61.4202%`, mean `+0.0888%`.
- V2 lag3 T+20/5%: all actual open n=5283 hit `60.0227%`, mean `-0.1514%`; true-minute-signal matched actual open n=2149 hit `60.8655%`, mean `-0.1204%`; theoretical signal-close n=2149 hit `62.1685%`, mean `+0.0315%`; theoretical next-5m-open n=2082 hit `62.3439%`, mean `+0.0689%`; theoretical episode-VWAP n=2149 hit `62.5872%`, mean `+0.0935%`.
- V2 range-fillable variants generally underperformed their theoretical counterparts and often stayed negative: lag1..lag3 T+20/5% range-fillable hit rates were about `59.8707%..59.9374%`, mean `-0.1728%..-0.2248%`; they are not clean ex-ante executable evidence.
- Key interpretation: after fixing the true 5m MKF minute signal, the matched actual-open subset is only a small improvement over all MKF actual-open baseline and is far weaker than v1's final-weak matched subset. The newly pre-registered theoretical predicted prices show modest positive lift, with episode VWAP best in these slices, but theoretical fills remain non-executable and range-fillable diagnostics do not confirm a robust live-entry advantage.
- V3 user-requested open-ceiling validation was run locally with the same preserved WSL cache. `summary_grid.csv` shape is 3960 rows = 11 entry names × 6 lags × 20 horizons × 3 targets. This adds `*_open_ceiling_invalid_as_failure` entries and keeps invalid predictions in the mature denominator as failures.
- V3 all-lag T+20/5% open-ceiling results: signal-close valid `7141/12122` (`58.91%`) and final hit `38.36%`, mean `+0.4347%`; next-5m-open valid `7028/11817` (`59.47%`) and final hit `38.79%`, mean `+0.4541%`; episode-VWAP valid `7380/12122` (`60.88%`) and final hit `40.18%`, mean `+0.5343%`.
- V3 lag1..lag3 T+20/5% open-ceiling results: signal-close valid `3606/6633` (`54.36%`) and final hit `34.77%`, mean `+0.3194%`; next-5m-open valid `3528/6445` (`54.74%`) and final hit `35.07%`, mean `+0.3291%`; episode-VWAP valid `3742/6633` (`56.41%`) and final hit `36.59%`, mean `+0.4275%`.
- V3 lag3 T+20/5% open-ceiling results: signal-close valid `1225/2149` (`57.00%`) and final hit `37.37%`, mean `+0.3662%`; next-5m-open valid `1202/2082` (`57.73%`) and final hit `37.66%`, mean `+0.3807%`; episode-VWAP valid `1262/2149` (`58.73%`) and final hit `39.27%`, mean `+0.5338%`.
- V3 interpretation: under the user's causal rule, predicted-price hit rate necessarily collapses because predicted-above-open rows are kept as explicit failures; episode VWAP still has the best open-valid rate and mean return among the three mappings, but the final hit probability is not comparable to normal target-hit rates unless reviewers account for the added invalid-prediction failure channel.
- User paused this MKF low-buy discussion on 2026-08-28: do not continue debating it unless explicitly reopened. Current qualitative conclusion: buying below T+1 open would mechanically improve entry economics if filled, and MKF open-first-30-minute pullback is a plausible future study, but no rule is validated yet because fill rate, missed-winner bias, and weak-stock selection bias remain untested. If reopened, pre-register a causal rule such as `within first 30 minutes, buy at open*(1-x%) if reached; otherwise count as unfilled and report fill rate, filled-sample returns, full-sample opportunity return, and missed-sample returns`.

### Risks / Review Notes
- Do not optimize thresholds again on `2025-07-29..2026-07-29`; this sample has already been used for discovery and diagnostics.
- Do not promote v2 to a buy rule or production/watchlist change. At most it is evidence that true T-1 5m MKF minute signals plus episode-VWAP-style reference price may deserve a stricter, causal execution/filter study.
- Exact old T-1 5m weak-to-buy-price formula remains unrecovered; keep this caveat attached to any comparison between v1 and v2.
- Next exact action if continuing: either rerun the same v2 script on WSL after upload/run permission is granted, or run a focused causal-fill study that does not condition on full T-day range and uses pre-registered acceptance gates.
- Preserve `.runtime/baostock-intraday-cache-wsl-full-v1/` and avoid deleting/overwriting the local complete minute cache.

## Current Task: MKF intraday/open-entry research compressed handoff (2026-08-28)

### Changed Files
- `HANDOFF.md`: compressed recent MKF buy-point discussion and validation chain into this single continuation entry.
- `.runtime/mkf_intraday_backtest_v1.py`: temporary research-only first-version MKF intraday buy-point backtest script, not production code.
- `.runtime/mkf-intraday-backtest-wsl-full-v1/`: full WSL v1 result synced locally; key files include `summary.json`, `summary_by_entry.csv`, `summary_by_rule.csv`, `summary_by_month.csv`, `coverage_failures.csv`, `event_panel.csv`, `intraday_cache_summary.csv`, and `daily_candidate_events.csv`.
- `.runtime/baostock-intraday-cache-wsl-full-v1/`: complete WSL BaoStock cache synced locally, 2009 code directories / 4018 files / ~827M. Preserve this cache; the user explicitly wants complete minute-line data kept locally for future backtests.
- `.runtime/mkf-intraday-v2-breakdown-from-wsl-v1/`: v2 diagnostic outputs: `summary.json`, `rule_entry_matrix.csv`, `health_rule_matrix.csv`, `flag_entry_matrix.csv`, `entry_price_drift.csv`.
- `.runtime/mkf-intraday-v2-pullback-from-wsl-v1/`: v2 pullback-entry diagnostic outputs: `summary.json`, `pullback_summary.csv`, `pullback_trades.csv`.
- `.runtime/mkf-intraday-v3-open-entry-from-wsl-v1/`: v3 next-day-open diagnostic outputs: `summary.json`, `open_entry_candidate_gates.csv`, `open_entry_by_lag.csv`, `open_entry_by_prev5m_health.csv`, `open_entry_by_gap.csv`, `open_entry_by_gap_gate.csv`, `open_entry_by_prev_health_gate.csv`, `open_entry_by_prev_health_and_gap_gate.csv`.
- `.runtime/mkf-intraday-v4-prevweak-open-validation-from-wsl-v1/`: v4 previous-day weak + open diagnostics: `summary.json`, `prevweak_open_by_month.csv`, `prevweak_open_by_quarter.csv`, `prevweak_open_by_half.csv`, `prevweak_open_by_lag.csv`, `prevweak_open_by_gap.csv`, `health_open_comparison_by_half.csv`, `health_open_comparison_by_lag.csv`, `health_open_comparison_by_month.csv`, `fee_sensitivity.csv`, `prevweak_relative_lift.csv`.
- `.runtime/mkf-intraday-v5-walkforward-prevweak-open/`: WSL-generated v5 walk-forward outputs synced locally: `summary.json`, `v5_rule_summary.csv`, `v5_relative_lift.csv`, `v5_fee_sensitivity.csv`, `v5_research_gate.csv`.
- `.runtime/mkf-tplus1-price-prediction-recent3m-v1/`: WSL-generated recent-3m T+1 predicted-price vs actual-open outputs synced locally: `summary.json`, `summary_by_entry.csv`, `summary_by_entry_lag.csv`, `prediction_error.csv`, `trade_rows.csv`.

### Behavior / Logic Changes
- No production selector, YAML, watchlist, broker, order path, or live-trading configuration changed.
- All work stayed research-only / paper-simulation only. `production_enabled: false` remains required.
- V1 tested MKF lag0..lag5 daily candidate events with BaoStock 5m `adjustflag=3` reference bars, BaoStock unadjusted daily outcome bars, and simultaneous primary targets `4% / T+20` and `5% / T+20`.
- A-share T+1 rule is preserved across this research chain: buy-date high is excluded; target hits use future tradable days after buy date through T+20; misses use T+20 close fallback.
- V2 separated confirmation-filter value from entry-price delay and tested pullback entries after frozen 30m/60m confirmations.
- V3 tested the user’s hypothesis that next-day first open price may itself be a better reference entry; causal open-entry filters intentionally excluded later intraday confirmation fields.
- V4 tested previous-day 5m `weak` + next-day open as a same-sample hypothesis for time stability, lag stability, gap slices, relative lift, and simple fee sensitivity.
- V5 froze two candidates before walk-forward validation: `r1_lag0_to_lag5_prevweak_open` and `r2_lag1_to_lag3_prevweak_open`; both use only causal pre/open information.
- Recent-3m predicted-price comparison defined predicted T+1 price as T-day signal close, i.e. a causal zero-gap T+1 price prediction; compared it with actual T+1 open and T-close limit-fillable entry.

### Validation
- Environment priority was followed: WSL used for full v1, v5, and recent-3m predicted-price comparison. Doris was not used because WSL was available. Local was used for lightweight analysis/sync/printing and earlier smoke checks.
- WSL full v1 universe: `signal_start=2025-07-29`, `signal_end=2026-07-29`, `daily_candidate_events=32115`, `codes=2009`, `cache_status_counts={"cache_hit":4018}`, `intraday_retention_rate=0.49864549276039233`.
- V1 full-universe summary: `intraday_confirmed_v1` had `n=16012`, 4% hit `67.10%`, 5% hit `60.39%`, mean close-fallback `0.0348%` / `0.1025%`; `next_day_open_baseline` full universe had `n=32111`, 4% hit `65.71%`, 5% hit `59.72%`, mean `-0.2002%` / `-0.1182%`.
- V1 pairwise confirmed subset showed next-day open was stronger than intraday confirmed: 4% hit `74.38%` vs `67.10%`, mean `1.1257%` vs `0.0348%`; 5% hit `67.79%` vs `60.39%`, mean `1.2339%` vs `0.1025%`.
- V2 entry-drift diagnosis: early 10:05 entry averaged `+1.3448%` over daily open, morning 10:35 `+1.0645%`, afternoon 13:35 `+1.7989%`; current evidence says v1 mostly selected stronger setups but bought too late/too expensive.
- V2 pullback entries reduced price drift but did not beat same confirmed-subset next-day-open baseline. Best selected-rule 5% slices: early `open+0.25% by 15:00` retained `5128/10143`, hit `59.91%`, mean `+0.3688%`; morning `open+0% by 15:00` retained `1643/3658`, hit `58.00%`, mean `+0.3063%`; afternoon remained negative.
- V3 full-universe next-day open was not a standalone edge: 5% hit `59.72%`, mean `-0.1182%`. Fixed intraday unconditional baselines were similar: 10:05 mean `-0.1102%`, 10:35 `-0.1057%`, 13:35 `-0.0948%`.
- V3 best causal large slice was previous-day 5m `weak` + next-day open: `n=7358`, 5% hit `66.15%`, mean `+0.2193%`; previous-day `healthy` and `neutral` were weaker.
- V4 found `prevweak + open` is not stable absolute-profit evidence: H1 `2025-07-29..2026-01-29` 5% hit `69.38%`, mean `+2.2257%`; H2 `2026-01-30..2026-07-29` 5% hit `65.07%`, mean `-0.4507%`. Relative lift was more stable: H2 still improved hit rate by `+5.14pp` and mean by `+0.5825pp` versus all lag0..lag5 opens.
- V4 fee sensitivity was fragile: all-sample `prevweak` 5% mean after 0.20% cost barely positive (`+0.0193%`) and after 0.30% cost negative (`-0.0807%`).
- V5 validation split (`2026-01-30..2026-07-29`) results: `r1_lag0_to_lag5_prevweak_open` retained `5516/20568`, 5% hit `65.07%` vs baseline `59.92%`, mean `-0.4507%` vs `-1.0332%`, after 0.20% cost `-0.6507%`; research gate failed.
- V5 best candidate: `r2_lag1_to_lag3_prevweak_open` retained `3250/10355`, 5% hit `66.92%` vs baseline `60.07%`, hit-rate lift `+6.86pp`, mean `-0.2231%` vs `-1.0044%`, mean lift `+0.7814pp`, after 0.20% cost `-0.4231%`. Research gate passed only as `candidate_relative_filter_only`.
- Recent-3m predicted-price comparison (`buy_date=2026-04-29..2026-07-30`, `events=13071`, targets 3/4/5%, lag0..lag5): actual T+1 open beat T-close predicted price on all target probabilities and mean returns. Actual open: 3% hit `73.13%`, 4% hit `67.87%`, 5% hit `63.23%`, 5% mean `-1.3693%`. T-close theoretical: 5% hit `62.48%`, mean `-1.5467%`. T-close limit-fillable: fill rate `93.22%`, 5% hit `60.95%`, mean `-1.8227%`.
- Recent-3m actual T+1 open averaged `-0.2274%` versus T close, median `-0.1508%`, p10 `-1.3688%`, p90 `+0.9075%`; lag split did not reverse the conclusion.

### Risks / Review Notes
- Do not promote any v1-v5 result to a buy rule or production/watchlist change. Best current interpretation: `prevweak + lag1..lag3 + next-day open` is a relative false-positive reducer/ranking annotation candidate, not a stable profit signal.
- Do not continue optimizing thresholds on the same `2025-07-29..2026-07-29` sample; it has already been used for discovery and diagnostics.
- Predicting T+1 open price is not currently useful unless a predictor can beat the naive T-close/zero-gap reference and improve execution decisions. The recent-3m test says actual T+1 open is already a better reference than T-close predicted price, but actual-open full lag0..lag5 mean is still negative before fees.
- If prediction research continues, focus on filtering bad signals / downside-risk / tradability bands rather than simply predicting T+1 open.
- Minute bars and all reference entries are research-only, not live execution/fill evidence. Fees, slippage, taxes, limit-up/down fillability, queue priority, partial fills, position sizing, and real exit mechanics remain incomplete.
- Next exact action: either wait for genuinely newer data after `2026-07-30` for true out-of-sample v6, or use the v5 result only as a human-review scanner ranking/risk annotation design candidate. If a new backtest is requested, pre-register fixed rules before running and use WSL -> Doris `.venv-doris/bin/python` -> local priority.
- Preserve `.runtime/baostock-intraday-cache-wsl-full-v1/` and avoid deleting/overwriting local complete minute cache.

## Relevant Historical Research Conclusions

### MKF selector and lag configuration
- Current chart-matched MKF rule uses the MFK4 green-zone right edge: prior tradable row has `momentum/inter/near <=20`; current red `momentum` and blue `near` cross from `<20` to `>=20`; current red/blue remain `<80`; existing hard gates remain applied.
- `lag0-lagX` means inclusive `{0..X}` over stock-tradable days;停牌/不可交易日不消耗 lag.
- Checked-in default in `yaml/edge_scout_v1.yaml` was previously verified as `lag0-lag2`; expanding to `lag0-lag5` should be explicit and validated before use.
- Prior config verification: 69 focused tests passed; default-vs-legacy selector rows identical when the new mkf config section was removed.

### Target / outcome methodology
- Valid user-confirmed target-timeout method for MKF lag/target profitability: target hit is based on T+1..T+N future high after entry; buy-day high is excluded.
- For fixed T+20 close fallback: if target is hit in T+1..T+20, realized return is fixed target%; otherwise use T+20 close / entry - 1.
- Old variable-horizon close-fallback ranking is forbidden unless explicitly reapproved; do not cite old results as valid conclusions.
- Existing broad research outputs include target grids under `docs/research/results/mkf/` and friction/drawdown study artifacts under `.runtime/` / docs; treat them as research indicators only, not executable P&L.

### Friction / position-size finding
- Prior 3手 + 三费 friction/drawdown grid found most cells negative to near-flat; only long-window high-target cases showed positive net with large drawdown, not a robust executable edge.
- Paper 2万资金 probe found risk-effective small positions net negative after fees; the only fee-positive large position broke the 10% drawdown constraint. Do not recommend real-money deployment from these studies.

## Repository / Governance
- Current branch at session start: `main`; recent committed checkpoint: `8690840 Record MKF release checkpoint`.
- Current authorized phase permits research signal generation, demo/paper workflows, PMKF/MKF dashboards, risk controls, audit logs, and read-only AI review.
- Keep `production_enabled: false` unless future explicit governance authorizes live trading.
- Live broker login, live orders, leverage, custody/settlement, unattended real-money execution, and committed real-money P&L remain prohibited.
- `PFrontStockData/` is adjusted research data only; never use it as live execution, live matching, or real-money fill evidence.
- Available validation environment priority: WSL first (`adminwsl@10.20.98.161`), Doris second (`chinaadmin@ts.dorisw.kdns.fr:56731` using `$HOME/NCN/.venv-doris/bin/python`), local last.
- Do not push, reset, clean, force-update, delete user work, or modify shared GitHub objects unless explicitly requested.
