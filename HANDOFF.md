# Reviewer Handoff

## Completed Task: Full local test run and diff check (2026-09-05)

### User Request
- User asked: “跑完整测试并检查 diff”.
- User clarified environment constraints: Doris cannot access AI and WSL is closed; do not use WSL/Doris for this AI validation path.

### Validation
- WSL check was attempted first per project priority before the clarification; it failed with SSH port reachable but connection closed during banner exchange.
- Doris Python check showed reachable `.venv-doris/bin/python`, but user clarified Doris cannot access AI, so subsequent validation stayed local.
- First local full pytest run failed due to outdated `tests/test_mkf_ai_review.py` assertions that still required banning BUY/SELL/WAIT/stop_loss/target_price/pnl and old prompt wording.
- Updated `tests/test_mkf_ai_review.py` to match current project rule: allow human research advice and only reject execution/live-broker/guarantee/leverage/real-money claims.
- Re-ran full local suite: `./.venv/bin/python -m pytest -q` -> 602 passed, 3 skipped in 67.08s.
- Ran `git diff --check` -> passed with no whitespace/conflict-marker output.

### Diff / Status Notes
- Tracked modified files now include `CLAUDE.md`, `HANDOFF.md`, `mkf.sh`, `remote-server.md`, `scripts/edge_scout_scan.sh`, `src/ashare_edge_scout/mkf_ai_review.py`, `tests/test_ai_provider_config.py`, `tests/test_main_script.py`, `tests/test_mkf_ai_review.py`, `tests/test_news_ai_review.py`, `yaml/ai_providers.yaml`, and `yaml/mkf_ai_review.yaml`.
- Untracked files include backup artifacts under `backups/`, AI4Finance experiment files, new eval/export/smoke scripts, new tests, `yaml/mkf_ai_review.pre-20260905-backup.yaml`, and `回测策略.md`.
- Important: `backups/modified-since-thursday-20260905_230606/` appears to be from the failed first backup attempt and should not be committed unless intentionally preserved; the successful backup is `backups/modified-since-thursday-20260905_230640/` and `.tar.gz`.

### Release Prep Scope
- Full local suite re-run for release prep: `./.venv/bin/python -m pytest -q` -> 602 passed, 3 skipped in 65.69s.
- Focused release suite: AI provider/news/MKF review/local-finance eval/LLM rotation/Web AI export/main-script tests -> 127 passed.
- `py_compile` passed for release candidate Python scripts, and `git diff --check` passed.
- Release candidate should include production/near-production AI provider/prompt/parser/test changes, MKF Web AI export entrypoint and tests, local-finance eval/smoke tools after boundary alignment, LLM rotation backtest provider-default fix, and the explicitly requested pre-change MKF prompt backup.
- Do not include `backups/` in the GitHub release commit; it is a local backup artifact.
- Do not include `experiments/ai4finance/` or `docs/research/ai4finance-production-integration-plan.md` in this release yet; grep found early sandbox prompt wording that still bans buy/sell/hold/target/stop terms, which conflicts with the current NCN no-live-trading-but-human-advice-allowed boundary and should be fixed in a separate AI4Finance sandbox cleanup.

### Next Exact Action
- Stage only the release candidate files, commit, push branch `ai4finance-production-integration`, then create a GitHub release/tag for this production-adjacent AI review/provider checkpoint.

## Completed Task: Normal AI features follow unified YAML provider default (2026-09-05)

### User Request
- User asked: “把正常功能都改成跟随统一 YAML 默认”.

### Changed Behavior
- Normal production/near-production AI paths now follow the top-level `provider` selected in `yaml/ai_providers.yaml`.
- MKF AI review and news AI review already used `yaml/ai_providers.yaml` through their business YAML `ai_config` fields.
- Updated `scripts/evaluate_mkf_ai_score_rotation_backtest.py` so its LLM lane no longer requires `local_finance`; it now builds the LLM client from the central YAML default provider.
- Preserved the old lane name `ts_local_finance_llm_no_news` for compatibility with existing CLI args/results, but the provider behind it now follows `yaml/ai_providers.yaml`.
- Updated the stage-note text to say the LLM lane uses the central YAML default instead of saying TS/local_finance only.

### Intentional Exceptions
- Left `scripts/evaluate_local_finance_models_on_mkf_candidates.py` hardcoded to `provider_override="local_finance"` because it is a local-finance model-pool comparison script, not a normal production default path.
- Left `scripts/smoke_local_finance_models.py` defaulting to `--provider local_finance` for the same reason.
- `scripts/smoke_ai_provider.py` remains generic and can follow YAML default when `--provider` is omitted.

### Tests / Validation
- Added `tests/test_mkf_ai_score_rotation_backtest.py::test_llm_backtest_client_follows_yaml_default_provider` to prove the LLM rotation backtest can use a non-`local_finance` YAML default provider.
- Ran `./.venv/bin/python -m pytest tests/test_ai_provider_config.py tests/test_news_ai_review.py tests/test_local_finance_mkf_model_eval.py tests/test_mkf_ai_score_rotation_backtest.py -q` -> 61 passed.
- Ran `./.venv/bin/python -m py_compile scripts/evaluate_mkf_ai_score_rotation_backtest.py src/ashare_edge_scout/mkf_ai_review.py scripts/evaluate_local_finance_models_on_mkf_candidates.py` -> passed.
- Grep for hardcoded `local_finance` defaults now only reports the two intentional local-finance-specific scripts.

### Remaining Notes
- Changing `yaml/ai_providers.yaml` top-level `provider` should now affect normal MKF/news/LLM rotation AI functionality.
- If a local-finance-specific benchmarking script should also become provider-generic later, rename or split it first to avoid confusing model-pool tests with production defaults.

## Review Task: AI default provider centralization status (2026-09-05)

### User Request
- User asked whether changing one YAML can adjust the default AI for all functions: “我需要修改以yaml文件所以功能的默认AI都需要调整。现在这个功能是否实现了”.

### Current Status
- Partially implemented, not fully global.
- Implemented for main production AI review configs: `yaml/mkf_ai_review.yaml` and `yaml/news_ai_review.yaml` both point to `yaml/ai_providers.yaml`, and `load_ai_provider_config()` selects either the YAML top-level `provider` or an explicit `provider_override`.
- Not fully implemented for all AI-related scripts: some scripts still pass `provider_override="local_finance"` or default CLI provider to `local_finance`, so changing only the top-level `provider` in `yaml/ai_providers.yaml` will not affect every tool.

### Known Exceptions
- `scripts/evaluate_local_finance_models_on_mkf_candidates.py` loads `yaml/ai_providers.yaml` but hardcodes `provider_override="local_finance"`; intended for local-finance model comparison, not global default behavior.
- `scripts/smoke_local_finance_models.py` defaults `--provider local_finance`; also intentionally local-finance-specific.
- `scripts/smoke_ai_provider.py` supports `--provider` override but otherwise can use the central YAML default.

### Recommendation
- If the desired product behavior is “edit `yaml/ai_providers.yaml` once and all normal AI features use that default,” keep production MKF/news review on central YAML and change generic scripts to omit hardcoded overrides by default.
- Keep explicitly local-finance benchmarking tools local-finance-specific, or rename/label them clearly so they are not confused with production default AI behavior.

## Completed Task: Unified AI provider config tests to local_finance default (2026-09-05)

### User Request
- User asked: “统一 provider 配置和测试”.

### Decision
- Kept production/default top-level provider as `local_finance` instead of silently switching to NVIDIA.
- Current default provider resolves to `http://ts.dorisw.kdns.fr:18090/v1`, model `Ornith-1.0-35B-4bit`, env `EDGE_SCOUT_LOCAL_AI_API_KEY`, timeout `120`.
- Kept newly added NVIDIA provider entries as available inventory, but they are not selected by default.

### Changed Files
- Updated `tests/test_ai_provider_config.py` so repository inventory and MKF/news shared-provider tests expect `local_finance` + `Ornith-1.0-35B-4bit`.
- Updated `tests/test_news_ai_review.py` so the repository news AI config default expectation matches `local_finance`.
- Did not change the top-level `provider` in `yaml/ai_providers.yaml` during this step.

### Validation
- `./.venv/bin/python -m pytest tests/test_ai_provider_config.py tests/test_news_ai_review.py tests/test_local_finance_mkf_model_eval.py -q` -> 53 passed.
- Direct config read confirmed provider/model/env/timeout: `local_finance`, `http://ts.dorisw.kdns.fr:18090/v1`, `Ornith-1.0-35B-4bit`, `EDGE_SCOUT_LOCAL_AI_API_KEY`, `120.0`.

### Remaining Notes
- If future work switches production/default provider to `nvidia_deepseek_v4_pro`, that should be a separate explicit provider migration with key/env validation and updated tests.

## Completed Task: MKF AI research-advice boundary optimization replay (2026-09-05)

### User Request
- User asked to continue AI testing/optimization and reminded: “你是不是又忘了，咱们的项目没有接入实盘”.
- Applied the standing rule: NCN is not connected to live trading, so human research advice must remain allowed; only claims of automatic execution/live broker/guaranteed return/leverage/real P&L should be blocked.

### Changed Files / Outputs
- Updated `src/ashare_edge_scout/mkf_ai_review.py`:
  - Replaced stale forbidden-action logic with execution-claim logic.
  - Fixed broken stale calls to `_contains_forbidden_action_text` that caused `NameError`.
  - Added negated-context handling so disclaimers like “非自动交易” are allowed instead of flagged.
- Updated untracked eval script `scripts/evaluate_local_finance_models_on_mkf_candidates.py` similarly:
  - `FORBIDDEN` now means execution/live-money/guarantee/leverage claim flags, not buy/sell/hold/wait advice.
  - Added `forbidden_matches()` with negated-context handling.
- Updated untracked test `tests/test_local_finance_mkf_model_eval.py`:
  - Human advice such as “买入观察，等待确认，参考止损和目标区间” is allowed.
  - “系统将自动下单” and escaped “保证收益” remain forbidden.
  - “非自动交易或收益承诺” disclaimer is allowed.
- Replay output: `output/回测结果/mkf-model-eval-ornith15-oq4e-research-advice-parserfix-20260905-231300/`.

### Validation
- `./.venv/bin/python -m pytest tests/test_local_finance_mkf_model_eval.py -q` -> 14 passed.
- `./.venv/bin/python -m py_compile src/ashare_edge_scout/mkf_ai_review.py scripts/evaluate_local_finance_models_on_mkf_candidates.py` -> passed.
- Replay completed 10/10 for `Ornith-1.5-35B-A3B-oQ4e-mtp` with fixed candidates and unified settings.
- Audit passed for replay: 10/10 JSON valid, 10/10 parser success, 10/10 contract pass, 0 truncation, 0 forbidden-output flags, 0 committee notes mismatches, mean 22.197s, state counts standard_research 9 / insufficient_evidence 1.
- Additional scan found no MA20/20日均线/20-day-cross terms, no unnegated execution/live-money/guarantee/leverage claims, and 2/10 outputs containing explicit human advice terms.

### MKF Selector Safety Check
- User asked whether MKF selection/scanning program had been modified.
- Verified current diff and Thursday-since log for `scripts/select_mkf_candidates.py`, `src/ashare_edge_scout/pmkf_mkf/candidates.py`, and `yaml/edge_scout_v1.yaml`: no changes.
- Only outer entry scripts `mkf.sh` and `scripts/edge_scout_scan.sh` are modified, adding a read-only `export-mkf-web-ai` command; selection conditions, candidate generation, `lag0-lag5` eligibility, and original MKF candidate sorting were not changed.

### Remaining Risks / Next Exact Action
- `yaml/ai_providers.yaml` still has unresolved provider direction: top-level provider remains `local_finance`, but some tests expect `nvidia_deepseek_v4_pro`; do not merge until this is reconciled.
- `tests/test_ai_provider_config.py` and `tests/test_news_ai_review.py` still fail due to provider expectation mismatch, unrelated to the MKF parser fix.
- If continuing optimization, review whether 2/10 explicit advice outputs are enough; if not, refine prompt to request a structured `human_review_plan` while keeping it clearly research-only and non-execution.

## Completed Task: Backup files touched since Thursday (2026-09-05)

### User Request
- User asked: “对周四之后修改的文件做一个备份。”

### Changed Files / Outputs
- Created backup directory: `backups/modified-since-thursday-20260905_230640/`.
- Created compressed archive: `backups/modified-since-thursday-20260905_230640.tar.gz`.
- Manifest: `backups/modified-since-thursday-20260905_230640/MANIFEST.txt`.
- File list copied count: 37 files.
- Backup scope: union of files touched by commits since `2026-09-03 00:00` plus current modified/untracked working-tree files.
- Excluded sensitive/broad runtime paths: `Key/**`, `.env`, `.env.*`, `.runtime/**`, `output/**`, `backups/**`, `.git/**`.

### Validation
- Backup command completed successfully and printed the backup directory, archive, manifest, and copied file count.
- First attempted zsh backup command failed due to zsh read-only variable name `status`; it was replaced by a bash-based command and did not produce the final backup.

### Next Exact Action
- If restoring or comparing, inspect `MANIFEST.txt`, then copy from `backups/modified-since-thursday-20260905_230640/files/` or apply `tracked-working-tree-changes.patch` selectively.
- Do not treat the backup as a production-ready snapshot; it intentionally preserves current in-progress changes, including the known MKF parser `NameError` state and provider-test mismatch recorded below.

## Review Task: Production-related diff audit (2026-09-05)

### User Request
- User asked: “审查生产相关 diff”.

### Scope Reviewed
- Production/near-production touched files: `mkf.sh`, `scripts/edge_scout_scan.sh`, `src/ashare_edge_scout/mkf_ai_review.py`, `yaml/ai_providers.yaml`, `yaml/mkf_ai_review.yaml`, plus related tests and operational docs.
- Also noted new untracked scripts/tests that affect MKF Web AI export and local-finance model evaluation.

### Findings
- High risk: `src/ashare_edge_scout/mkf_ai_review.py` is currently broken. The function was renamed to `_contains_forbidden_execution_text`, but `_scan_forbidden_payload` and `parse_ai_response` still call `_contains_forbidden_action_text`, causing `NameError` during MKF AI parsing.
- High risk: AI provider tests now expect `nvidia_deepseek_v4_pro`, while `yaml/ai_providers.yaml` still selects `provider: local_finance`. This creates failing repository tests and an unclear production provider direction.
- Medium risk: `yaml/ai_providers.yaml` changes the `local_finance` model from `Qwen3.8-27B-oQ4e-mtp` to `Ornith-1.0-35B-4bit` and adds enabled NVIDIA providers. The default provider remains `local_finance`, so the added NVIDIA providers do not take effect unless the top-level provider changes or an override is used.
- Medium risk: `yaml/mkf_ai_review.yaml` is intentionally in transition from over-restrictive trading-word bans to allowing human research advice while banning only execution/live-money/guarantee/leverage claims. It should not be treated as a final production prompt until parser/eval/tests are synchronized.
- Lower risk: `mkf.sh` and `scripts/edge_scout_scan.sh` add `export-mkf-web-ai`, a read-only Markdown export command. It appears isolated from SMC selection/watchlist/production logic, but depends on the new untracked `scripts/export_scan_csv_for_web_ai.py` being kept.
- Operational docs `CLAUDE.md` and `remote-server.md` changes are governance/process documentation, not runtime logic, and are directionally consistent with remote-validation rules.

### Validation Run
- Ran `./.venv/bin/python -m pytest tests/test_ai_provider_config.py tests/test_news_ai_review.py tests/test_local_finance_mkf_model_eval.py -q`.
- Result: 10 failed, 40 passed.
- Failure classes: provider expectation mismatch (`local_finance` vs `nvidia_deepseek_v4_pro`) and MKF parser `NameError` from stale `_contains_forbidden_action_text` call sites.

### Recommendation
- Do not run or merge current production-related diff as-is.
- First fix or revert the broken MKF parser call sites.
- Then choose one provider direction explicitly: keep production default on `local_finance` and revert tests to match, or intentionally switch top-level provider to `nvidia_deepseek_v4_pro` with key/env validation and user approval.
- Keep `yaml/mkf_ai_review.pre-20260905-backup.yaml` as the preserved good pre-change prompt.

## Paused Task: Backed up pre-change MKF AI prompt and paused contract rewrite (2026-09-05)

### User Request
- User asked to preserve the good AI prompt version from before today's changes: “今天修改前的AI提示词是一个很好的版本，请把那个版本备份一份出来”.

### Changed Files / Outputs
- Created `yaml/mkf_ai_review.pre-20260905-backup.yaml` from the committed baseline via `git show HEAD:yaml/mkf_ai_review.yaml`.
- Current working `yaml/mkf_ai_review.yaml` remains modified from the ongoing research-advice boundary rewrite.
- Current `src/ashare_edge_scout/mkf_ai_review.py` remains partially modified: forbidden constants/payload key were reframed to execution claims, and `_contains_forbidden_action_text` was replaced with `_contains_forbidden_execution_text`; downstream call sites still need cleanup.

### Validation
- Backup file creation was verified by `git status --short`, showing `?? yaml/mkf_ai_review.pre-20260905-backup.yaml`.
- No tests were run after this backup step.

### Next Exact Action
- If continuing the boundary rewrite, update remaining `mkf_ai_review.py` call sites from `_contains_forbidden_action_text` to `_contains_forbidden_execution_text`, update error messages, then adjust `scripts/evaluate_local_finance_models_on_mkf_candidates.py` and `tests/test_local_finance_mkf_model_eval.py` to allow human research advice while only flagging execution/live-money/guarantee/leverage claims.
- If the user wants to restore the backed-up prompt, compare `yaml/mkf_ai_review.pre-20260905-backup.yaml` with `yaml/mkf_ai_review.yaml` first, then explicitly replace only after confirmation.

### Risks / Do Not Repeat
- Do not ban useful human-review terms such as 买入观察/卖出风险/持有观察/等待确认/参考止盈止损/目标区间 merely because they resemble trading vocabulary; NCN is not connected to live trading.
- Do not change provider YAML based only on prompt-contract tests.

## Completed Task: Prompt hardening round 2 and user concern about over-restriction (2026-09-05)

### Changed Files / Outputs
- Modified `yaml/mkf_ai_review.yaml` again to hard-ban MA20/均线 terms and hard-ban `持有`/`等待`/`观望` wording.
- New replay output: `output/回测结果/mkf-model-eval-ornith15-oq4e-promptfix2-20260905-224242/`.

### Validation
- Focused test passed: `./.venv/bin/python -m pytest tests/test_local_finance_mkf_model_eval.py -q` -> 11 passed.
- Replay completed 10/10 for `Ornith-1.5-35B-A3B-oQ4e-mtp` with fixed candidates and unified settings.
- `--audit-run` passed: 10/10 JSON valid, 10/10 parser success, 10/10 contract pass, 0 truncation, 0 forbidden-output flags, 0 committee notes type mismatches, mean 20.421s, states standard_research 8 / insufficient_evidence 2.
- Additional scan found no MA20/均线/20-day-cross and no hard banned action terms in the second-hardened outputs.

### Important User Feedback
- User objected that banning terms like stop-profit/stop-loss/target/BUY/HOLD/WAIT and related advice removes the usefulness of the AI system: they want AI to provide judgmental advice to help decision-making.
- This is valid product feedback: the current hard-ban approach optimizes contract compliance but can over-restrict research judgment.

### Decision / Next Exact Action
- Do not continue tightening by simply banning more decision words. Reframe the contract instead: allow `research_action`/`human_review_plan`/`risk_plan` fields for judgmental human-review guidance, while still forbidding automatic execution, real broker actions, direct order instructions, or promises.
- A better prompt/schema should allow bounded research recommendations such as priority, avoid_for_now/risk_watch, confirmation conditions, invalidation risks, and review checkpoints, clearly labeled as human review guidance rather than live trading instruction.
- Do not change provider YAML until this product-level policy is clarified and replayed.


## Completed Task: Ornith oQ4e prompt-fix replay (2026-09-05)

### Changed Files / Outputs
- Modified `yaml/mkf_ai_review.yaml` prompt only; did not modify provider YAML.
- Added explicit constraints: MKF `cross_up_20` threshold is not MA20/20-day cross, no-news alone must not force `insufficient_evidence`, historical return fields should use `涨跌幅/return_pct` instead of `收益`, and `committee.*.notes` must be arrays.
- New replay output: `output/回测结果/mkf-model-eval-ornith15-oq4e-promptfix-20260905-223611/`.

### Validation
- Focused test `./.venv/bin/python -m pytest tests/test_local_finance_mkf_model_eval.py -q` passed: 11 passed.
- Broader focused run `tests/test_local_finance_mkf_model_eval.py tests/test_news_ai_review.py -q` had 1 existing config expectation failure: `news_ai_review.yaml` provider is `local_finance` while test expects `nvidia_deepseek_v4_pro`; unrelated to this `mkf_ai_review.yaml` prompt change.
- Replay completed 10/10 for `Ornith-1.5-35B-A3B-oQ4e-mtp` with same fixed candidates and unified settings. `--audit-run` passed, verifying manifest, prompt hashes, and decoded forbidden-term checks.
- Metrics after prompt fix: 10/10 JSON valid, 10/10 parser success, 7/10 contract pass, 0 truncation, 3 forbidden-output flags, 0 committee notes type mismatches, mean 21.574s, state counts: standard_research 7, insufficient_evidence 2, risk_attention 1.

### Findings
- Major improvement: notes mismatch fixed from 10/10 to 0/10; state distribution improved from all `insufficient_evidence` to useful split (`standard`/`insufficient`/`risk`).
- Regression/remaining issue: contract pass declined from 9/10 to 7/10 due to remaining forbidden terms. Key scan found forbidden terms in responses 03 (`持有`), 06 (`等待`), and 10 (`持有`).
- Prompt still leaks MA20/均线 terms: scan found `20日均线`/`均线` in most outputs despite the new threshold instruction. Need stronger user-message/schema-level constraints or postprocessor tests before switching provider.
- Do not treat prompt-fixed replay as final model-selection proof; it is a prompt contract iteration result, not accuracy/win-rate/return evidence.

### Next Exact Action
- Strengthen prompt again: ban the exact substrings `20日均线`, `均线`, `20-day cross`, `moving average`, and replace with `MKF指标阈值20`; ban `持有`/`等待` even in generic phrasing and require `继续人工复核` wording instead.
- Add a small regression test that frozen prompt includes these constraints and that contract scan catches MA20/均线 if desired.
- Replay the same 10 candidates for `Ornith-1.5-35B-A3B-oQ4e-mtp` after the second prompt hardening before considering provider YAML changes.


## Recommendation: MKF AI review adjustment after unified model evals (2026-09-05)

### Recommendation
- Do not tune temperature first; keep `temperature=0`, `seed=42`, `max_tokens=2048`, thinking disabled, and JSON response format for reproducible production-style replay.
- Prioritize prompt/schema fixes before provider YAML changes: explicitly state MKF `cross_up_20` is an indicator threshold crossing (not MA20/20-day cross), require `committee.*.notes` as arrays, and instruct models to use `涨跌幅/return_pct` wording instead of forbidden `收益` for historical return fields.
- Calibrate review-state rules so no-news alone does not collapse every technically reviewable candidate to `insufficient_evidence`; reserve `insufficient_evidence` for missing/conflicting/weak technical evidence, use `standard_research` for technically reviewable but no-news cases, and only allow `priority_research` if strict technical confirmation gates are met.
- Current best candidate for prompt/schema replay remains `Ornith-1.5-35B-A3B-oQ4e-mtp`; compare against `Qwen3.6` only after the same factual review and replay.

### Validation Target
- After changes, replay the exact same 10 frozen candidates first. Success target: 10/10 parser success, 0 truncation, 0 committee notes type mismatches, no MA20/20-day-cross semantic errors, lower forbidden-keyword noise, and a more informative state distribution without treating confidence as accuracy.


## Completed Task: Ornith oQ4e bounded factual review and latency-agnostic choice (2026-09-05)

### Scope
- Reviewed `Ornith-1.5-35B-A3B-oQ4e-mtp` outputs from `output/回测结果/mkf-model-eval-11-unified-20260905-204827/response-03-01..10.json` against frozen `inputs.json`.
- Checked MKF threshold wording, cross_date/signal_date, signal-day OHLC/shadow/volume/breakout claims, no-news context, and forbidden keyword source.

### Findings
- Strong mostly-correct pattern: all 10 responses correctly recognized MKF red/blue cross-up-20 eligibility, post_cross_lag within range, no-news/evidence unavailable context, and generally matched signal-day candle/volume/range indicators.
- Confirmed factual/semantic issues:
  - `response-03-01` (`sh.600025`) says “red/blue 20-day cross”; input means MKF indicator crossing threshold value 20, not a 20-day/MA20 cross.
  - `response-03-06` (`sh.603858`) says “equal 0.5 upper and 0.3889 lower shadows”; quoted values are not equal.
- Checked possible scanner flags: `sh.603665` correctly says long lower shadow and upper_shadow 0.17 with no long-upper flag; no contradiction. `sh.605377` mentions recent K-lines with long upper shadows, which is broadly supported by recent bars, but its single forbidden keyword hit is `收益` in a historical return description, requiring manual context review rather than automatic investment-advice conclusion.
- Shared contract issue remains: all 10 committee notes are strings, so production parser normalizes notes to empty arrays.

### Latency-Agnostic Choice
- If ignoring latency/wait time and using current completed evidence only, `Ornith-1.5-35B-A3B-oQ4e-mtp` remains the best practical candidate overall: 9/10 contract pass, 10/10 parser success, 1 forbidden-output flag, mostly correct facts, and only two bounded factual/semantic issues found in the 10-response review.
- `Qwen3.6` ties 9/10 contract pass but had 1 parser/forbidden-label failure and has not yet received the same factual review; it is a second candidate, not clearly superior.
- Do not treat this as accuracy/win-rate/return proof. No provider YAML change should be made before prompt/schema fixes and replay.


## Completed Task: Completed-model comparison after partial all-model evals (2026-09-05)

### Scope
- Compared only models with a full 10/10 response set from the fixed MKF candidate replay. Excluded unavailable/incomplete models: `Gemma-4-31B-JANG_4M-CRACK` and `Qwen3.8-27B-MTP-4bit`.
- Avoided double-counting repeated `Qwen3.8-27B-4bit` by using its standalone audited run (`output/回测结果/mkf-model-eval-qwen38-4bit-unified-20260905-220431/`).
- Used audited Qwen3.8 standalone/remaining directories where available; Ornith/Qwen3.6 metrics came from completed model blocks inside partial directory `output/回测结果/mkf-model-eval-11-unified-20260905-204827/`, which aborted before final manifest, so those blocks are usable as saved evidence but not final-manifest audited.

### Comparison Result
- Full 10/10 completed models compared: `Ornith-1.0-35B-4bit`, `Ornith-1.5-35B-A3B-MLX-4bit`, `Ornith-1.5-35B-A3B-oQ4e-mtp`, `Ornith-1.5-35B-A3B-oQ6e-mtp`, `Qwen3.6-27B-Claude-Opus-Reasoning-Distill-v2-abliterated-8bit-mlx`, `Qwen3.8-27B-4bit`, `Qwen3.8-27B-MTPLX-Optimized-Speed`, `Qwen3.8-27B-oQ4e-mtp`.
- Contract-pass leaders: `Ornith-1.5-35B-A3B-oQ4e-mtp` 9/10 and `Qwen3.6-27B-Claude-Opus-Reasoning-Distill-v2-abliterated-8bit-mlx` 9/10. `Qwen3.6` had 1 parser/forbidden-label failure; Ornith oQ4e had 1 forbidden-output flag and all 10 parsed.
- Next tier: `Ornith-1.5-35B-A3B-MLX-4bit` 5/10 and `Qwen3.8-27B-oQ4e-mtp` 5/10. Qwen3.8-oQ4e is the best among completed audited Qwen3.8 variants, but not best overall by contract pass.
- Slower models: Qwen3.6 mean ~71.756s; Qwen3.8 variants mean ~49-55s. Ornith variants mean ~16.6-19.4s.
- Shared issue: every completed model had 10/10 committee notes type mismatches; production parser drops string notes to empty arrays.

### Decision / Next Exact Action
- Do not change `yaml/ai_providers.yaml` from this table alone; metrics are contract/output compliance on one no-news 10-candidate replay, not accuracy/win-rate/return evidence.
- If choosing a next candidate for deeper manual factual review: review `Ornith-1.5-35B-A3B-oQ4e-mtp` first for speed + contract pass, then `Qwen3.6` for high contract pass but slower and one parser failure, then `Qwen3.8-oQ4e` as best audited Qwen3.8 variant.
- Next validation should be raw-response factual review: forbidden keyword context, threshold-20 vs MA20 semantics, cross_date vs signal_date, candle/shadow/volume claims, and notes schema.


## Completed Task: Qwen3.8 series unified retest (2026-09-05)

### Changed Files / Outputs
- `HANDOFF.md`: prepended this completion note.
- New completed output directories:
  - `output/回测结果/mkf-model-eval-qwen38-4bit-unified-20260905-220431/` for `Qwen3.8-27B-4bit` (10/10, manifest and audit complete).
  - `output/回测结果/mkf-model-eval-qwen38-remaining-unified-20260905-214617/` for `Qwen3.8-27B-MTPLX-Optimized-Speed` and `Qwen3.8-27B-oQ4e-mtp` (20/20, manifest and audit complete).
- Partial/failed evidence preserved:
  - `output/回测结果/mkf-model-eval-qwen38-unified-20260905-213214/` completed `Qwen3.8-27B-4bit` 10/10 then aborted at `Qwen3.8-27B-MTP-4bit` first candidate.
  - Prior 11-model partial run `output/回测结果/mkf-model-eval-11-unified-20260905-204827/` also aborted at `Qwen3.8-27B-MTP-4bit` first candidate.

### Validation
- All completed runs used the same 10 frozen MKF candidates from `output/edge_scout/mkf_candidate_selections/mkf-select-20260904_091715`, no-news context, production prompt construction, model-major sequential order, and unified settings: `temperature=0`, `seed=42`, `max_tokens=2048`, `enable_thinking=false`, `response_format={"type":"json_object"}`.
- `--audit-run` passed for both completed Qwen3.8 output directories; audit verified manifest hashes, prompt identity hashes, and decoded Chinese forbidden-term checks.
- Completed audited Qwen3.8 metrics:
  - `Qwen3.8-27B-4bit`: 10/10 JSON valid, 10/10 project parser success, 3/10 contract pass, 0 truncation, 7 forbidden-output flags, 10 committee-notes type mismatches, mean 50.352s, states standard2/insufficient8.
  - `Qwen3.8-27B-MTPLX-Optimized-Speed`: 10/10 JSON valid, 10/10 parser success, 4/10 contract pass, 0 truncation, 6 forbidden-output flags, 10 notes mismatches, mean 54.516s, states standard2/insufficient8.
  - `Qwen3.8-27B-oQ4e-mtp`: 10/10 JSON valid, 10/10 parser success, 5/10 contract pass, 0 truncation, 5 forbidden-output flags, 10 notes mismatches, mean 49.198s, states standard5/insufficient5.
- `Qwen3.8-27B-MTP-4bit` failed twice at first candidate (`sh.600025`) with `AIRequestError` before any content/finish_reason; treat as current service availability/load problem, not a model-quality score.

### Decision / Next Exact Action
- Do not call this a complete four-model Qwen3.8 comparison because `Qwen3.8-27B-MTP-4bit` is unavailable.
- Among the three completed Qwen3.8 variants, contract metrics are best for `Qwen3.8-27B-oQ4e-mtp` in this no-news 10-candidate replay, but this is still contract compliance only, not accuracy/win-rate/return evidence.
- Do not modify `yaml/ai_providers.yaml` or start portfolio/live trading actions from these metrics alone. Next useful action is bounded factual-evidence review of the completed raw responses, especially forbidden keyword context, threshold-20 vs MA20 semantics, and committee notes schema mismatch.


## Current Task: 11-model unified eval aborted after 61 responses (2026-09-05)

### Status
- User authorized skipping unavailable `Gemma-4-31B-JANG_4M-CRACK`; remaining 11-model run started with the same 10 frozen candidates and unified generation settings.
- Run directory: `output/回测结果/mkf-model-eval-11-unified-20260905-204827/`.
- The run completed 61/110 requests before transport failure. It is incomplete and must not be presented as a complete 11-model comparison.

### Completed Evidence
- Fully completed models: `Ornith-1.0-35B-4bit` (10), `Ornith-1.5-35B-A3B-MLX-4bit` (10), `Ornith-1.5-35B-A3B-oQ4e-mtp` (10), `Ornith-1.5-35B-A3B-oQ6e-mtp` (10), `Qwen3.6-27B-Claude-Opus-Reasoning-Distill-v2-abliterated-8bit-mlx` (10), and `Qwen3.8-27B-4bit` (10). `Qwen3.8-27B-MTP-4bit` has only its first request, which failed.
- Transport failure occurred at `Qwen3.8-27B-MTP-4bit` candidate 1 (`sh.600025`); saved row is `response-07-01.json` with `AIRequestError`, no server body persisted.
- Interim contract metrics are not final quality metrics. Completed model contract-pass counts in order: 4/10, 5/10, 9/10, 4/10, 9/10, 3/10. The first Qwen3.6 response failed project parsing because of a forbidden action label; its raw response remains saved.
- No manifest or audit result exists because the script aborted before finalization. Do not run `--audit-run` until a complete immutable run is available; the current directory is partial evidence only.

### Decision / Next Exact Action
- Preserve this partial directory and the earlier Gemma failure directory; do not overwrite either.
- Do not infer model ranking from this partial batch. A retry needs service recovery/clearance for the Qwen3.8 MTP model or a separately documented continuation design that preserves the exact model/case identity and does not falsely claim 110 fresh responses.
- No provider YAML change, live trading action, portfolio backtest, or destructive remote operation was performed.


## Current Task: 11-model unified eval excluding unavailable Gemma (2026-09-05)

### Status
- Per user instruction, skipped `Gemma-4-31B-JANG_4M-CRACK` after its server-side VLM load failure and started the remaining 11 models.
- New run: `output/回测结果/mkf-model-eval-11-unified-20260905-204827/`.
- Fixed inputs remain the same 10 MKF candidates from `mkf-select-20260904_091715`, with no-news context and frozen production prompts.
- Unified settings remain `temperature=0`, `seed=42`, `max_tokens=2048`, `enable_thinking=false`, JSON response format; model-major sequential order with no sleeps.

### Validation / Current State
- Background task `bkkjzzna3` is running. It reached `START model=Ornith-1.0-35B-4bit candidate=1/10 code=sh.600025`.
- No result or model-comparison conclusion is available yet. Preserve the prior failed Gemma directory and the old 40-response directory; do not overwrite either.

### Next Exact Action
- Await task completion. Then run `--audit-run` on the new 11-model directory, verify 110 response files, manifest/input hashes, and inspect summary/audit metrics before drawing any model conclusion.
- Do not change provider YAML or start portfolio/live trading actions from this eval.


## Current Task: Complete 12-model unified eval blocked by server-side Gemma load failure (2026-09-05)

### Status
- Started the requested complete 12-model unified replay with 10 frozen MKF candidates, model-major sequential order, no sleeps, `temperature=0`, `seed=42`, `max_tokens=2048`, JSON response format, and thinking disabled.
- New output directory: `output/回测结果/mkf-model-eval-all12-unified-20260905-204147/`.
- The first request only (`Gemma-4-31B-JANG_4M-CRACK`, `sh.600025`) failed with HTTP 409; no subsequent model was requested.

### Verified Cause / Evidence
- Direct diagnostic against `http://ts.dorisw.kdns.fr:18090/v1` reproduced the failure: server says the Gemma model is unavailable after a previous load failure, `VLM load failed`, with 2010 parameter mismatches including vision/language model tensors.
- `/v1/models` remains reachable and lists all 12 requested general models plus `MarkItDown`; endpoint availability does not prove every model can load.
- Saved run metadata confirms 12 models, 10 cases, and unified generation settings. The run contains one `response-01-01.json`, `summary.json`, and `inputs.json`; it has no complete manifest or audit result.

### Decision / Next Exact Action
- Do not report a 12-model comparison and do not rank models from this aborted run. Do not silently omit Gemma while claiming completion.
- Before retrying the full 12-model batch, confirm the service operator has cleared/reloaded the failed Gemma model or explicitly authorize a documented partial run excluding unavailable models. Preserve this failed directory as evidence; do not overwrite it.
- No YAML/provider change, live trading action, portfolio backtest, or destructive remote operation was performed.


## Completed Task: Ten-candidate four-model eval (2026-09-05)

### Changed Files
- `scripts/evaluate_local_finance_models_on_mkf_candidates.py`, `tests/test_local_finance_mkf_model_eval.py`, and `HANDOFF.md`.
- Results: `output/回测结果/mkf-model-eval-20260905-181415/` with frozen inputs, 40 raw responses, original manifest, corrected `audit-summary.json/csv`, and `evidence-review.json`.
- Production YAML, parser, prompts, scanner logic, and unrelated user changes intentionally unchanged. No broker/order/return simulation.

### Behavior / Logic Changes
- User's 10-20 candidate eval is complete: latest 10 candidates, signal date 2026-09-03, four models, 2048 max tokens, temperature 0, seed 42, thinking disabled, sequential model-major with no sleeps. No online/current news; frozen unavailable-news context.
- Original inference used raw-string keyword checks; Unicode escapes caused missed Chinese hits. Added decoded inspection and offline `--audit-run`, regraded all 40 without repeat inference or overwriting raw evidence. Use audit-summary, not original summary, for keyword/contract metrics.

### Validation
- Task `bhzq3117r` completed exit 0; monitor `bd8uymdev` stopped. 40/40 JSON objects parsed by project, all finish_reason=stop, zero truncations/errors. Original manifest hashes and all candidate/model/message-hash identities verified.
- Per model (Qwen / Ornith1.0 / Ornith1.5-Q6 / Ornith1.5-Q4): mean seconds 54.380 / 16.768 / 20.463 / 17.681; decoded keyword-hit outputs 4 / 6 / 6 / 1; string-notes mismatch outputs 10 / 10 / 10 / 10.
- State counts: Qwen standard5/insufficient5; Ornith1.0 standard7/insufficient2/risk1; Q6 standard1/insufficient9; Q4 insufficient10. No priority_research. Confidence is descriptive only.
- Local focused tests: 32 passed (11 eval + 21 production); git diff --check passed. Remote priority attempted: WSL SSH closed; Doris lacked pytest and exact selection snapshot; local orchestration with inference on Doris endpoint.

### Risks / Review Notes
- Decision: keep current configuration, no validated winning model. Qwen misclassified sh.603665 as long upper shadow despite flag=false/ratio0.17; Ornith1.0 repeatedly calls threshold20 a 20-day moving average; Q6 assigns signal-day volume ratio to prior day; Q4 contains a contradictory equal-shadow comparison.
- All 40 raw committee notes are strings and production parser drops them to empty lists. This is a shared prompt/parser compatibility issue, not evidence of empty model reasoning.
- Keyword hits include historical-return descriptions/non-action waiting; Q4 mostly English also biases Chinese keyword counts. They are NOT proven advice rates or accuracy scores. Latency includes model loading.
- Next exact action: separately fix/clarify MKF threshold20 vs MA20, cross_date vs signal_date, notes-array schema; validate against the same fixed input set before model-switch decisions. Do not launch LLM portfolio backtests or rerun this completed batch without a new task.


## Current Task: Read-only simplification review for local_finance MKF eval (2026-09-05)

### Changed Files
- `HANDOFF.md`: prepended this review entry per project handoff rule.
- No code or test files were modified; user requested read-only cleanup review only.

### Behavior / Logic Changes
- Reviewed only `scripts/evaluate_local_finance_models_on_mkf_candidates.py` and `tests/test_local_finance_mkf_model_eval.py` for simplification/cleanup candidates.
- Searched adjacent/shared utilities for duplicate functionality newly reimplemented in the target script.
- No tests, remote commands, model calls, backtests, or artifact retrieval were run.

### Validation
- Read-only inspection of the two scoped files plus adjacent utilities in `src/ashare_edge_scout/mkf_ai_review.py`, `src/ashare_edge_scout/ai_providers.py`, `src/ashare_edge_scout/operations.py`, `scripts/smoke_local_finance_models.py`, `scripts/evaluate_mkf_ai_score_rotation_backtest.py`, and `scripts/export_scan_csv_for_web_ai.py`.

### Risks / Review Notes
- Findings focus on actionable reuse/duplicate-maintenance costs around production prompt construction, no-news context construction, forbidden-action scanning, atomic JSON writing, checksum helpers, and response-content extraction.

## Current Task: Ten-candidate local_finance eval (2026-09-05)

### Changed Files
- `scripts/evaluate_local_finance_models_on_mkf_candidates.py`: freezes production-built prompts once, replays model-major sequentially without sleeps, applies 2048 tokens, saves every raw response/finish reason and summary, aborts on transport failure.
- `tests/test_local_finance_mkf_model_eval.py`: eight focused tests. Production code/YAML and unrelated user edits intentionally unchanged.

### Behavior / Logic Changes
- Fixed sample: all 10 candidates in `mkf-select-20260904_091715`, signal date 2026-09-03; same technical context through signal day and explicit unavailable news for all four models. No current news fetch.
- Models: Qwen3.8-27B-oQ4e-mtp, Ornith-1.0-35B-4bit, Ornith-1.5-35B-A3B-oQ6e-mtp, Ornith-1.5-35B-A3B-oQ4e-mtp. 40 logical reviews, one active request; transport may retry once on HTTP 400/422 without seed/response_format.
- Contract gate: raw JSON object + project parser + normal stop + no prohibited keyword hits. Keyword hits require manual review. Self-confidence/priority counts are NOT accuracy; no automatic recommended_model.

### Validation
- WSL check failed (SSH connected then closed). Doris Python 3.13.15 works, but pytest and the exact selection snapshot are absent. Local orchestration/tests fallback; actual inference remains Doris local_finance endpoint. No credential/output folder sync.
- Local focused pytest: 29 passed (8 new + 21 production). Initial test fixture used incorrect AIRequestError constructor, corrected and rerun. git diff --check passed.
- Prepare-only succeeded for all 10 technical contexts, zero model calls: `output/回测结果/mkf-model-eval-20260905-181301/inputs.json`.
- Full inference running as local background task `bhzq3117r`; output `output/回测结果/mkf-model-eval-20260905-181415/`; log `/private/tmp/claude-501/-Users-artx-Local-Git-Stock-NCN/5817cd11-6a67-4421-97cd-9d121ab6ef2a/tasks/bhzq3117r.output`. First request START verified (Qwen, sh.600025). Per-candidate log monitor `bd8uymdev` active. Next: await completion, verify manifest and 40 responses, inspect evidence. No live trading/return backtest/config change authorized by this eval.

### Risks / Review Notes
- Run launched with initial raw-text keyword detector. Inspection found Unicode-escaped Chinese bypasses it; script now includes decoded-JSON inspection and `--audit-run` to regrade saved immutable responses WITHOUT model calls. Do not trust original summary contract/keyword counts; use audit-summary.json after completion.
- Production parser silently drops string committee notes (expects arrays); report diagnostic count without changing production parser/prompt in this eval. All first 30 outputs have this mismatch.
- Current local validation: 32 passed (11 eval + 21 production); git diff --check passed. Next exact action after task completes: `./.venv/bin/python scripts/evaluate_local_finance_models_on_mkf_candidates.py --audit-run output/回测结果/mkf-model-eval-20260905-181415`, inspect fourth model, report verified evidence issues and keep config unchanged.
- Earlier one-case smoke ranking by self-confidence cannot establish Qwen superiority. All four passed corrected smoke, contrary to older stale only-Ornith claims.
- apply_patch is unavailable in this shell; used dedicated Write/Edit tools instead.

## Prior Task: Read-only MKF AI review API/fairness inspection (2026-09-05)

### Changed Files
- `HANDOFF.md`: prepended this read-only inspection entry only.
- No code, configs, tests, scripts, result CSVs, remote processes, broker/login/order paths, or LLM requests were modified or run.

### Behavior / Logic Changes
- User requested read-only inspection of `src/ashare_edge_scout/mkf_ai_review.py`, `src/ashare_edge_scout/ai_providers.py`, news context helpers, and `scripts/evaluate_local_finance_models_on_mkf_candidates.py`.
- Read `AGENTS.md` and newest `HANDOFF.md` first. Did not read `remote-server.md` because no remote sync/test/backtest/artifact retrieval was performed.
- Confirmed reusable production prompt construction is currently embedded in `mkf_ai_review.OpenAICompatibleClient.analyze`; there is no exported pure helper that builds the exact system/user messages without sending a request.
- Confirmed `run_mkf_ai_review` builds technical/news contexts inside each run and therefore model-comparison scripts rerunning it per model do not freeze context once across models.

### Validation
- Read-only file inspection only; no local tests, remote commands, or LLM/provider requests were run.
- Key interfaces inspected: `parse_ai_response`, `load_mkf_ai_config`, `build_ai_client`, `run_mkf_ai_review`, `build_mkf_news_context`, `load_ai_provider_config`, shared `build_ai_client`, and model-eval script functions.

### Risks / Review Notes
- `scripts/evaluate_local_finance_models_on_mkf_candidates.py` bypasses shared credential precedence (`api_key_env`, `api_key_file_env`, `key_file`) by requiring and directly reading `key_file`; this can disagree with production config behavior.
- Injected per-model clients cause `run_mkf_ai_review` summary fields such as `ai_model` to come from YAML provider config rather than the injected model, so per-model eval metadata can be misleading even when rows contain the actual model.
- Fairness risk: per-model runs can have different freshly fetched/cache-hit news contexts, time-dependent cache statuses, and repeated output directories; a fair benchmark should pre-freeze selection, technical contexts, news contexts, prompt hash, candidate order, and generation parameters once, then replay identical messages per model.

## Current Task: TS/local_finance model catalog checked (2026-09-05)

### Changed Files
- `HANDOFF.md`: prepended this model-catalog analysis entry only.
- No code, YAML config, tests, scanner logic, result CSVs, remote processes, broker/login/order paths, or live-trading behavior were modified.

### Behavior / Logic Changes
- User asked to access `http://ts.dorisw.kdns.fr:18080` using `Key/ts.key`, search available models, and analyze which model best fits NCN.
- Read `AGENTS.md`, latest `HANDOFF.md`, and `remote-server.md` first per project rules.
- Used the key only inside local commands and did not print or expose it.
- `http://ts.dorisw.kdns.fr:18080` returned HTTP 503 for common model endpoints; repository config points local_finance to `http://ts.dorisw.kdns.fr:18090/v1`, where `/models` succeeded.

### Validation
- Queried `http://ts.dorisw.kdns.fr:18090/v1/models`; available model IDs included `Ornith-1.0-35B-4bit`, `Ornith-1.5-35B-A3B-oQ4e-mtp`, `Ornith-1.5-35B-A3B-oQ6e-mtp`, `Qwen3.8-27B-oQ4e-mtp`, `Qwen3.8-27B-MTP-4bit`, `Qwen3.8-27B-MTPLX-Optimized-Speed`, `Qwen3.6-27B-Claude-Opus-Reasoning-Distill-v2-abliterated-8bit-mlx`, Gemma/gpt-oss variants, and `MarkItDown`.
- Read `yaml/ai_providers.yaml`; current YAML selects `local_finance` with model `Ornith-1.0-35B-4bit` at `http://ts.dorisw.kdns.fr:18090/v1`.
- Read `tests/test_ai_provider_config.py`; current tests still expect selected provider `nvidia_deepseek_v4_pro` and local model `Qwen3.8-27B-oQ4e-mtp`, so tests and YAML appear out of sync.
- Added `scripts/smoke_local_finance_models.py`, a bounded local_finance multi-model JSON smoke/eval script using the existing `OpenAICompatibleClient` and `mkf_ai_review.parse_ai_response`.
- Validation passed: `./.venv/bin/python -m py_compile scripts/smoke_local_finance_models.py`.
- Ran the smoke/eval against `Ornith-1.5-35B-A3B-oQ6e-mtp`, `Ornith-1.5-35B-A3B-oQ4e-mtp`, `Ornith-1.0-35B-4bit`, and `Qwen3.8-27B-oQ4e-mtp`; result JSON was saved under `output/回测结果/model-smoke-eval-*/local_finance_model_smoke.json`.
- First smoke/eval outcome: only `Ornith-1.0-35B-4bit` returned project-parseable JSON (`standard_research`, confidence `0.78`, no forbidden terms); the other three failed with `AI response contains no JSON object`.
- User clarified resources are limited and each model run needs a 5-minute interval. Updated `scripts/smoke_local_finance_models.py` with `--delay-between-models-seconds` and incremental result writing after each model.
- Validation passed again: `./.venv/bin/python -m py_compile scripts/smoke_local_finance_models.py`.
- User requested stopping the 5-minute interval task because the visible model panel looked idle. Stopped background task `bu73pajy9`.
- Restarted background sequential smoke/eval task `bxbpkh5y8` with models `Ornith-1.5-35B-A3B-oQ6e-mtp`, `Ornith-1.5-35B-A3B-oQ4e-mtp`, `Ornith-1.0-35B-4bit`, `Qwen3.8-27B-oQ4e-mtp`, `--delay-between-models-seconds 180`; output path is `output/回测结果/model-smoke-eval-sequential-*/local_finance_model_smoke.json`.
- Task `bxbpkh5y8` was stopped before completion after the user said to restart again. New background task `b3favx01t` ran the same four-model sequential smoke/eval with `--delay-between-models-seconds 180`.
- User provided omlx logs showing `Ornith-1.5-35B-A3B-oQ6e-mtp` was active but finished with `finish_reason=length`, `max_tokens=512`; the earlier parse failure was likely output truncation rather than an idle model.
- Stopped task `b3favx01t` and restarted as task `bumjqwwxz` with the same model order, `--delay-between-models-seconds 180`, and larger `--max-tokens 2048`.
- Task `bumjqwwxz` was stopped before completion after the user said to restart again. New task `by2lx4ljy` ran the same sequential smoke/eval with `--delay-between-models-seconds 180` and `--max-tokens 2048`.
- Interim result from `by2lx4ljy`: `Ornith-1.5-35B-A3B-oQ6e-mtp` completed successfully with `finish_reason=stop` behavior, project-parseable JSON, `standard_research`, confidence `0.58`, no forbidden terms. User then requested fixing the truncation issue and restarting; task `by2lx4ljy` was stopped.
- Fixed the truncation-prone default by changing `scripts/smoke_local_finance_models.py` default `--max-tokens` from `512` to `2048`.
- Validation passed: `./.venv/bin/python -m py_compile scripts/smoke_local_finance_models.py`.
- New background task `b5kinaapf` ran the same four-model sequential smoke/eval with `--delay-between-models-seconds 180`; it relied on the corrected `2048` default output limit.
- User changed the flow: no waiting is needed between models; run one model, then immediately test the next model sequentially. Stopped task `b5kinaapf`.
- New background task `bgvxl7a3i` ran the same four-model sequential smoke/eval without `--delay-between-models-seconds`, so the default delay was `0` and models ran back-to-back.
- Task `bgvxl7a3i` completed with exit code `0`. Final ranked result: `Qwen3.8-27B-oQ4e-mtp` passed JSON/parser checks with no forbidden terms, `priority_research`, confidence `0.85`, elapsed `75.421s`; `Ornith-1.0-35B-4bit` passed with `standard_research`, confidence `0.78`, elapsed `12.933s`; `Ornith-1.5-35B-A3B-oQ6e-mtp` passed with `standard_research`, confidence `0.58`, elapsed `8.797s`; `Ornith-1.5-35B-A3B-oQ4e-mtp` passed with `standard_research`, confidence `0.58`, elapsed `13.524s`.
- Recommendation after this one-case smoke/eval: do not treat it as final model selection; `Qwen3.8-27B-oQ4e-mtp` is now the best candidate to test next because it produced the strongest structured review, but it is slow and needs a multi-case eval before changing `yaml/ai_providers.yaml`.

### Risks / Review Notes
- Updated recommendation after smoke/eval: do not switch from `Ornith-1.0-35B-4bit` yet; it is the only tested local_finance candidate that passed the current MKF AI JSON parser contract.
- The higher-quality-looking catalog candidates may need model-specific thinking/template options before they can satisfy strict JSON output; evaluate that separately before any config change.
- Do not change `yaml/ai_providers.yaml` or tests until deciding whether to keep current local model, align tests to current YAML, or add per-model compatibility options.
- Do not start TS/local_finance LLM backtests or live trading actions from this model smoke alone.

## Current Task: Explain MKF AI review workflow (2026-09-05)

### Changed Files
- `HANDOFF.md`: prepended this explanatory-task entry only.
- No code, configs, result CSVs, scanner logic, remote processes, broker/login/order paths, or live-trading behavior were modified.

### Behavior / Logic Changes
- User asked to continue explaining the MKF AI review workflow after clarifying OHLCV, local_score, confidence, and review_state ordering.
- Explanation should stay in research/paper-simulation terms and avoid presenting AI output as buy/sell/hold, return probability, or live-trading instruction.

### Validation
- Existing inspected files for this explanation: `futu.md`, `yaml/edge_scout_v1.yaml`, `src/ashare_edge_scout/pmkf_mkf/candidates.py`, and `src/ashare_edge_scout/mkf_ai_review.py`.
- No new validation command was required for the explanation.

### Risks / Review Notes
- Keep emphasizing that AI confidence is a model self-assessed review confidence, not a win-rate/profit probability.
- Keep distinguishing raw MKF candidate ordering from AI-reviewed ordering.

## Current Task: MKF AI-score overall coordination scheme analysis (2026-09-05)

### Changed Files
- `HANDOFF.md`: updated this methodology/readout entry.
- No code, result CSV, scanner logic, YAML config, remote process, broker/login/order path, or live-trading behavior was modified.

### Behavior / Logic Changes
- User clarified they want the overall coordination scheme: how MKF scanning, AI score, threshold entry/hold logic, dynamic replacement, cost-aware paper simulation, and validation should fit together.
- Analysis should describe the scheme as a staged offline research/paper-simulation workflow, not a final profitable strategy or live trading rule.

### Validation
- No new backtest or data extraction was run for this analysis request.
- Latest validated result available locally: `output/回测结果/mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1/`, with `grid_summary.csv` verified at `15498` rows and manifest hashes matched after Doris sync.

### Risks / Review Notes
- Current validated grid used deterministic no-news/no-LLM lane `deterministic_local_score_x10`; do not overstate it as proof that real LLM review improves outcomes.
- Best `ashare` result had positive sample total return but low closed-trade win rate and small trade count, so it is a research lead requiring stability/tail-risk review.
- If continuing, next exact action is to turn the overall scheme into a pre-registered validation ladder: deterministic baseline, LLM no-news overlay, archived point-in-time news overlay if available, then paper-forward monitoring.

## Current Task: Doris MKF AI-score threshold-grid result validated and synced (2026-09-05)

### Changed Files
- `HANDOFF.md`: updated the Doris continuation entry with completed validation/sync status.
- `output/回测结果/mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1/`: synced from Doris to local after remote validation.
- No code, tests, scanner logic, YAML config, remote process, broker/login/order path, or live-trading behavior was modified.

### Behavior / Logic Changes
- User asked to continue after checking whether `simulated` progress appeared for the Doris deterministic MKF AI-score threshold-grid run.
- Read `AGENTS.md`, latest `HANDOFF.md`, and `remote-server.md` before remote validation, per project instructions.
- Validated Doris run `mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1`; original PID `56062` was no longer active, but final result files were present.
- Method remains deterministic no-news/no-LLM lane `deterministic_local_score_x10`, start `2025-09-01`, `initial_capital=10000`, entry/hold threshold grids `60..100` with `hold<=entry`, `max_positions=1,2,3`, `replacement_gap=0,3,5`, `cost_modes=none,ashare`, `workers=16`.

### Validation
- Remote log `/Users/chinaadmin/NCN/.runtime/mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1.log` contains `simulated` progress through `simulated 15250/15498 combos`.
- Remote output directory contained `manifest.json`, `summary.json`, `grid_summary.csv`, `trades.csv`, `daily_equity.csv`, `daily_scores_top.csv`, and `阶段项目说明.md`.
- Remote `grid_summary.csv` row count was `15498`, matching expected `861 threshold pairs × 3 max_positions × 3 replacement_gap × 2 cost_modes`.
- Remote key hashes: `grid_summary.csv` SHA-256 `53cf2a07a49d029b08a974bf525147c36ad2258c0dbe13d5d75f4ec0888410f4`, `summary.json` SHA-256 `f919b05e727e915f5a16fa0155c1987067debb006484d6353c2fe7780a28eb42`; `manifest.json` local file hash was `0ca8eea6599284faca769974078de8b640de85aa2c1c991fe1827b398cff2908`.
- Local rsync of only this result directory completed; local manifest validation passed for every listed file size and SHA-256, and local `grid_summary.csv` still had `15498` rows.
- Best `ashare` row by total return: `deterministic_local_score_x10|entry84|hold64|pos1|gap0|ashare`, final equity `11232.8178362`, total return `12.32817836%`, max drawdown `-4.92111282%`, trade_count `32`, closed_trade_win_rate `37.5%`, cost_paid `235.2881578`, avg_hold_days `1.1875`, turnover_ratio `28.81581973`.
- Best no-cost row by total return: `deterministic_local_score_x10|entry80|hold63|pos1|gap0|none`, final equity `11575.854184`, total return `15.75854184%`, max drawdown `-13.86632392%`, trade_count `120`, closed_trade_win_rate `43.333333%`, cost_paid `0`, avg_hold_days `1.98333333`, turnover_ratio `107.56784844`.

### Risks / Review Notes
- These are offline deterministic paper/simulation results only; do not present them as real-money profitability, live execution evidence, investment advice, or a production trading rule.
- Best rows have low closed-trade win rates despite positive total return over this sample; they should be treated as research leads requiring stability/tail-risk review, not as final scanner logic.
- TS/local_finance `Ornith-1.0-35B-4bit` no-news LLM lane remains not run; do not start it until the user explicitly confirms the next methodology step.

## Current Task: MKF AI-score threshold-grid deterministic Doris migration (2026-09-04)

### Changed Files
- `scripts/evaluate_mkf_ai_score_rotation_backtest.py`: current working version uses threshold grids (`entry_threshold_grid=60..100`, `hold_threshold_grid=60..100`, filtered `hold<=entry`) and `ProcessPoolExecutor` (with `_init_sim_worker` initializer) for deterministic combo simulation. Combo simulation was switched from `ThreadPoolExecutor` to processes because threads were GIL-bound to ~1 core; candidate construction still uses `ProcessPoolExecutor`.
- `tests/test_mkf_ai_score_rotation_backtest.py`: focused tests cover next tradable open, LLM score mapping, A-share fees, next-day exits, lot-size cash skip, replacement-gap boundary, and threshold summary fields.
- `HANDOFF.md`: updated this active Doris continuation entry with the process-based full run.

### Behavior / Logic Changes
- User requested migrating the latest stable thread-mode deterministic full-grid run to Doris because the session was about to close.
- Historical replay remains no-news: do not fetch or use current/7-day news caches for 2025 dates; deterministic lane is `deterministic_local_score_x10` only.
- WSL full grid using multiprocessing initializer failed with `_pickle.UnpicklingError: pickle data was truncated`; combo simulation was switched to threads while candidate construction still uses processes.
- First Doris run `mkf-ai-score-threshold-grid-thread-det-doris-20260904-1` (PID `54166`) was intentionally stopped by the user at `simulated 250/15498 combos`; no manifest or result files were produced.
- Second Doris run `mkf-ai-score-threshold-grid-thread-det-doris-20260904-2` (PID `54883`) was left running but was effectively single-core: the combo simulation used `ThreadPoolExecutor`, which is GIL-bound (~116% CPU). The user asked to restart with 4 processes.
- User requested stopping prior progress and restarting using all Doris resources. All active NCN `evaluate_mkf_ai_score_rotation_backtest.py` main processes were stopped before relaunch; `$HOME/NCN/.venv-doris` multiprocessing child leftovers from the prior process run were also cleared.
- Current Doris run: `mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1`, PID `56062`, detached (PPID `1`), log `/Users/chinaadmin/NCN/.runtime/mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1.log`, output `/Users/chinaadmin/NCN/output/回测结果/mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1`.
- Run parameters: `deterministic_local_score_x10`, no news, no LLM, start `2025-09-01`, `initial_capital=10000`, entry/hold threshold grids `60..100` (861 valid pairs), `max_positions=1,2,3`, `replacement_gap=0,3,5`, `cost_modes=none,ashare`, `workers=16`.

### Validation
- Local validation after combo-process change passed: `./.venv/bin/python -m py_compile scripts/evaluate_mkf_ai_score_rotation_backtest.py` and focused pytest with `7 passed`.
- WSL thread smoke passed for the earlier mode: manifest present, 12 rows, `combo_tasks=12`, `combo_parallel=True`, `combo_workers_used=4`.
- Doris pre-launch check passed: host `chinaadmins-Mac-Studio.local`, `.venv-doris/bin/python` Python `3.13.15`, `PFrontStockData` count `7375`, memory free `59%` at launch.
- Doris script md5 `756fc08bf25bfef5781ba5fa1065200c` matches local updated version.
- Current 16-worker run verified alive at elapsed `00:16`: main PID `56062`, PPID `1`, STAT `RN`, about `%CPU 100.2`, `%MEM 2.2`; log had not emitted progress yet and combo worker children had not appeared at that early check.
- Doris focused pytest did not run because `.venv-doris` lacks pytest (`No module named pytest`). Do not use system `python3` as a substitute.

### Risks / Review Notes
- Do not copy `Key/`, `.env*`, `.runtime/`, broad `output/`, or `config/research_watchlist.json` between machines. Sync back only the completed Doris run directory after manifest validation.
- Expected deterministic full-grid rows: 861 valid threshold pairs × 3 max_positions × 3 replacement_gap × 2 cost_modes = 15498 rows.
- Prior Doris run reached `250/15498 combos` shortly after candidate construction; full combo phase ETA is expected to be several hours.
- Next exact action: monitor PID `56062` / log / manifest for `mkf-ai-score-threshold-grid-proc-det-doris-20260904-16w-1`; on completion validate `summary.json`, `grid_summary.csv`, `manifest.json` hashes and row count, extract best `ashare` and `none` rows, then rsync only that result directory to local `output/回测结果/`.
- WSL thread full run `mkf-ai-score-threshold-grid-thread-det-wsl-20260904-1` may still be running; check later if needed, but do not kill remote work unless explicitly authorized or clearly necessary.
- TS/local_finance `Ornith-1.0-35B-4bit` no-news LLM lane has not been run; do not start it until deterministic Doris result is complete and the user confirms the next step.

## Current Task: MKF AI-score threshold-grid parallel deterministic WSL run (2026-09-04)

### Changed Files
- `scripts/evaluate_mkf_ai_score_rotation_backtest.py`: added `--entry-threshold-grid` and `--hold-threshold-grid`; combo IDs and `grid_summary.csv`/`trades.csv`/`daily_equity.csv` include entry/hold thresholds; deterministic combo simulation now uses `ProcessPoolExecutor` across threshold/position/gap/cost combos.
- `tests/test_mkf_ai_score_rotation_backtest.py`: updated `ComboState` construction for threshold fields and added coverage that summaries preserve entry/hold thresholds.
- `HANDOFF.md`: updated this active-run entry.

### Behavior / Logic Changes
- Deterministic threshold search is grid-capable: entry thresholds and hold thresholds can be scanned independently, with invalid `hold_threshold > entry_threshold` combinations filtered out.
- The earlier full WSL run `mkf-ai-score-threshold-grid-det-wsl-20260904-1` was stopped after user approved the recommendation because its combo simulation phase was serial and used only about one CPU core on a 20-core WSL host.
- New full WSL run is deterministic only: `deterministic_local_score_x10`, no news, no LLM, start `2025-09-01`, `initial_capital=10000`, `entry_threshold_grid=60..100`, `hold_threshold_grid=60..100 filtered to hold<=entry`, `max_positions=1,2,3`, `replacement_gap=0,3,5`, `cost_modes=none,ashare`, `workers=16`.
- New run id: `mkf-ai-score-threshold-grid-parallel-det-wsl-20260904-1`; remote log: `/home/adminwsl/NCN/.runtime/mkf-ai-score-threshold-grid-parallel-det-wsl-20260904-1.log`; remote output: `/home/adminwsl/NCN/output/回测结果/mkf-ai-score-threshold-grid-parallel-det-wsl-20260904-1/`.

### Validation
- Local validation passed after parallelization: `./.venv/bin/python -m py_compile scripts/evaluate_mkf_ai_score_rotation_backtest.py` and `./.venv/bin/python -m pytest tests/test_mkf_ai_score_rotation_backtest.py -q` with 7 tests passed.
- WSL validation passed after sync: `./scripts/remote_test_env.sh check`, `./scripts/remote_test_env.sh sync-code`, WSL focused pytest with 7 tests passed.
- WSL parallel smoke run passed for short range `2025-09-01..2025-09-10`; it emitted `simulated 5/40 combos` through `simulated 40/40 combos` and wrote output to `mkf-ai-score-threshold-parallel-smoke-wsl-20260904-1`.
- New full WSL run was verified actually running as PID `15204`; `.runtime/mkf-ai-score-threshold-grid-parallel-det-wsl-20260904-1.log` exists. A completion waiter is active for manifest generation or PID exit.

### Risks / Review Notes
- The latest SSH/nohup wrapper still did not write the pid file, but remote process PID `15204` was verified separately; do not rely on the pid file.
- Expected summary rows if completed: 861 valid threshold pairs × 3 max_positions × 3 replacement_gap × 2 cost_modes = 15498 rows for the deterministic lane.
- Next exact action: check WSL process/log, wait for completion, validate `summary.json`/`manifest.json`, extract best `ashare` and `none` rows, sync only this result directory locally, then report results. TS/Ornith LLM no-news lane remains not run.


## Current Task: MKF AI-score dynamic rotation deterministic WSL result (2026-09-04)

### Changed Files
- `scripts/evaluate_mkf_ai_score_rotation_backtest.py`: added the research/paper dynamic AI-score portfolio rotation backtest script.
- `tests/test_mkf_ai_score_rotation_backtest.py`: added focused tests for next-tradable-open execution, LLM state score mapping, fees, pending exits, lot constraints, and replacement-gap behavior.
- `yaml/ai_providers.yaml`: final local_finance/TS model is `Ornith-1.0-35B-4bit`; nvidia is not the active provider.
- `output/回测结果/mkf-ai-score-rotation-det-wsl-20260904-1053/`: synced deterministic WSL result folder locally.
- `HANDOFF.md`: prepended this continuation entry.

### Behavior / Logic Changes
- User-confirmed protocol: start `2025-09-01`, ignore news because historical message context is not point-in-time verifiable, and run a dynamic portfolio rule with entry threshold 65 and hold threshold 60.
- Completed only the deterministic lane: `deterministic_local_score_x10`, where `ai_score = local_score * 10`; no LLM/news was used for this result.
- WSL full run used `.venv/bin/python`, `--workers 16`, `max_positions=1,2,3`, `replacement_gap=0,3,5`, `cost_modes=none,ashare`, `initial_capital=10000`, run id `mkf-ai-score-rotation-det-wsl-20260904-1053`.

### Validation
- Local focused validation passed earlier: `./.venv/bin/python -m py_compile scripts/evaluate_mkf_ai_score_rotation_backtest.py` and `./.venv/bin/python -m pytest tests/test_mkf_ai_score_rotation_backtest.py -q` with 6 tests passed.
- WSL focused tests also passed earlier with 6 tests passed.
- WSL process has ended and output files exist: `summary.json`, `grid_summary.csv`, `trades.csv`, `daily_equity.csv`, `daily_scores_top.csv`, `manifest.json`, and `阶段项目说明.md`.
- Remote and local manifest validation passed for the synced result folder; local `grid_summary.csv` has 18 rows.
- Best `ashare` cost-mode row by total return is `deterministic_local_score_x10|pos1|gap0|ashare`: final equity 6328.48311112, total return -36.71516889%, max drawdown -47.74984969%, trade_count 419, cost_paid 2800.18428088.
- Best no-cost row by total return is `deterministic_local_score_x10|pos1|gap3|none`: final equity 9562.701136, total return -4.37298864%, max drawdown -33.86298864%, trade_count 417.

### Risks / Review Notes
- The deterministic local-score lane is negative across the best reported cost/no-cost cases; with A-share costs, turnover and 5 CNY commission floor dominate a 10,000 CNY account.
- Do not report this as a profitable rule, real-money recommendation, or live trading signal; it is offline research/paper simulation only.
- TS/local_finance LLM no-news lane has not been fully run yet. If continuing, first run a capped full-period `--llm-top-per-day 1` estimate using `Ornith-1.0-35B-4bit`, then decide whether to expand to top 3 or 5.
- Avoid reusing the earlier faulty nohup wrapper pattern that produced `${pid}: ambiguous redirect`; use a simpler quoted SSH/nohup command for the next detached WSL run.


## Current Task: WSL AI-score portfolio backtest news-context decision (2026-09-04)

### Changed Files
- `HANDOFF.md`: prepended this methodology note.
- No script, production code, scanner logic, YAML config, prompt, watchlist, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked whether a WSL backtest of the AI-score dynamic replacement portfolio should ignore news context and whether historical news can still be fetched.
- Current project news context config/code was checked: `yaml/mkf_news_context.yaml` uses `NEWS_DAYS: 7`, `CACHE_RETENTION_DAYS: 7`, and sources Google News RSS / Eastmoney stock news / Eastmoney announcements; `src/ashare_edge_scout/mkf_news_context.py` names cache files by current `today` and validates cache payload date against that same day.

### Validation
- Read `remote-server.md` before discussing WSL backtest work.
- Read `yaml/mkf_news_context.yaml` and `src/ashare_edge_scout/mkf_news_context.py` news-context implementation.
- No WSL command or backtest was launched yet.

### Risks / Review Notes
- For historical replay from 2025-09-01, current online news fetch is not a reliable point-in-time historical news source; using today's fetched news for past dates would introduce look-ahead/time-travel bias.
- Unless timestamped historical daily news/AI-review artifacts exist for each scan date, the first WSL backtest should use price/indicator/scanner/available saved AI-score data only and treat news as missing or run a separate live-forward/paper overlay.
- If news must be included, next exact action is to inventory whether daily `news_contexts.json`/`reviews.json` scan artifacts were archived since 2025-09-01 before defining the final backtest protocol.

## Current Task: AI-score dynamic replacement portfolio question (2026-09-04)

### Changed Files
- `HANDOFF.md`: prepended this clarification/readout entry.
- No script, production code, scanner logic, YAML config, prompt, watchlist, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User corrected the prior fixed single-combination interpretation and described a dynamic daily workflow from 2025-09-01: scan each day, select stocks whose AI recommendation value is above 65%, start with 10,000 capital, automatically replace based on AI analysis score, keep held stocks above 60%, exit held stocks below 60%.
- This is a strategy/backtest-methodology question and should be treated as a portfolio-style paper/simulation design, not live trading or guaranteed return guidance.

### Validation
- No new backtest was run for this question yet.
- Existing prior first-touch and low-stop result tables do not directly answer this dynamic AI-score replacement workflow because they evaluate fixed MKF entry/exit combinations, not daily AI-score calibrated portfolio replacement.

### Risks / Review Notes
- Key unresolved specification: how many concurrent positions / allocation rule should 10,000 capital use when multiple stocks pass AI >=65%, and how replacement is ranked.
- Main methodological risk is treating AI score percentages as calibrated return probabilities without validating calibration, turnover, transaction costs, and out-of-sample behavior.
- Next exact action should be to define a fixed paper-backtest protocol for the dynamic AI-score portfolio before implementing or judging profitability.

## Current Task: MKF highest-return mechanical combination readout (2026-09-04)

### Changed Files
- `HANDOFF.md`: prepended this read-only readout entry.
- No script, production code, scanner logic, YAML config, prompt, watchlist, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked for the highest-return “无脑操作” combination.
- Readout used existing Doris result tables only: main-board/`production_gate_mask` low-stop feature-filter v3 summary and all-A fixed-candidate pressure-test full-period table.
- Definition used for this answer: fixed mechanical entry/exit rule, no manual judgement, no new post-hoc filter mining, ranked by historical `mean_realized_return` under the timeout-open first-touch口径.
- Exit method remains: buy at next tradable open after lag signal close; scan `T+1..T+N-1`; same-day stop+target counts stop first; unresolved exits at `T+N open`.

### Validation
- Re-read `AGENTS.md` and latest `HANDOFF.md` before the readout.
- Used local project virtualenv `./.venv/bin/python` to sort `output/回测结果/20260903_215942/mkf_low_stop_feature_filters_summary_fast_20210101_20260902_doris_v3.csv` and `output/回测结果/20260904_082341/mkf_all_a_low_stop_fixed_candidates_full_period.csv` by `mean_realized_return`.
- Main-board highest historical realized mean: `4% target / 12% stop / lag7 / T+19 / entry_gap_le_0pct&range20_pos_35_to_85`, n=4114, target hit 68.8867%, Wilson lower 67.4550%, stop hit 13.1988%, timeout 17.9144%, timeout-open mean -3.7873%, mean realized return 0.4931%.
- All-A fixed-candidate highest historical realized mean: same rule `4% target / 12% stop / lag7 / T+19 / entry_gap_le_0pct&range20_pos_35_to_85`, n=14591, target hit 66.5479%, Wilson lower 65.7780%, stop hit 13.1794%, timeout 20.2728%, timeout-open mean -3.4787%, mean realized return 0.3752%.
- More conservative mechanical alternative remains `3% target / 12% stop / lag7 / T+19 / entry_gap_le_0pct&range20_pos_35_to_85`: main-board mean 0.3027%, all-A mean 0.1541%, with higher hit rate but weak annual stability.

### Risks / Review Notes
- The highest-return mechanical row is not a 70% hit-rate/stability winner and stop-hit rate is slightly above 12%; it is a sample-period return maximum, not the most robust rule.
- Annual stability remains the main blocker: prior diagnostics showed weak years and negative mean-return years, so the rule is offline research/paper-only and must not be presented as a real-money execution rule, investment advice, or return promise.
- Do not write this into scanner or production logic without fixed-rule board/liquidity/year/tail-risk validation.

## Current Task: MKF T+10 low-stop combination readout (2026-09-04)

### Changed Files
- `HANDOFF.md`: prepended this read-only T+10 extraction entry.
- No script, production code, scanner logic, YAML config, prompt, watchlist, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked which combination is most suitable if timeout horizon is fixed to `T+10`.
- Readout used existing Doris v3 low-stop feature-filter summary at `output/回测结果/20260903_215942/mkf_low_stop_feature_filters_summary_fast_20210101_20260902_doris_v3.csv`.
- Important boundary: this is the prior main-board/`production_gate_mask` low-stop feature-filter grid, not the later all-A fixed-candidate pressure test. The all-A pressure test only covered fixed `T+13/T+19` candidates and does not answer all-A `T+10`.
- Exit method remains timeout-open first-touch: scan `T+1..T+N-1`; same-day stop+target counts stop first; unresolved exits at `T+N open`.

### Validation
- Used local project virtualenv `./.venv/bin/python` to extract `horizon == T+10` rows from the existing 99900-row v3 summary CSV.
- For `T+10`, no combination reached target hit >=70% or Wilson lower >=70% while also keeping stop hit <=12% and mean realized return positive.
- Best high-confidence/low-shakeout tradeoff: `3% target / 12% stop / lag7 / T+10 / entry_gap_le_0pct&range20_pos_35_to_85`, n=4142, target hit 66.5620%, Wilson lower 65.1105%, stop hit 7.0256%, timeout 26.4124%, timeout-open mean -3.5551%, mean realized return 0.2148%.
- Closest `10%` stop alternative: `3% target / 10% stop / lag2 / T+10 / volume_ratio_1p0_to_2p5&range20_pos_35_to_85`, n=2157, target hit 67.3621%, Wilson lower 65.3539%, stop hit 11.7756%, timeout 20.8623%, timeout-open mean -3.1256%, mean realized return 0.1912%.
- Mean-return maximum at T+10 is `4% target / 12% stop / lag7 / T+10 / entry_gap_le_0pct&range20_pos_35_to_85`, n=4142, target hit 58.2327%, Wilson lower 56.7238%, stop hit 7.4843%, timeout 34.2830%, timeout-open mean -3.0782%, mean realized return 0.3759%; this is lower-win-rate and not suitable if the priority is hit rate.

### Risks / Review Notes
- Direct recommendation for `T+10` under low-stop/high-hit preference: use `3% target / 12% stop / lag7 / entry_gap_le_0pct&range20_pos_35_to_85`; do not call it a 70% strategy because it only reaches 66.56% hit rate.
- If the user wants the all-A universe answer for `T+10`, run a separate all-A fixed-candidate pressure test that includes `T+10`; do not infer it from the all-A `T+13/T+19` result.
- These outputs are offline research only, not live trading, real fill evidence, investment advice, or a real-money execution rule.


## Current Task: MKF all-A low-stop fixed-candidate pressure test (2026-09-04)

### Changed Files
- `HANDOFF.md`: updated the pending all-A pressure-test entry to completed.
- `.runtime/evaluate_mkf_all_a_low_stop_fixed_candidates.py`: temporary ignored research script for fixed-rule pressure testing across all `PFrontStockData/*.parquet` files.
- `output/回测结果/20260904_082341/`: final user-facing deliverable folder with fetched Doris JSON/CSV, derived full-period CSV, derived annual-stability CSV, and `阶段项目说明.md`.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked to run the all-A pressure test with ST/untradable/low-liquidity exclusions and annual layering.
- Universe: all `PFrontStockData/*.parquet` files, not just main-board `PREFIXES`; signal row must be non-ST, `tradestatus == 1`, close > 0, and signal-date ADV20 >= 50,000,000 CNY.
- This is a fixed-candidate pressure test, not a new filter search. It evaluates prior candidates: primary `3% target / 12% stop / lag7 / T+19 / entry_gap_le_0pct&range20_pos_35_to_85`, shorter `3% target / 12% stop / lag6 / T+13 / close_above_ma60&volume_ratio_0p8_to_2p0`, plus liquid-gate-only baselines for the same lags/horizons.
- Exit method remains timeout-open first-touch: scan `T+1..T+N-1`; same-day stop+target counts stop first; unresolved exits at `T+N open`.
- Targets/stops evaluated: 3%/4% targets and 10%/12% stops; full-period min_n=1000 and annual_min_n=80.

### Validation
- Read `AGENTS.md`, latest `HANDOFF.md`, `回测策略.md`, and `remote-server.md` before fetching Doris results.
- Local syntax validation used project virtualenv before the run: `./.venv/bin/python -m py_compile .runtime/evaluate_mkf_all_a_low_stop_fixed_candidates.py`.
- Synced only `.runtime/evaluate_mkf_all_a_low_stop_fixed_candidates.py` to Doris `NCN/.runtime/` and ran detached with run_id `mkf-all-a-low-stop-fixed-20210101-20260902-doris-20260903-224135`, workers=12, `.venv-doris/bin/python`, min_adv20=50000000.
- Doris run completed: log showed `processed 7375/7375 codes`; remote JSON/CSV were fetched into `output/回测结果/20260904_082341/`.
- Validation with local `./.venv/bin/python`: schema `ncn_mkf_all_a_low_stop_fixed_candidates_v1`; sample has 7375 files, 102169 parent crosses, 134971 lag events, 134046 mature and 925 partial events; summary CSV has 112 rows, including 16 full-period rows and 96 annual rows.
- Main full-period result: primary `entry_gap_le_0pct&range20_pos_35_to_85 / lag7 / T+19`, 3% target and 12% stop, n=14591, target hit 72.9422%, Wilson lower 72.2154%, stop hit 11.8361%, timeout 15.2217%, timeout-open mean -4.0324%, realized mean 0.1541%.
- Same primary row with 10% stop: target hit 71.4756%, Wilson lower 70.7373%, but stop hit 16.1401%, so it fails the low-stop shakeout requirement.
- 4% target remains unsupported for 10%/12% stops: primary 4%/12% has target hit 66.5479%, Wilson lower 65.7780%, stop hit 13.1794%.
- Annual stability failed for primary 3%/12%: min yearly target hit 66.0434%, min yearly Wilson 64.2266%, max yearly stop hit 17.5019%, min yearly realized mean -1.0234%, and 4 negative mean-return years.

### Risks / Review Notes
- Direct answer: all-A pressure testing preserves a full-period 3%/12% signal for the primary filtered candidate, but it does not pass annual stability; keep it as research candidate only, not a scanner/production rule.
- 10% stop still appears too tight for the 70% version because the 3% primary row has stop hit 16.14%; lowering stop further would likely increase shakeouts.
- Do not add more post-hoc filters merely to fix the weak annual years. If continuing, pre-register board/prefix and ADV20-tier diagnostics, then reject the rule if weak-year instability remains.
- These outputs are offline research only, not live trading, real fill evidence, investment advice, or a real-money execution rule.


## Current Task: MKF low-stop pre-entry feature subset search (2026-09-03)

### Changed Files
- `HANDOFF.md`: prepended this completed Doris result entry.
- `.runtime/evaluate_mkf_low_stop_feature_filters_fast.py`: temporary ignored research script; optimizes low-stop feature-filter study by precomputing each target/stop/lag/horizon exit outcome once, then vector-aggregating pre-entry filter masks.
- `output/回测结果/20260903_215942/`: final v3 user-facing deliverable folder with JSON, full summary CSV, candidate CSV, annual diagnostic CSV, derived key-point CSVs, and `阶段项目说明.md`.
- Earlier intermediate output folders `output/回测结果/20260903_214516/` and `output/回测结果/20260903_215250/` were created during v1/v2 debugging; final answer should use `20260903_215942`.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked to find MKF subsets where `10%~12%` stops are less likely to shake out positions, while still counting timeout exits at `T+N open`.
- Scope: 2021-01-01 through 2026-09-02, targets 3%/4%, stops 10%/12%, lag0..lag7, T+2..T+20, MKF parent signal plus `production_gate_mask`.
- Entry/exit method: buy at next stock-tradable open after lag signal close; scan only `T+1..T+N-1` for first-touch stop/target; same-day stop+target counts as stop first; unresolved samples exit at `T+N open`.
- Filter search uses only pre-entry/signal-date/entry-open features such as entry gap, lag runup, MA context, volume ratio, liquidity, volatility, range position, upper shadow, and signal-day return. It does not use future drawdown, future highs/lows, or realized future outcomes for filtering.
- Full-sample candidate threshold is `n >= 1000`; annual diagnostic threshold is `annual_min_n = 80`.

### Validation
- Read `AGENTS.md`, latest `HANDOFF.md`, and `remote-server.md`; WSL check failed with TCP connect then SSH banner close, so Doris was used per priority. Doris check passed: host `chinaadmins-Mac-Studio.local`, 16 logical CPUs, memory free 94%, `.venv-doris/bin/python` Python 3.13.15.
- Local syntax validation used project virtualenv: `./.venv/bin/python -m py_compile .runtime/evaluate_mkf_low_stop_feature_filters_fast.py`.
- Doris v3 command: `cd "$HOME/NCN" && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src .venv-doris/bin/python .runtime/evaluate_mkf_low_stop_feature_filters_fast.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 12 --min-n 1000 --annual-min-n 80 --output .runtime/mkf-low-stop-feature-filters-fast-20210101-20260902-doris-v3.json --summary-csv .runtime/mkf-low-stop-feature-filters-fast-20210101-20260902-doris-v3.csv --candidates-csv .runtime/mkf-low-stop-feature-filter-candidates-fast-20210101-20260902-doris-v3.csv --annual-csv .runtime/mkf-low-stop-feature-filter-annual-fast-20210101-20260902-doris-v3.csv` -> processed 3197/3197 codes and evaluated 608/608 exit combos.
- Final v3 JSON schema is `ncn_mkf_low_stop_pre_entry_filters_fast_v1`; sample: 3197 codes, 56379 parent crosses, 155234 lag events, 154223 mature and 1011 partial events. Row counts: 99900 summary rows, 14 candidate rows, 66 annual rows.
- Strict gate result: no 10% stop combination met target hit >=70%, stop hit <=12%, and positive mean realized return; no 4% target combination met the same gate for 10% or 12% stops.
- 3% target with 12% stop did meet the full-sample strict gate. Best full-sample row: `entry_gap_le_0pct&range20_pos_35_to_85`, lag7, T+19, n=4114, target hit 75.3038%, Wilson lower 73.9628%, stop hit 11.7647%, timeout 12.9315%, timeout-open mean -4.2121%, mean realized return 0.3027%.
- Shortest Wilson-lower-70 full-sample row for 3%/12%: `close_above_ma60&volume_ratio_0p8_to_2p0`, lag6, T+13, n=1613, target hit 72.3497%, Wilson lower 70.1157%, stop hit 10.6014%, timeout 17.0490%, timeout-open mean -4.3784%, mean realized return 0.1518%.
- Annual diagnostics are weak: the best 3%/12% row has min yearly hit 68.3702%, min yearly Wilson 64.8934%, max yearly stop hit 18.2708%, min yearly realized mean -0.3396%, and 4 negative mean-return years; the shortest Wilson row has min yearly hit 64.7651%, max yearly stop hit 20.4651%, min yearly realized mean -0.8697%, and 4 negative years.

### Risks / Review Notes
- Direct answer: `10%` stop is not supported for a 70% high-confidence version; `12%` stop has a promising full-sample 3% target subset but fails annual stability, so it is a research candidate only, not a scanner/production rule.
- Recommended candidate to carry forward for fixed-rule validation: `3% target / 12% stop / lag7 / T+19 / entry_gap_le_0pct&range20_pos_35_to_85`. Secondary shorter-hold candidate: `3% target / 12% stop / lag6 / T+13 / close_above_ma60&volume_ratio_0p8_to_2p0`.
- Do not add more post-hoc filters to force a positive conclusion. Next exact action, if continuing, is fixed-rule annual/sample-out/tail-risk confirmation and reject the rule if weak years remain unacceptable.
- These outputs are offline research only, not live trading, real fill evidence, investment advice, or a real-money execution rule.


## Current Task: MKF first-touch timeout-open stop5..20 backtest (2026-09-03)

### Changed Files
- `HANDOFF.md`: replaced the prior clarification entry with this completed WSL result entry.
- `.runtime/evaluate_mkf_first_touch_timeout_open.py`: temporary ignored research script; adds future `open` columns and evaluates first-touch exits with timeout sold at `T+N open`.
- `output/回测结果/20260903_145805/`: user-facing deliverable folder with detailed CSV/JSON, key point CSV, best-by-stop CSV, top20 CSV, and `阶段项目说明.md`.
- Memory updated outside the repo: `feedback_project_virtualenv.md` and `MEMORY.md` now record that local NCN Python commands must use `./.venv/bin/python`, not system `python3`.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User confirmed timeout-open口径: for horizon `T+N`, scan first-touch stop/target only from `T+1..T+N-1`; unresolved samples sell at `T+N open`.
- Same prior daily OHLC tie rule remains: if a scan-day bar touches both stop and target, count stop-loss first.
- Scope: 2021-01-01 through 2026-09-02, target 3%/4%, stop thresholds 5%..20%, lag0..lag7, T+1..T+20, MKF parent signal and production gate from `回测策略.md`.
- Return model changed from timeout `0` to realized timeout-open return: target first `+target_pct`, stop first `-stop_pct`, timeout `T+N open / entry_open - 1`.
- `T+1` is a strict-boundary row with no pre-timeout high/low scan; all samples exit at `T+1 open`. Reports therefore also include a practical “排除 T+1 后” best-first-touch view.

### Validation
- Read `AGENTS.md`, latest `HANDOFF.md`, and `remote-server.md` before WSL work. WSL check passed; memory/Python check showed 19Gi total, 18Gi available, `.venv/bin/python` Python 3.14.4.
- Synced only `.runtime/evaluate_mkf_first_touch_timeout_open.py` to WSL and ran: `cd /home/adminwsl/NCN && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python .runtime/evaluate_mkf_first_touch_timeout_open.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 8 --output .runtime/mkf-first-touch-timeout-open-stop5-20-target-20210101-20260902-wsl.json --summary-csv .runtime/mkf-first-touch-timeout-open-stop5-20-target-20210101-20260902-wsl.csv --sweet-csv .runtime/mkf-first-touch-timeout-open-stop5-20-target-sweet-spots-20210101-20260902-wsl.csv` -> processed 3197/3197 codes.
- First WSL run completed computation but failed JSON write because `avg_first_touch_day` carried NaN in T+1 rows; fixed by converting non-finite floats to JSON `null`, then reran successfully.
- Copied WSL outputs directly into `output/回测结果/20260903_145805/` and used local project virtualenv `./.venv/bin/python` for validation/derived tables; detailed CSV has 5120 data rows, JSON schema is `ncn_mkf_first_touch_timeout_open_v1`, sample has 3197 codes, 56379 parent crosses, 155234 lag events.
- Key result, strict global best realized mean: 3% target -> `stop=5%, lag1, T+1`, n=19962, all samples timeout at `T+1 open`, mean return 0.1492%; this is a boundary open-to-open row, not a first-touch sweet spot.
- Key result, excluding T+1 pure-open-exit rows: 3% target -> `stop=20%, lag7, T+18`, n=18624, target hit 73.8348%, Wilson lower 73.1987%, stop hit 3.5492%, timeout 22.6160%, timeout-open mean -6.4866%, realized mean 0.0382%; 4% target -> `stop=20%, lag7, T+18`, n=18624, target hit 66.9351%, Wilson lower 66.2560%, stop hit 3.9948%, timeout 29.0700%, timeout-open mean -5.8242%, realized mean 0.1853%.
- 3% target reaches point-estimate 70% at `stop=20%, lag7, T+14`, hit 70.2001%, Wilson lower 69.5403%, realized mean -0.0464%; Wilson lower 70% at `stop=20%, lag7, T+15`, hit 71.1831%, Wilson lower 70.5293%, realized mean 0.0126%.
- 4% target still has no `stop5..20%` timeout-open first-touch combination reaching point-estimate or Wilson-lower 70% target-hit rate.

### Risks / Review Notes
- Follow-up combination analysis from the completed CSV favors two explicit choices: conservative/high-confidence 3% target -> `target=3%, stop=20%, lag7, T+15` because Wilson lower is above 70% and realized mean is slightly positive; return-max within tested grid -> `target=4%, stop=20%, lag7, T+18` because realized mean is highest, but target hit rate is only 66.9351% and does not meet 70%.
- Timeout-open materially lowers the earlier timeout=0 simplified return for long windows because unresolved samples often have negative `T+N open` returns; do not compare those two mean-return columns as the same metric.
- The 3% global `T+1` best is a boundary artifact of the confirmed strict timing, not evidence that a stop/target rule works; prefer the “排除 T+1 后” table for practical first-touch interpretation.
- `stop=20%` remains the grid boundary. Do not infer it is the true optimal stop without pre-registering a wider grid plus annual/out-of-sample/tail-risk checks.
- These outputs are offline research only, not live trading, real fill evidence, investment advice, or a real-money execution rule.


## Current Task: MKF first-touch stop5..20 backtest (2026-09-03)

### Changed Files
- `HANDOFF.md`: prepended this completed WSL result entry.
- `.runtime/evaluate_mkf_first_touch_stop_target.py`: temporary ignored research script updated so `STOP_PCTS = range(5, 21)` for this run.
- `.runtime/mkf-first-touch-stop5-20-target-20210101-20260902-wsl.json`: copied WSL JSON output back locally; runtime artifact is ignored.
- `output/回测结果/20260903_144315/`: user-facing deliverable folder with detailed CSV/JSON, sweet-spot CSVs, and `阶段项目说明.md`.
- Local duplicate `.runtime` CSV copies for this run were removed after copying into the timestamped output folder.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User asked to rerun first-touch stop/target backtest with stop thresholds 5% through 20%.
- Same confirmed first-touch口径 as the previous run: if a sellable daily bar has both `low <= stop_price` and `high >= target_price`, count stop-loss first.
- Scope: 2021-01-01 through 2026-09-02, target 3%/4%, stop thresholds 5%..20%, lag0..lag7, T+1..T+20, MKF parent signal and production gate from `回测策略.md`.
- Return model remains `+target_pct` if target first, `-stop_pct` if stop first, `0` if timeout by horizon.

### Validation
- Read latest `HANDOFF.md`, `AGENTS.md`, `remote-server.md`, and reused the already-read `回测策略.md` first-touch context before running.
- WSL memory/Python check before run: 19Gi total, 18Gi available, `.venv/bin/python` Python 3.14.4.
- Synced `.runtime/evaluate_mkf_first_touch_stop_target.py` to WSL and ran: `cd /home/adminwsl/NCN && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python .runtime/evaluate_mkf_first_touch_stop_target.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 8 --output .runtime/mkf-first-touch-stop5-20-target-20210101-20260902-wsl.json --summary-csv .runtime/mkf-first-touch-stop5-20-target-20210101-20260902-wsl.csv --sweet-csv .runtime/mkf-first-touch-stop5-20-target-sweet-spots-20210101-20260902-wsl.csv` -> processed 3197/3197 codes.
- Copied WSL outputs locally, generated `output/回测结果/20260903_144315/`, validated complete detailed CSV has 5120 data rows plus header, and JSON parses with `python -m json.tool`.
- Key result, best mean first-touch simplified return: 3% target -> `stop=20%, lag7, T+11`, n=18727, target hit 67.8806%, Wilson lower 67.2082%, stop hit 1.9918%, timeout 30.1276%, mean return 1.6381%; 4% target -> `stop=20%, lag7, T+12`, n=18727, target hit 61.4300%, Wilson lower 60.7306%, stop hit 2.4777%, timeout 36.0923%, mean return 1.9617%.
- 3% target reaches point-estimate 70% at `stop=20%, lag7, T+13`, hit 70.2553%, Wilson lower 69.5964%, mean return 1.6014%; Wilson lower 70% at `stop=20%, lag7, T+14`, hit 71.1901%, Wilson lower 70.5365%, mean return 1.5878%.
- 4% target still has no `stop5..20%` first-touch combination reaching point-estimate or Wilson-lower 70% target-hit rate.

### Risks / Review Notes
- `stop=20%` is the edge of the requested wider grid; do not infer the true optimum is exactly 20% without pre-registering a further wider grid and adding tail-risk/stability analysis.
- Wider stops improve simplified mean return in this grid mainly by avoiding stop-outs and allowing target hits, but they create larger single-trade loss exposure that this mean-only summary can understate.
- If using these results for candidate filtering, next exact action is not to widen indefinitely; choose practical stops for annual/out-of-sample stability and drawdown/tail-risk review before any scanner behavior change.


## Current Task: MKF first-touch stop/target backtest (2026-09-03)

### Changed Files
- `HANDOFF.md`: replaced the prior clarification entry with this completed WSL result entry.
- `.runtime/evaluate_mkf_first_touch_stop_target.py`: temporary ignored research script; recomputes MKF lag events with future high/low and evaluates first-touch stop/target outcomes.
- `.runtime/mkf-first-touch-stop-target-20210101-20260902-wsl.json`: copied WSL JSON output back locally; runtime artifact is ignored.
- `output/回测结果/20260903_142654/`: user-facing deliverable folder with detailed CSV/JSON, sweet-spot CSVs, and `阶段项目说明.md`.
- Local duplicate `.runtime` CSV copies for this run were removed after copying into the timestamped output folder.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User confirmed same-day target+stop tie handling: if a sellable daily bar has both `low <= stop_price` and `high >= target_price`, count stop-loss first.
- Scope: 2021-01-01 through 2026-09-02, target 3%/4%, stop thresholds 0%..10%, lag0..lag7, T+1..T+20, MKF parent signal and production gate from `回测策略.md`.
- First-touch definition: scan T+1..T+N stock-tradable days after entry; target price is `entry_open*(1+target_pct/100)`, stop price is `entry_open*(1-stop_pct/100)`; return model is `+target_pct` if target first, `-stop_pct` if stop first, `0` if timeout by horizon.
- This is offline daily-OHLC first-touch research; no fees, slippage, tax, sizing, fillability, limit-up/down execution constraints, or real P&L is modeled.

### Validation
- Read latest `HANDOFF.md`, `AGENTS.md`, `回测策略.md`, and `remote-server.md` before running.
- WSL memory/Python check before run: 19Gi total, 18Gi available, `.venv/bin/python` Python 3.14.4.
- Synced `.runtime/evaluate_mkf_first_touch_stop_target.py` to WSL and ran: `cd /home/adminwsl/NCN && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python .runtime/evaluate_mkf_first_touch_stop_target.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 8 --output .runtime/mkf-first-touch-stop-target-20210101-20260902-wsl.json --summary-csv .runtime/mkf-first-touch-stop-target-20210101-20260902-wsl.csv --sweet-csv .runtime/mkf-first-touch-stop-target-sweet-spots-20210101-20260902-wsl.csv` -> processed 3197/3197 codes.
- Copied WSL outputs locally, generated `output/回测结果/20260903_142654/`, validated complete detailed CSV has 3520 data rows plus header, and JSON parses with `python -m json.tool`.
- Key result, best mean first-touch simplified return: 3% target -> `stop=10%, lag0, T+3`, n=20163, target hit 44.1998%, Wilson lower 43.5154%, stop hit 3.8834%, timeout 51.9169%, mean return 0.9377%; 4% target -> `stop=10%, lag7, T+4`, n=18734, target hit 41.1231%, Wilson lower 40.4204%, stop hit 6.4268%, timeout 52.4501%, mean return 1.0022%.
- 3% target can reach point-estimate 70% only at longer horizon: `stop=10%, lag7, T+17`, hit 70.4231%, Wilson lower 69.7635%, mean return 0.2578%; Wilson lower 70% requires `stop=10%, lag7, T+18`, hit 70.8494%, Wilson lower 70.1925%, mean return 0.2333%.
- 4% target has no `stop0..10%` first-touch combination reaching point-estimate or Wilson-lower 70% target-hit rate.

### Risks / Review Notes
- `stop=10%` is the edge of the requested grid; do not infer the true optimum is exactly 10% without testing wider stops and out-of-sample stability.
- Tight stops increase same-day/touch stop-outs under daily bars; same-day stop-first is conservative but may understate target-first cases in real intraday paths.
- The first-touch results show the prior conditional MAE table should not be used directly as a stop-loss rule; conditioning on paths with low realized MAE is materially different from executing a stop.
- If these results are used for candidate filtering, next exact action is to pre-register one or two practical stop/target/horizon candidates and run annual/stability plus sample-out checks before changing scanner behavior.


## Current Task: MKF drawdown-threshold conditional target-hit table (2026-09-03)

### Changed Files
- `HANDOFF.md`: replaced the prior clarification entry with this completed WSL result entry.
- `.runtime/evaluate_mkf_drawdown_threshold_hit_rate.py`: temporary ignored research script; recomputes MKF lag events with future high/low to evaluate drawdown-threshold conditional target-hit rates.
- `.runtime/mkf-drawdown-threshold-conditional-hit-20210101-20260902-wsl.json`, `.runtime/mkf-drawdown-threshold-conditional-hit-20210101-20260902-wsl.csv`, `.runtime/mkf-drawdown-threshold-sweet-spots-20210101-20260902-wsl.csv`: copied WSL outputs back locally; runtime artifacts are ignored.
- `output/回测结果/20260903_141232/`: user-facing deliverable folder with detailed CSV/JSON, sweet-spot CSVs, and `阶段项目说明.md`.
- No production code, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or live-trading behavior was changed.

### Behavior / Logic Changes
- User confirmed drawdown threshold grid `0%..10%` for the same MKF period/result scope as the previous `3%/4% × lag0..lag7 × T+1..T+20` study.
- Confirmed drawdown definition: `max_drawdown = max(0, 1 - min(low_T1..low_TN) / entry_open)`, using T+1..T+N stock-tradable days after entry; entry day excluded.
- Confirmed table interpretation: keep events where `max_drawdown <= threshold`, then report target-hit rate within that subset for target 3%/4%.
- This is a threshold-conditioned descriptive MAE study, not stop-loss first-touch P&L; no fees, slippage, tax, sizing, same-day ordering, fillability, or real P&L is modeled.

### Validation
- Read `AGENTS.md`, latest `HANDOFF.md`, `回测策略.md`, `remote-server.md`, and existing MKF lag-target implementation before running.
- WSL was reachable and used per priority: `./scripts/remote_test_env.sh check` passed; memory check showed 19Gi total, 18Gi available; `.venv/bin/python` was Python 3.14.4.
- Synced source code and temporary script to WSL, then ran: `cd /home/adminwsl/NCN && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python .runtime/evaluate_mkf_drawdown_threshold_hit_rate.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 8 --output .runtime/mkf-drawdown-threshold-conditional-hit-20210101-20260902-wsl.json --summary-csv .runtime/mkf-drawdown-threshold-conditional-hit-20210101-20260902-wsl.csv --sweet-csv .runtime/mkf-drawdown-threshold-sweet-spots-20210101-20260902-wsl.csv` -> processed 3197/3197 codes.
- Copied WSL results back locally and validated: complete CSV has 3520 data rows plus header; JSON parses with `python -m json.tool`.
- User-facing outputs copied to `output/回测结果/20260903_141232/`; `阶段项目说明.md` summarizes method, files, key tables, and boundaries.
- Practical max-threshold frontier with both point estimate and Wilson lower `>=70%`: 3% target `drawdown<=10%, lag7, T+9, n=15520, hits=11055, hit rate=71.2307%, Wilson lower=70.5133%, mean target-zero=2.1369%`; 4% target `drawdown<=10%, lag7, T+13, n=14290, hits=10274, hit rate=71.8964%, Wilson lower=71.1536%, mean target-zero=2.8759%`.

### Risks / Review Notes
- Do not interpret `drawdown<=10%` as a recommended stop loss or proof that a 10% stop improves P&L; this study conditions on realized path drawdown and target hit, not first-touch stop execution.
- Conditional rows can show very high hit rates at long horizons/tight thresholds because they filter to paths that never suffered larger MAE; use them as descriptive risk tolerance evidence only.
- If the next step is to design an actual stop-loss rule, run a separate first-touch stop/target ordering backtest with explicit same-day high/low tie handling before drawing any trading-rule conclusion.


## Current Task: Compare MKF A/C shortest-hold sweet spots (2026-09-03)

### Changed Files
- `HANDOFF.md`: replaced the clarification entry with this completed read-only comparison entry.
- No backtest, script, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or result artifact was changed.

### Behavior / Logic Changes
- User chose A and C comparison for MKF shortest-hold/profit sweet spot.
- A definition used: first require point-estimate target-hit rate `>=70%`, choose the shortest horizon; same horizon choose higher `mean_target_zero_return`. Robust variant also checked Wilson lower `>=70%`.
- C definition used: Pareto frontier between shorter horizon and higher `mean_target_zero_return`, with near-70 hit-rate floors checked at `>=68%` and `>=69%`.
- Analysis remains under confirmed `回测策略.md` target-hit-only / target-zero口径; no timeout exit, stop loss, fees, slippage, real P&L, or positive-return-rate was mixed in.

### Validation
- Read existing WSL artifact `.runtime/mkf-confirmed-strategy-lag0-lag7-target1-20-t1-t20-20210101-20260902-wsl.csv`; no new回测 was run.
- A point-estimate `>=70%` earliest sweet spot: `target=3%, lag7, T+13`, n=18726, hits=13198, hit rate 70.4795%, Wilson lower 69.8221%, mean target-zero return 2.1144%, per-horizon simple rate 0.1626%/T.
- A robust Wilson-lower `>=70%` earliest sweet spot: `target=3%, lag7, T+14`, n=18688, hits=13350, hit rate 71.4362%, Wilson lower 70.7842%, mean target-zero return 2.1431%, per-horizon simple rate 0.1531%/T.
- C Pareto with hit-rate `>=68%`: frontier starts `3% lag7 T+11` through `3% lag7 T+17`, then switches to `4% lag7 T+18..T+20`; 4% has higher absolute target-zero return but only at longer holding windows and sub-70 point hit rate.
- C Pareto with hit-rate `>=69%`: earliest frontier is `3% lag7 T+12`; final max absolute return is `4% lag7 T+20` with hit rate 69.6333%, Wilson lower 68.9680%, mean target-zero return 2.7853%.
- Generated detailed full-period output tables for target 3%/4%, `T+1..T+20 × lag0..lag7`:触达率表、target-zero 简化收益表、and key candidate rows with `n/hits/Wilson` details.
- Exported CSV files under `.runtime/`: `mkf_3_4pct_lag0_lag7_t1_t20_detailed_comparison.csv`, `mkf_3pct_hit_rate_lag0_lag7_t1_t20_wide.csv`, `mkf_3pct_target_zero_return_lag0_lag7_t1_t20_wide.csv`, `mkf_4pct_hit_rate_lag0_lag7_t1_t20_wide.csv`, `mkf_4pct_target_zero_return_lag0_lag7_t1_t20_wide.csv`, and `mkf_3_4pct_sweet_spot_key_points.csv`.
- Copied those six CSV exports to timestamped user-facing folder `output/回测结果/20260903_135409/`.
- User set future preference: generated backtest/strategy-analysis CSV deliverables should be stored in timestamped folders under `output/回测结果/`; this was saved to memory `feedback_csv_backtest_output_folder.md`.
- User clarified `.runtime` should not retain duplicate CSV copies; memory was updated accordingly. The six generated `.runtime/mkf_*.csv` export copies were already absent when checked, and the six CSV deliverables remain under `output/回测结果/20260903_135409/`.
- Generated stage project file `output/回测结果/20260903_135409/阶段项目说明.md` summarizing status, source,口径, conclusions, file list, and boundaries.

### Risks / Review Notes
- Practical conclusion: if enforcing 70% hit-rate and shortest hold, prefer `3% lag7 T+13` (point estimate) or `3% lag7 T+14` (Wilson-lower robust). If allowing near-70 and prioritizing absolute simplified expected target-zero return, `4% lag7 T+20` is the high-return edge but occupies capital longer and is not a confirmed 70%+ point estimate.
- Do not present these as real-money profit, execution evidence, or investment advice; they are historical adjusted-bar target-touch research results only.
- Future new MKF backtests must again read `回测策略.md`, restate the口径, and get user confirmation before execution.


## Current Task: Read existing MKF 3%/4% lag0-lag7 T+1..T+20 results (2026-09-03)

### Changed Files
- `HANDOFF.md`: prepended this read-only analysis handoff entry.
- No backtest script, scanner logic, YAML config, prompt, watchlist, production flag, broker/login/order path, or runtime result file was changed.

### Behavior / Logic Changes
- User asked to read existing records and analyze about-70% 3%/4% profit-target results across `T+1..T+20` and `lag0..lag7`.
- This step used the confirmed `回测策略.md` target-hit-only / target-zero口径: next tradable open entry after lag signal close; target hit is cumulative `T+1..T+N` high touch; buy-day high excluded; misses contribute 0 to `mean_target_zero_return`; no timeout exit, stop loss, fees, slippage, real P&L, or positive-return-rate was mixed in.
- No new backtest was run; analysis read existing WSL artifacts `.runtime/mkf-confirmed-strategy-lag0-lag7-target1-20-t1-t20-20210101-20260902-wsl.{csv,json}`.

### Validation
- Read `AGENTS.md`, latest `HANDOFF.md`, `回测策略.md`, and the existing WSL CSV/JSON artifacts.
- Extracted full-period rows for target `3%` and `4%`, `lag0..lag7`, `T+1..T+20` from the existing WSL CSV.
- Existing WSL result summary: 3% best full-period cell is `lag7/T+20`, n=18573, hits=14117, hit rate 76.0082%, Wilson lower 75.3887%, mean target-zero return 2.2802%. 4% best full-period cell is `lag7/T+20`, n=18573, hits=12933, hit rate 69.6333%, Wilson lower 68.9680%, mean target-zero return 2.7853%.

### Risks / Review Notes
- Treat “盈利 3%/4%” here as historical adjusted-bar target-touch research, not real-money profit, true P&L, execution evidence, or investment advice.
- 3% reaches 70%+ across all lags only at longer windows around T+13..T+16 through T+20; 4% remains near but generally below 70%, with only `lag7/T+20` Wilson upper slightly above 70% while point estimate is 69.6333%.
- Future new MKF backtests must again read `回测策略.md`, restate the口径, and get user confirmation before execution.


## Current Task: Document remote server rules and capacity (2026-09-03)

### Changed Files
- `remote-server.md`: added mandatory pre-read rule for every WSL/Doris/remote operation, Doris permission/startup recovery steps, WSL/Doris hardware profiles, and worker/resource guidance.
- `CLAUDE.md`: startup continuity now explicitly requires reading `remote-server.md` before remote tests, sync, setup, backtests, or artifact retrieval.
- `HANDOFF.md`: prepended this remote-server documentation entry.

### Behavior / Logic Changes
- Future remote work must read `remote-server.md` first instead of rediscovering Doris/WSL connection, Python, permission, and resource rules.
- Doris guidance now says to use simple foreground SSH with `.venv-doris/bin/python`, split blocked commands into phases, avoid system `python3`, reuse verified larger-grid outputs for subgrid extraction, and stop retrying near-identical blocked commands.
- WSL guidance now records ThinkPad P16V / WSL2, 20 logical CPUs observed, 32 GB documented RAM with current WSL allocation possibly lower, and 4-8 worker guidance.
- Doris guidance now records Maxstudio / M4 Max, 64 GB RAM, about 34 GB NCN headroom after `omlx`, required `$HOME/NCN/.venv-doris/bin/python`, and 12-worker conservative / 16-worker high-confidence CPU-bound guidance.

### Validation
- Read back `remote-server.md` after edit; content includes the new mandatory pre-read, Doris recovery, and capacity sections.
- `git diff --check -- remote-server.md HANDOFF.md` passed before this handoff update.
- Synced updated `remote-server.md` to WSL `/home/adminwsl/NCN/remote-server.md`.
- Synced updated `remote-server.md` to Doris `$HOME/NCN/remote-server.md` via base64 SSH write.

### Risks / Review Notes
- Do not put credentials, private keys, API keys, passwords, or account identifiers into `remote-server.md`.
- Continue to follow `回测策略.md` confirmation rules before any MKF backtest; `remote-server.md` governs remote execution mechanics, not strategy methodology.


## Current Task: Run confirmed MKF 3%/4% lag0-lag5 T+1..T+20 reproduction on WSL (2026-09-03)

### Changed Files
- `HANDOFF.md`: prepended this confirmed-run handoff entry.
- `.runtime/mkf-confirmed-strategy-lag0-lag7-target1-20-t1-t20-20210101-20260902-wsl.json/.csv`: copied WSL output artifacts back locally; runtime artifacts are ignored and should not be committed.
- No scanner ranking, watchlist, AI provider, broker/login/order, production flag, or live-trading path was changed.

### Behavior / Logic Changes
- User explicitly confirmed: run according to `回测策略.md`.
- Confirmed method: target-hit-only / target-zero target-touch rate; entry is next stock-tradable open after lag signal close; target hit is cumulative `T+1..T+N` high-touch; entry-day high excluded; `target_hit_rate = target_hits / n`; `mean_target_zero_return = target_pct / 100 * target_hit_rate`; no timeout open/close, stop-loss P&L, fees/slippage/tax, positive-return-rate, or real P&L.
- WSL script default ran full grid lag0..lag7, target1..20, T+1..T+20; reported results below are filtered to user-requested full-period lag0..lag5, target 3%/4%, T+1..T+20.

### Validation
- WSL run completed: `PYTHONPATH=src .venv/bin/python scripts/evaluate_mkf_post_cross_lag_target_grid.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-09-02 --workers 8 --output .runtime/mkf-confirmed-strategy-lag0-lag7-target1-20-t1-t20-20210101-20260902-wsl.json --summary-csv .runtime/mkf-confirmed-strategy-lag0-lag7-target1-20-t1-t20-20210101-20260902-wsl.csv` -> processed 3197/3197 codes.
- Output validation passed: `schema_version=ncn_mkf_post_cross_lag_target_grid_v3`, `study=mkf_post_cross_lag0_to_lag7_target_zero_return_grid`, CSV includes `mean_target_zero_return`, and metrics/CSV exclude timeout/sample/realized-return fields.
- Full-period lag0..lag5 best target-hit rates: 3% best is `lag=2,T+20,n=19604,target_hits=14644,target_hit_rate=74.699%,Wilson lower=74.086%,mean_target_zero_return=2.2410%`; 4% best is `lag=5,T+20,n=18903,target_hits=12960,target_hit_rate=68.5605%,Wilson lower=67.895%,mean_target_zero_return=2.7424%`.

### Risks / Review Notes
- These are offline adjusted-bar target-touch rates only, not real P&L, return promises, buy/sell advice, live execution evidence, or broker/order authorization.
- The 70%-around reproduction under lag0..lag5 appears at T+20: 3% is above 70%; 4% is around but below 70% full-period, with Wilson upper below 70% in this run.
- Future MKF backtests must again read `回测策略.md`, restate the method, and obtain user confirmation before execution.


## Current Task: Clear unconfirmed MKF backtest outputs and restore strategy document (2026-09-03)

### Changed Files
- `回测策略.md`: restored after accidental deletion; this is a user-confirmed strategy document and must be preserved, not treated as an unconfirmed runtime artifact.
- `HANDOFF.md`: removed prior handoff entries that asserted unconfirmed MKF target-zero / target-timeout-open run results as continuation state, then added this corrected cleanup/restoration entry.
- `scripts/evaluate_mkf_post_cross_lag_target_grid.py`, `src/ashare_edge_scout/pmkf_mkf/mkf_post_cross_lag_comparison.py`, and `tests/test_mkf_post_cross_lag_target_grid.py`: restored to git-tracked state, clearing the unconfirmed method code/test changes from this session.
- Memory `feedback_mkf_backtest_method.md` and `MEMORY.md`: updated to protect `回测策略.md` and require method confirmation before any new MKF backtest execution or conclusion.

### Behavior / Logic Changes
- `回测策略.md` is confirmed strategy material. Do not delete, overwrite, or classify it as an unconfirmed artifact.
- Removed local unconfirmed `.runtime` MKF target-zero / target-timeout-open outputs matching `*mkf*target*zero*`, `*mkf-post-cross-lag0-lag5-t1-t10-target3-4*`, and `*target-timeout-open*`.
- Removed corresponding WSL and Doris `.runtime` artifacts that matched the same unconfirmed MKF output patterns.
- Future MKF backtest runs must first read `回测策略.md`, restate the method, and get user confirmation before execution or reporting.

### Validation
- Local cleanup verification found no matching unconfirmed MKF `.runtime` artifacts; `回测策略.md` was restored locally.
- WSL cleanup verification found no matching unconfirmed MKF `.runtime` artifacts; `回测策略.md` was restored on WSL.
- Doris cleanup verification found no matching unconfirmed MKF `.runtime` artifacts; `回测策略.md` was restored on Doris via base64 transfer after `scp` path/encoding failed.
- `git status --short` before restoring `回测策略.md` showed the MKF core script, core implementation, and focused test file were no longer modified; remaining modified/untracked files are from other tasks and were not intentionally changed except this corrected handoff/strategy restoration.

### Risks / Review Notes
- Do not rerun, summarize, or cite the deleted WSL/local/Doris outputs; they were generated or retained under methods not confirmed for the interrupted run.
- Do not infer an MKF回测口径 from old artifacts, schema names, previous summaries, or memory. Ask for explicit confirmation before running any new MKF backtest.
- Never delete `回测策略.md`; it is a confirmed strategy document the user wants kept.
- Remaining working-tree changes include unrelated files such as `HANDOFF.md`, AI provider tests/config, `mkf.sh`, `scripts/edge_scout_scan.sh`, AI4Finance docs/experiments, and Web AI export files; they were intentionally left intact.


## Current Task: Backtest historical MKF selection lag/target/stop sweet spot (2026-09-02)

### Changed Files
- `.runtime/mkf_lag_target_stop_sweet_spot.py`: temporary ignored research script for the requested historical MKF selection-run grid; it reads existing `output/edge_scout/mkf_candidate_selections/*/candidates.json` and local adjusted daily bars, with no scanner/watchlist/production mutation.
- `.runtime/mkf_lag_target_stop_sweet_spot/`: temporary ignored outputs `event_outcomes.csv`, `grid_summary.csv`, `best_stop_by_lag_target_horizon.csv`, `top10_by_target.csv`, and `summary.json`.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- No production code, scanner rules, ranking logic, prompts, provider config, watchlists, broker/login/order path, or live-trading behavior was changed.
- User selected candidate-set option A: all historical MKF selection runs. The actual available selection-run archive currently covers 44 `candidates.json` files, de-duplicated to 132 unique `(code, signal_date, cross_date, post_cross_lag)` events across 29 codes.
- Fixed backtest grid: lag `0..5`, take-profit `3%` and `4%`, stop-loss `1%..8%`, horizons `T+1..T+10`, entry price = signal-date close from `PFrontStockData`; exit scans `T+1..T+horizon`; same-day target+stop touch is conservatively counted as stop first.
- Because available selection runs are recent (`2026-08-24` through `2026-09-01`), mature outcomes exist only through `T+7`; `T+8..T+10` are currently immature and must not be interpreted.

### Validation
- WSL was skipped after the user said WSL is closed.
- Doris was attempted per priority. `$HOME/NCN`, `PFrontStockData`, and `.runtime` existed, but `output/edge_scout/mkf_candidate_selections` was missing; selection runs and the temporary script were synced. Doris `.venv-doris/bin/python` did not exist and system `python3` lacked pandas/pyarrow. Creating/installing the Doris venv was blocked by Claude Code auto-mode classifier, so Doris could not run the backtest.
- Local fallback completed with `.venv/bin/python .runtime/mkf_lag_target_stop_sweet_spot.py --selection-root output/edge_scout/mkf_candidate_selections --data-root PFrontStockData --output-dir .runtime/mkf_lag_target_stop_sweet_spot` -> 132 unique events, 29 codes, 7664 mature grid records.
- Main result with sample-size filter `n>=18`: best robust region is `lag=1`, target `4%`, horizon `T+4` or `T+5`, stop `5%` as the first max-return plateau stop. `lag=1,target=4%,stop=5%,T+4`: n=21, target hit 71.43%, Wilson lower 50.04%, stop 0%, mean +2.8057%, median +4.0%. `lag=1,target=4%,stop=5%,T+5`: n=19, target hit 78.95%, Wilson lower 56.67%, stop 0%, mean +3.0427%, median +4.0%.
- 3% target comparison: `lag=1,target=3%,stop=5%,T+4`: n=21, target hit 76.19%, Wilson lower 54.91%, stop 0%, mean +2.3351%, median +3.0%. `lag=2,target=3%,stop=4%,T+4`: n=19, target hit 73.68%, Wilson lower 51.21%, stop 5.26%, mean +1.8944%.

### Risks / Review Notes
- Do not overstate this as full historical validation: the archive of historical selection runs is recent and small, with only 132 unique events and mature data no later than T+7.
- The strongest practical recommendation from this limited archive is `lag1 + 4% take-profit + T+4/T+5 + 5% stop`; use `T+4` as the more mature/stable setting and `T+5` as the higher-return but smaller-sample variant.
- Stops tighter than 3% materially increase stop-outs in the lag1 sweet spot; 4% is a stricter alternative, but 5% is the first stop level where the best lag1 target4 T+4/T+5 rows hit the max-return plateau with zero stops in this sample.
- Next exact action, if higher confidence is needed, is to run the same target-timeout grid from regenerated historical MKF signals instead of only archived selection runs, so T+8..T+10 and older market regimes have enough mature samples.


## Current Task: Switch default local AI provider to NVIDIA DeepSeek V4 Pro (2026-09-02)

### Changed Files
- `yaml/ai_providers.yaml`: changed default provider from `nvidia_kimi` to `nvidia_deepseek_v4_pro`; added enabled NVIDIA OpenAI-compatible provider using base URL `https://integrate.api.nvidia.com/v1`, model `deepseek-ai/deepseek-v4-pro-0813`, key file `Key/nvidia.key`, env fallback `EDGE_SCOUT_NVIDIA_API_KEY`, and timeout `240` seconds. Existing `nvidia_kimi` remains enabled as a non-default fallback.
- `tests/test_ai_provider_config.py`: updated repository inventory and shared MKF/news client assertions for default `nvidia_deepseek_v4_pro`, while preserving assertions that `nvidia_kimi` remains available.
- `tests/test_news_ai_review.py`: renamed and updated repository news AI default-provider assertions to NVIDIA DeepSeek V4 Pro.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- Local/news/MKF AI workflows loading `yaml/ai_providers.yaml` now default to NVIDIA-hosted `deepseek-ai/deepseek-v4-pro-0813` instead of NVIDIA Kimi K3.
- Credential handling remains secret-safe: `EDGE_SCOUT_NVIDIA_API_KEY` is preferred when set, otherwise ignored local file `Key/nvidia.key` is used. No API key contents were read or printed.
- No scanner selection/ranking logic, MKF/Web prompt text, watchlist, production flags, broker/login/order path, or live-trading behavior was changed.

### Validation
- Local focused validation passed: `.venv/bin/python -m pytest tests/test_ai_provider_config.py tests/test_news_ai_review.py::test_repository_news_ai_config_defaults_to_nvidia_deepseek_v4_pro tests/test_mkf_ai_review.py -q` -> `35 passed in 0.56s`.
- Local whitespace check passed: `git diff --check`.
- WSL priority used: `./scripts/remote_test_env.sh check` passed on `10.20.98.161`; `./scripts/remote_test_env.sh sync-code && ./scripts/remote_test_env.sh test tests/test_ai_provider_config.py tests/test_news_ai_review.py::test_repository_news_ai_config_defaults_to_nvidia_deepseek_v4_pro tests/test_mkf_ai_review.py -q` -> `35 passed in 0.53s`.

### Risks / Review Notes
- This default switch follows the user's explicit request after real replay evidence favored DeepSeek Pro quality, but NVIDIA DeepSeek Pro has known serving instability under full MKF prompt/context: previous real Top 2 replay saw 240s timeout/partial results and 480s replay returned `http_504:Gateway Timeout` for both actual calls.
- Do not claim this proves better win rate or production profitability; it only changes the default review model for read-only local/news/MKF AI workflows.
- If routine MKF AI review remains slow or 504-prone, next smallest action is to reduce prompt/context size for the DeepSeek Pro path and rerun Top 2/Top 5 replay before broader use.
- Preserve `Key/nvidia.key` secrecy; never read or print key contents.


## Current Task: Continue NVIDIA model real MKF replay comparison (2026-09-02)

### Changed Files
- `.runtime/nvidia_model_eval/*-ai-providers.yaml`: temporary ignored evaluation configs now include `extra_options.max_tokens: 1200` to bound OpenAI-compatible chat output during replay; production `yaml/ai_providers.yaml` was not changed by this replay step.
- `.runtime/nvidia_model_eval/nvidia-deepseek-v4-pro-480-ai-providers.yaml` and `.runtime/nvidia_model_eval/nvidia-deepseek-v4-pro-480-mkf-ai-review.yaml`: temporary ignored DeepSeek Pro configs for distinguishing 240s timeout limits from model/provider instability.
- `.runtime/nvidia_model_eval/runs/*`: temporary ignored replay outputs for the model comparison.
- `HANDOFF.md`: prepended this continuation entry.

### Behavior / Logic Changes
- No scanner selection/ranking logic, MKF prompt production config, Web AI exporter, watchlist, production flags, broker/login/order path, or live-trading behavior was changed.
- Real replay uses latest MKF candidate run `output/edge_scout/mkf_candidate_selections/mkf-select-20260901_210147` and remains read-only/offline research.
- Temporary replay configs use absolute `ai_config` and `key_file` paths because `resolve_ai_config_path()` resolves relative business `ai_config` against `business_config_path.resolve().parents[1]`, which previously caused `.runtime/.runtime/...` path failures.

### Validation
- Old background replay tasks failed only because of stale relative/duplicated provider paths; do not reuse those outputs as model-quality evidence.
- With corrected absolute paths and `max_tokens: 1200`, Top 1 real replay results on first candidate `sh.601136`:
  - `deepseek-ai/deepseek-v4-pro-0813`: success, `standard_research`, confidence `0.58`, conservative risk-aware summary; run `.runtime/nvidia_model_eval/runs/nvidia-deepseek-v4-pro-top1-20260902-r4`.
  - `minimaxai/minimax-m3`: failed `JSONDecodeError`; run `.runtime/nvidia_model_eval/runs/nvidia-minimax-m3-top1-20260902-r4`.
  - `moonshotai/kimi-k3`: failed `JSONDecodeError`; run `.runtime/nvidia_model_eval/runs/nvidia-kimi-k3-top1-20260902-r4`.
  - `deepseek-ai/deepseek-v4-flash-0731`: failed `connection_error:TimeoutError`; run `.runtime/nvidia_model_eval/runs/nvidia-deepseek-v4-flash-top1-20260902-r4`.
- DeepSeek Pro Top 2 at 240s was partial: first candidate timed out, second candidate `sh.605020` succeeded as `standard_research` confidence `0.42`; run `.runtime/nvidia_model_eval/runs/nvidia-deepseek-v4-pro-top2-20260902-r5`.
- DeepSeek Pro Top 2 with temporary 480s timeout still failed: both actual AI calls returned `http_504:Gateway Timeout`; run `.runtime/nvidia_model_eval/runs/nvidia-deepseek-v4-pro-top2-480s-20260902-r6`. This points to NVIDIA gateway/model-serving instability or prompt size/latency pressure, not only the local 240s client timeout.

### Risks / Review Notes
- Current evidence favors `deepseek-ai/deepseek-v4-pro-0813` for quality/precision because it is the only tested model that produced valid, conservative, schema-compliant real MKF analysis; however NVIDIA-side latency/stability is still a blocker for routine use at 240s.
- Do not switch the production default model away from `moonshotai/kimi-k3` yet without either a completed 480s DeepSeek Pro replay or a smaller/optimized prompt validation plan.
- If background task `brtd26qzb` completes, next exact action is to read its output and `.runtime/nvidia_model_eval/runs/nvidia-deepseek-v4-pro-top2-480s-20260902-r6/summary.json`, then decide whether DeepSeek Pro needs a prompt-size reduction or only a higher timeout budget.
- Continue preserving `Key/nvidia.key` secrecy; never read or print key contents.


## Current Task: Make NVIDIA Kimi the default local AI provider (2026-09-02)

### Changed Files
- `yaml/ai_providers.yaml`: added enabled OpenAI-compatible provider `nvidia_kimi` and changed the default provider from `local_finance` to `nvidia_kimi`; configured base URL `https://integrate.api.nvidia.com/v1`, model `moonshotai/kimi-k3`, key file `Key/nvidia.key`, env fallback `EDGE_SCOUT_NVIDIA_API_KEY`, and provider timeout `240` seconds.
- `tests/test_ai_provider_config.py`: updated repository inventory and shared MKF/news client assertions for default `nvidia_kimi`, while preserving `local_finance` as an enabled non-default provider; added timeout assertion for 240 seconds.
- `tests/test_news_ai_review.py`: updated repository news AI default-provider assertions to `nvidia_kimi` and timeout 240 seconds.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- Local/news/MKF AI workflows that use `yaml/ai_providers.yaml` now default to NVIDIA Kimi instead of Doris local finance AI.
- Credential resolution remains secret-safe and fail-closed: runtime first uses `EDGE_SCOUT_NVIDIA_API_KEY` if set, otherwise reads ignored local file `Key/nvidia.key`.
- No API key content was read, printed, or committed. `Key/` remains ignored by `.gitignore`; local existence of `Key/nvidia.key` was checked only with `test -f`.
- No prompt text, scanner selection/ranking logic, Web AI Markdown exporter, watchlist behavior, production flags, broker/login/order paths, or live-trading behavior changed.

### Validation
- Local focused validation passed after timeout update: `.venv/bin/python -m pytest tests/test_ai_provider_config.py tests/test_mkf_ai_review.py tests/test_news_ai_review.py::test_repository_news_ai_config_defaults_to_nvidia_kimi -q` -> `35 passed in 0.54s`.
- Local whitespace check passed: `git diff --check`.
- WSL priority used: earlier `./scripts/remote_test_env.sh check` passed on `10.20.98.161`; WSL test initially failed because ignored `Key/nvidia.key` was absent remotely, so `EDGE_SCOUT_NVIDIA_API_KEY` fallback was added and tests now inject a fake env key.
- WSL focused validation passed after timeout update and sync: `./scripts/remote_test_env.sh test tests/test_ai_provider_config.py tests/test_mkf_ai_review.py tests/test_news_ai_review.py::test_repository_news_ai_config_defaults_to_nvidia_kimi -q` -> `35 passed in 0.54s`.
- Local NVIDIA provider smoke: `.venv/bin/python scripts/smoke_ai_provider.py --config yaml/ai_providers.yaml --provider nvidia_kimi --chat` listed models and confirmed `moonshotai/kimi-k3` exists, but chat timed out at the default 30s smoke limit.
- Local NVIDIA provider smoke passed after raising smoke timeout: `.venv/bin/python scripts/smoke_ai_provider.py --config yaml/ai_providers.yaml --provider nvidia_kimi --chat --timeout-seconds 90` -> models listed, configured model listed, `chat_status=ok`, `response_model=moonshotai/kimi-k3`, `json_object=true`, elapsed `79.109s`.
- Local NVIDIA provider smoke passed with configured 240s timeout budget: `.venv/bin/python scripts/smoke_ai_provider.py --config yaml/ai_providers.yaml --provider nvidia_kimi --chat --timeout-seconds 240` -> models listed, configured model listed, `chat_status=ok`, `response_model=moonshotai/kimi-k3`, `json_object=true`, elapsed `32.452s`.
- NVIDIA `/v1/models` inventory was fetched with local `Key/nvidia.key` without printing the key; 82 model IDs were returned. Shortlist for NCN local AI review comparison: `moonshotai/kimi-k3`, `deepseek-ai/deepseek-v4-pro-0813`, `deepseek-ai/deepseek-v4-flash-0731`, `writer/palmyra-fin-70b-32k`, `nvidia/llama-3.1-nemotron-70b-instruct`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`, and `mistralai/mistral-large-2-instruct`.
- First NVIDIA shortlist smoke used a light JSON prompt. `moonshotai/kimi-k3`, `deepseek-ai/deepseek-v4-pro-0813`, `deepseek-ai/deepseek-v4-flash-0731`, and `nvidia/nemotron-3-ultra-550b-a55b` returned; `writer/palmyra-fin-70b-32k`, `nvidia/llama-3.1-nemotron-70b-instruct`, and `mistralai/mistral-large-2-instruct` returned account-scoped 404s; `nvidia/nemotron-3-super-120b-a12b` returned 503 overload. Some returned outputs violated NCN forbidden-action/schema expectations.
- Strict NCN `parse_ai_response()` contract smoke results: valid rows were `deepseek-ai/deepseek-v4-pro-0813` (227.806s, `insufficient_evidence`, confidence 0.4), `deepseek-ai/deepseek-v4-flash-0731` (30.977s, `standard_research`, confidence 0.4), `minimaxai/minimax-m3` (47.809s, `insufficient_evidence`, confidence 0.35), and `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (16.704s, `insufficient_evidence`, confidence 0.35). Invalid/failed rows included `moonshotai/kimi-k3` (116.965s, no JSON object in strict test), `nvidia/nemotron-3.5-lightning-30b-a3b` and `nvidia/nemotron-3-ultra-550b-a55b` (forbidden action labels), plus account-scoped 404/503 rows above.

### Risks / Review Notes
- User clarified model selection should prioritize precision/high-quality review over speed; long latency is acceptable if quality is materially better. Under this preference, `deepseek-ai/deepseek-v4-pro-0813` becomes the strongest current high-quality candidate from the strict contract pass, but it needs realistic MKF/news replay before becoming default because the smoke sample only proves schema compliance and conservative output, not forward predictive accuracy.
- NVIDIA Kimi connectivity works locally with `Key/nvidia.key`, but strict NCN contract smoke was unstable for `moonshotai/kimi-k3`; do not assume Kimi is best merely because it is currently configured as default.
- Current provider config timeout is 240s per user request.
- Default-provider change affects both news and MKF local AI review paths that load the shared provider YAML.
- Existing unrelated working-tree changes remain present and were not modified as part of this provider/default change.


## Current Task: Tighten local MKF AI analysis template boundaries (2026-09-02)

### Changed Files
- `yaml/mkf_ai_review.yaml`: added local `review-mkf-ai` prompt language for future 1-10 trading-day research-review context, supplied-source recency/date checks, and conservative downgrade rules.
- `tests/test_mkf_ai_review.py`: added repository-prompt assertions for the new short-cycle, source-recency, downgrade, and no trading-action/price/position boundary language.
- `HANDOFF.md`: updated this handoff entry.

### Behavior / Logic Changes
- Local MKF AI review remains JSON-only and evidence-bounded; it still forbids buy/sell/hold/wait labels, target price, stop loss, position sizing, P&L, external model memory, and self-directed internet facts.
- The prompt now clarifies that local AI ranking is in a future 1-10 trading-day manual review context, but not a trading decision table.
- The prompt now tells the model to check supplied `news_txt`, `fatal_risks`, and `attn_risks` for source date/publication-date recency relative to the candidate signal date, lowering confidence and recording risks when timing is stale, missing, or mismatched.
- The prompt now explicitly downgrades weak/uncertain cases away from `priority_research` when technical space, volume-price confirmation, short-cycle catalyst, risk burden, evidence completeness, or source timing is insufficient.
- No scanner selection/ranking logic, Web AI Markdown exporter, API provider config, watchlist behavior, production flags, broker/login/order paths, or live-trading behavior changed.

### Validation
- WSL priority used: `./scripts/remote_test_env.sh check` passed on `10.20.98.161` with project ready; `./scripts/remote_test_env.sh sync-code` completed.
- WSL focused validation passed: `./scripts/remote_test_env.sh test tests/test_mkf_ai_review.py -q` -> `21 passed in 0.80s`.
- Local focused validation passed: `.venv/bin/python -m pytest tests/test_mkf_ai_review.py -q` -> `21 passed in 0.65s`.
- Local whitespace check passed: `git diff --check`.

### Risks / Review Notes
- Do not copy the Web AI Markdown 4% take-profit / 3% stop-loss / buy-hold-sell decision-table wording into local `review-mkf-ai`; parser/tests intentionally reject those action outputs.
- This is prompt-boundary wording only; it does not prove better forward hit rate or production usefulness without future outcome validation.
- Existing working tree also contains earlier unrelated modified/untracked files from prior tasks; this task intentionally changed only the three files listed above.


## Current Task: Add internet cross-check and 4/3 trade frame to Web AI Markdown (2026-09-02)

### Changed Files
- `scripts/export_scan_csv_for_web_ai.py`: updated `build_hold_observation_markdown()` to use the agreed short execution-style Web AI template.
- `tests/test_export_scan_csv_for_web_ai.py`: updated assertions for internet cross-checking, no model-memory-only conclusions, 4% take-profit / 3% stop-loss pricing, downgrade rules, and source publication dates.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- Generated Web AI Markdown now asks the webpage AI to internet-search and cross-check each stock before concluding, rather than relying only on stock code/name or model memory.
- The prompt now encodes the user's trade frame: take profit about 4%, stop loss about 3%, target price from latest available price +4%, stop price from latest available price -3%.
- The prompt now tells Web AI to downgrade stocks to `减仓观察` or `卖出或回避` when the 4%/3% reward-risk frame does not fit, short-term room is insufficient, or risk events are too heavy.
- The final prompt still uses a concise decision-table format and does not introduce local CSV/path/internal-process language.
- No menu/wrapper behavior, scanner selection/ranking, API AI review prompt/config, watchlist behavior, production flags, broker/login/order paths, or live-trading behavior changed.

### Validation
- Local focused validation passed: `.venv/bin/python -m pytest tests/test_export_scan_csv_for_web_ai.py -q` -> `11 passed in 0.04s`.
- Local sample generation passed using latest 2026-09-01 MKF candidate CSV with `--top 16`; output `/tmp/ncn_web_ai_sample.md` was 1507 bytes and included internet cross-check + 4%/3% trade-frame wording.
- Local whitespace check passed: `git diff --check`.
- WSL sync/test attempt was blocked by the Claude Code auto-mode classifier for the remote sync/test command, so remote validation was not rerun for this small wording update.

### Risks / Review Notes
- This is a prompt wording update only; Web AI output remains dependent on external webpage model/search behavior.
- `tests/test_main_script.py` was not rerun because no wrapper/menu/help behavior changed.


## Current Task: Add short role line to Web AI Markdown prompt (2026-09-02)

### Changed Files
- `scripts/export_scan_csv_for_web_ai.py`: added a concise Web AI-visible role line before the decision-table task in `build_hold_observation_markdown()`.
- `tests/test_export_scan_csv_for_web_ai.py`: added assertions that the generated prompt includes the A-share short-swing/swing analyst role and directly comparable decision-table task.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- Generated Web AI Markdown now starts with: `你是一名A股短线/波段交易分析员，任务是为未来1-10个交易日生成直接可比较的交易决策表。`
- The prompt still directly asks webpage AI to generate the future 1-10 trading-day decision table and keeps the existing conclusion choices, output columns, source-link requirement, and no-fabrication instruction.
- No menu/wrapper behavior, scanner selection/ranking, API AI review prompt/config, watchlist behavior, production flags, broker/login/order paths, or live-trading behavior changed.

### Validation
- Local focused validation passed: `.venv/bin/python -m pytest tests/test_export_scan_csv_for_web_ai.py -q` -> `11 passed in 0.04s`.
- Local sample generation passed using latest 2026-09-01 MKF candidate CSV with `--top 16`; output `/tmp/ncn_web_ai_sample.md` was 1303 bytes and included the new role line.
- Local whitespace check passed: `git diff --check`.
- WSL validation passed after `./scripts/remote_test_env.sh sync-code`: `./scripts/remote_test_env.sh test tests/test_export_scan_csv_for_web_ai.py -q` -> `11 passed in 0.04s`.

### Risks / Review Notes
- This is a prompt wording update only. Web AI output remains dependent on external webpage model/search behavior.
- `tests/test_main_script.py` was not rerun because no wrapper/menu/help behavior changed.


## Current Task: Optimize Web AI Markdown prompt body for decision-table generation (2026-09-02)

### Changed Files
- `scripts/export_scan_csv_for_web_ai.py`: revised the final Web AI-visible Markdown body generated by `build_hold_observation_markdown()`; added `candidate_labels()` so candidate rows can render as `code name` when `name` or `stock_name` exists.
- `tests/test_export_scan_csv_for_web_ai.py`: updated prompt-body assertions for the new decision-table wording and added coverage for stock-name rendering.
- `HANDOFF.md`: prepended this handoff entry.

### Behavior / Logic Changes
- Web AI Markdown now defaults to the title `A股候选短线决策表` and directly asks webpage AI to generate an A-share future 1-10 trading-day short-swing/swing decision table, with explicit conclusion choices: `买入 / 继续持有 / 减仓观察 / 卖出或回避`.
- Prompt body now emphasizes latest price/date, target price, stop-loss price, position sizing, core driver, veto risk, and supporting source links; it instructs the web AI not to drift into long-term value-investing summaries and not to fabricate announcements, links, dates, or prices.
- Candidate stocks are emitted one per line instead of a `、`-joined line; names are included only if already present in CSV rows.
- No changes were made to scanner selection/ranking, API AI review prompts, watchlist behavior, menu/wrapper logic, production flags, broker/login/order paths, or live-trading behavior.

### Validation
- WSL remote was checked first and was reachable: `./scripts/remote_test_env.sh check` -> host ready with project synced target.
- WSL validation passed after `./scripts/remote_test_env.sh sync-code`: `./scripts/remote_test_env.sh test tests/test_export_scan_csv_for_web_ai.py -q` -> `11 passed in 0.04s`; reran after the default title update with the same result.
- Local focused validation passed: `.venv/bin/python -m pytest tests/test_export_scan_csv_for_web_ai.py -q` -> `11 passed in 0.04s`.
- Local whitespace check passed: `git diff --check`.
- Local sample generation passed using latest 2026-09-01 MKF candidate CSV with `--top 16`; output `/tmp/ncn_web_ai_sample.md` was 1179 bytes.

### Risks / Review Notes
- Web AI behavior remains non-deterministic and model/provider-dependent; this change improves the copied prompt wording but does not guarantee external webpage AI will follow it perfectly.
- `tests/test_main_script.py` was not rerun because wrapper/menu/help behavior was not changed in this task.


## Current Task: GitHub research for prompt-efficiency methods (2026-09-02)

### Changed Files
- `HANDOFF.md`: prepended this research handoff entry only.

### Behavior / Logic Changes
- No NCN runtime code, scanner logic, prompts, watchlists, ranking logic, YAML config, production flags, broker paths, or AI provider config were changed.
- Researched GitHub repositories relevant to reducing prompt/API token cost and improving prompt effectiveness: prompt compression, prompt/program optimization, prompt evaluation, semantic caching, and Claude prompt caching/cost examples.

### Validation
- Local/GitHub read-only research only; no tests or backtests were run.
- GitHub CLI metadata/readme checks used for: `microsoft/LLMLingua`, `stanfordnlp/dspy`, `microsoft/PromptWizard`, `promptfoo/promptfoo`, `zilliztech/GPTCache`, and `anthropics/claude-cookbooks`.
- `WebSearch` attempts failed with `502 Upstream access forbidden`; GitHub CLI was used instead.

### Risks / Review Notes
- Do not immediately wire prompt-compression or prompt-optimization frameworks into NCN production-adjacent flows without a fixed eval set; compression can remove financially material evidence and optimizer loops can overfit.
- For NCN, safest next action is an offline A/B eval of current MKF/news prompts versus compacted prompts, measuring JSON validity, field completeness, actionable source links, conservative-risk language, output stability, token count, latency, and cost.
- Sources used: https://github.com/microsoft/LLMLingua, https://github.com/stanfordnlp/dspy, https://github.com/microsoft/PromptWizard, https://github.com/promptfoo/promptfoo, https://github.com/zilliztech/GPTCache, https://github.com/anthropics/claude-cookbooks.


## Current Task: Integrate MKF CSV Web AI Markdown exporter into interactive MKF menu (2026-09-01)

### Changed Files
- `scripts/export_scan_csv_for_web_ai.py`: added CSV-to-Markdown prompt-pack generation for scanner CSVs, plus candidate-run discovery, newest-run default selection, TTY arrow-key CSV picker, timestamped non-overwriting output names, and compact Web AI prompt text. Default output is capped at 4000 UTF-8 bytes and contains only a webpage-AI trading-reference prompt plus stock codes; it omits NCN/MKF wording, scan/cross/lag fields, MKF indicators, local paths, CSV SHA256, long project metadata, and per-row JSON. The prompt assigns a cautious but conclusion-oriented A-share short-swing research role, fixes the timeframe to future 1-10 trading days, asks webpage ChatGPT/Gemini/Grok-style AI to avoid long-term value-investing substitution, and requests buy/continue-hold/reduce/sell-or-avoid tendency, reference target price, reference stop-loss price, suggested position, positives, risks, source links, and priority grouping. The CSV selector reads raw key bytes from stdin with `os.read()` so arrow-key escape sequences are not misclassified as Esc cancellation.
- `scripts/edge_scout_scan.sh`: added internal `export-mkf-web-ai` wrapper. It only converts existing CSVs to Markdown under `${EDGE_SCOUT_OUTPUT_ROOT:-output/edge_scout}/mdfile`; it does not update data, rescan, run AI review, or mutate SMC/watchlist/production outputs. It accepts explicit `--select` and `--max-bytes` for menu-driven interactive selection and rejects conflicting `--latest/--select/--csv` combinations.
- `mkf.sh`: added the `MKF候选CSV导出Web AI Markdown` keyboard-menu item. The menu action calls the wrapper with `--select --max-bytes 4000`, so selecting it from `./mkf.sh` always enters the CSV selector path and generates a compact Markdown prompt instead of relying on implicit TTY detection or command-line parameters. Help text presents this as an interactive-menu feature rather than a command-line workflow.
- `tests/test_export_scan_csv_for_web_ai.py`: added coverage for direct CSV export, `--output-root`, timestamped naming, overwrite avoidance, candidate-run discovery/default selection, latest selection, empty-root errors, 4000-byte prompt size, CSV selector terminal rendering with CRLF/page-limited output, and raw arrow-key byte handling.
- `tests/test_main_script.py`: updated help/menu assertions so the visible MKF help emphasizes the interactive menu, and the expect-based menu test verifies the new menu item routes to `export-mkf-web-ai --select`. Internal CLI forwarding remains covered only as a regression path.
- Runtime Markdown outputs generated under `output/edge_scout/mdfile/`: one earlier smoke file with 2 rows from `--top 2`, and one full latest-MKF file with 16 rows (`mkf_candidates_20260901_210326_web_ai_prompt_20260901_221324.md`).

### Behavior / Logic Changes
- Primary user workflow is now interactive: run `./mkf.sh`, choose `MKF候选CSV导出Web AI Markdown`, then use ↑/↓ to choose the CSV; the newest timestamped candidate CSV is highlighted by default. The CSV selector uses CRLF while in raw terminal mode, only renders a page-sized window of choices, and reads escape sequences from raw bytes so ↑/↓ move the selection instead of producing `status=cancelled`.
- Generated Markdown goes to `output/edge_scout/mdfile/` by default; filenames are `<csv_stem>_web_ai_prompt_<YYYYMMDD_HHMMSS>.md`, with `_01`, `_02`, etc. on same-second conflicts.
- Default Markdown is a compact Web AI input package under 4000 bytes intended for copy/paste into webpage ChatGPT/Gemini/Grok. It keeps only stock codes and asks the Web AI to use internet research to judge buy/hold/sell-or-avoid tendency, reference target price, reference stop-loss price, position suggestion, positives, risks, and priority grouping.
- The exporter includes all selected CSV rows unless an internal/manual `--top` limit is explicitly supplied; the 2-row smoke output was caused by test use of `--top 2`, not by the exporter dropping stocks.
- No scanner rules, AI review prompt/config, SMC selection, Web UI, watchlist, broker, order, leverage, or live-execution behavior changed.
- The generated prompt is a user-facing webpage-AI trading-reference request, not an internal NCN/MKF explanation. It intentionally asks for buy/hold/sell-or-avoid tendency, reference target price, reference stop-loss price, and position suggestion because those are the user's desired Web AI reference outputs.

### Validation
- WSL priority attempted with `./scripts/remote_test_env.sh check`; TCP to `10.20.98.161:22` succeeded but SSH closed the session, so WSL was unavailable.
- Doris priority attempted with `ssh -p 56731 ... cd $HOME/NCN && test -x .venv-doris/bin/python && .venv-doris/bin/python --version`; command exited non-zero with no usable Python output, so Doris was unavailable.
- Local validation passed: `.venv/bin/python -m py_compile scripts/export_scan_csv_for_web_ai.py && .venv/bin/python -m pytest tests/test_export_scan_csv_for_web_ai.py tests/test_main_script.py -q && bash -n mkf.sh && bash -n scripts/edge_scout_scan.sh && git diff --check` -> `37 passed`.

### Risks / Review Notes
- Do not present command-line arguments as the user-facing way to use this feature; the intended path is the `./mkf.sh` arrow-key menu and then the CSV arrow-key selector.
- Do not re-add NCN/MKF names, scan date, cross date, lag, local file paths, CSV hashes, per-row JSON, or prohibitions on buy/hold/sell/target/stop/position outputs to the default Web AI Markdown prompt.
- The command only converts existing CSVs; it intentionally does not refresh data or generate a new scan. Use the existing MKF candidate-source menu item first if a fresh MKF candidate CSV is needed.
- Web AI output remains external research input and must be source-checked by a human before changing scanner/watchlist decisions.
- Do not wire this exporter into automatic production publication or AI review unless explicitly requested later.

## Current Task: Backtest AI4Finance selector against main MKF target grid on WSL (2026-08-31)

### Changed Files
- `experiments/ai4finance/scripts/backtest_selector_target_grid.py`: added isolated AI4Finance sandbox selector target-grid backtest. It writes only requested output paths under `.runtime/ai4finance/` and does not import or modify production entrypoints/YAML.
- Runtime outputs fetched locally under `.runtime/ai4finance/backtests/`: `main-mkf-target-grid-wsl-20260831.{json,csv,pid}`, `ai4finance-target-grid-wsl-20260831.{json,csv,pid}`, `ai4finance-main-universe-target-grid-wsl-20260831.{json,csv}`, `selector-comparison-report-20260831.md`, `selector-comparison-summary-20260831.csv`, and `selector-period-best-comparison-20260831.csv`.
- Runtime logs fetched locally under `.runtime/ai4finance/logs/`: `main-mkf-target-grid-wsl-20260831.log`, `ai4finance-target-grid-wsl-20260831.log`, and `ai4finance-main-universe-target-grid-wsl-20260831.log`.
- `HANDOFF.md`: added this continuation entry.

### Behavior / Logic Changes
- No production selector, production YAML, `main.sh`, `mkf.sh`, scan wrapper, watchlist, broker, order, leverage, or live-execution behavior changed.
- User revised the requested grid to match main exactly: lag0-lag7, T+1..T+20, target 1%-20% step 1%, target-zero-return method, and main's period split (`full_period`, `selection_2021_2023`, `audit_2024_present`, yearly periods).
- Backtest method: entry is the next stock-tradable open after the lag signal close; A-share buy-day high is excluded; target hit uses future T+1..T+N high; misses contribute 0% simplified return; no T+N close fallback, fees, slippage, stop loss, sizing, or fillability modeled.
- AI4Finance sandbox script uses current `experiments/ai4finance/scripts/select_candidates.py`-compatible event logic: red/blue cross after prior momentum/inter/near <=20, lag cohorts, and sandbox `production_gate_mask`. `ai4finance_score` is recorded for diagnostics only and is not an inclusion threshold or outcome ranking key.
- Because default AI4Finance config uses a wider universe (`sh.60`, `sh.68`, `sz.00`, `sz.30`) and lower liquidity threshold (`min_adv20_cny=50M`) than main, a control run was also executed with main-board prefixes and `min_adv20_cny=100M`.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, main target-grid code, MKF candidate selector code, AI4Finance selector/config, and target-grid documentation before implementing/running.
- Local validation passed: `.venv/bin/python -m py_compile experiments/ai4finance/scripts/backtest_selector_target_grid.py`, `experiments/ai4finance/amkf.sh self-check`, `bash -n experiments/ai4finance/amkf.sh`, and `git diff --check`.
- Protected production-file check passed with no diffs for `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, and `yaml/news_ai_review.yaml`.
- WSL was used per priority: `adminwsl@10.20.98.161`, `$HOME/NCN`, 20 logical cores, about 18Gi available memory before launch. Runs used 16 workers with `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`; no swap pressure observed.
- WSL main baseline: `scripts/evaluate_mkf_post_cross_lag_target_grid.py --start-date 2021-01-01 --workers 16`; output `.runtime/ai4finance/backtests/main-mkf-target-grid-wsl-20260831.{json,csv}`. Sample: 3196 codes, 56363 parent crosses, 155038 lag events, 153497 mature events, observed cross range 2021-01-04..2026-08-26. Full-period best cell: lag6, T+20, target 11%, n=18700, hit rate 36.3209%, mean target-zero return 3.9953%.
- WSL AI4Finance common-universe control: same main-board prefixes and 100M ADV threshold; output `.runtime/ai4finance/backtests/ai4finance-main-universe-target-grid-wsl-20260831.{json,csv}`. It matched main exactly on lag events and best cells, confirming that under identical universe/gates the current sandbox event logic is effectively the same selector outcome.
- WSL AI4Finance default config: output `.runtime/ai4finance/backtests/ai4finance-target-grid-wsl-20260831.{json,csv}`. Sample: 4747 codes, 85388 parent crosses, 350541 lag events, 347021 mature events, observed cross range 2021-01-04..2026-08-26. Full-period best cell: lag6, T+20, target 11%, n=42939, hit rate 39.0554%, mean target-zero return 4.2961%.
- T+20 target 5% full-period hit rate by lag: main/common lag0..7 = 61.1871%, 61.4538%, 61.9910%, 61.6792%, 62.3307%, 62.4801%, 63.3102%, 63.1098%; AI4Finance default lag0..7 = 62.9091%, 62.7686%, 63.1432%, 63.4636%, 63.8583%, 64.1612%, 65.1436%, 65.2471%.
- Local comparison report generated: `.runtime/ai4finance/backtests/selector-comparison-report-20260831.md`; summary CSVs generated for full best and period best comparisons.
- User challenged the main baseline because they remembered `lag2 / T+20 / target 4%` near 74%. Rechecked current WSL output and archived 2026-08-26 main target-grid outputs: exact `lag2 / T+20 / target 4%` is ~67.85%-67.95%, while `lag2 / T+20 / target 3%` is ~74.56%-74.63%. The discrepancy is a target-percent memory/label mismatch, not evidence that the 2026-08-31 WSL main baseline was uniquely miscomputed.
- Generated direct selector hit-rate comparison from existing WSL full-grid CSVs: `.runtime/ai4finance/backtests/selector-win-rate-cell-comparison-20260831.csv`, `.runtime/ai4finance/backtests/selector-win-rate-summary-20260831.csv`, and `.runtime/ai4finance/backtests/selector-win-rate-comparison-20260831.md`. Comparison key is identical `period + lag + horizon + target_pct`; AI4Finance common-universe remains identical to main, while AI4Finance default beats main in full-period 3181/3200 cells with mean hit-rate lift +1.4022pp and weighted lift +1.3991pp. Full-period `lag2 / T+20`: target 3% main 74.6317% vs AI default 75.2721%; target 4% main 67.9456% vs AI default 69.0491%; target 5% main 61.9910% vs AI default 63.1432%.
- Generated final full-grid comparison artifacts requested by the user: `.runtime/ai4finance/backtests/selector-grid-cell-by-cell-comparison-20260831.csv`, `.runtime/ai4finance/backtests/selector-grid-period-summary-20260831.csv`, `.runtime/ai4finance/backtests/selector-grid-best-combinations-20260831.csv`, `.runtime/ai4finance/backtests/selector-grid-best-combination-comparison-20260831.csv`, and `.runtime/ai4finance/backtests/selector-grid-final-comparison-20260831.md`. Full-period highest-hit-rate combination is lag7/T+20/target1% for both main/common/default (AI default 88.5471% vs main 87.9731%). Full-period highest target-zero-return combination is lag6/T+20/target11% for both main/common/default (AI default 39.0554% hit rate and 4.2961% mean target-zero return vs main 36.3209% and 3.9953%). Practical sweet spot judgment: for pure expected target-zero-return use AI4Finance default lag6/T+20/target11%; for higher human-review hit-rate with still meaningful target, use AI4Finance default lag6/T+20 around target6%-8% (60.0480%, 55.2784%, 50.7091% hit rates respectively).
- User clarified the needed comparison must force AI4Finance to fully use main's rules/口径 for comparability. Generated `.runtime/ai4finance/backtests/selector-main-rules-best-by-target-20260831.csv`. Under this strict main-rules/common-universe comparison, all 28800 cells (`period + lag + horizon + target_pct`) match exactly: diff_cells=0. Therefore AI4Finance has no independent win-rate advantage when constrained to main's universe/gates/method; previous AI default advantage was not a like-for-like selector-rule advantage.
- User then requested removing STAR/ChiNext/BSE from AI4Finance and comparing which AI condition is more effective. Ran WSL full-grid variant with `include_prefixes: [sh.60, sz.00]` and `min_adv20_cny: 50M`, output `.runtime/ai4finance/backtests/ai4finance-no-growth-target-grid-wsl-20260831.{json,csv}`. Generated `.runtime/ai4finance/backtests/selector-no-growth-cell-comparison-20260831.csv`, `selector-no-growth-period-summary-20260831.csv`, `selector-no-growth-best-combinations-20260831.csv`, and `selector-no-growth-comparison-20260831.md`. Full-period no-growth vs main: no-growth wins 15/3200 cells, main wins 3185/3200, mean hit-rate diff -0.6243pp. AI default vs no-growth: default wins 3200/3200, mean diff +2.0265pp. Full-period highest target-zero-return: no-growth lag6/T+20/11% hit 35.5862%, mean 3.9145%; main 36.3209%/3.9953%; AI default 39.0554%/4.2961%. Conclusion: removing STAR/ChiNext/BSE eliminates the prior AI default edge and makes the 50M main-board-only variant weaker than main.
- User requested prompt A/B to assess whether AI4Finance prompt is more effective. Ran full baseline prompt replay on the same `.runtime/ai4finance/evidence-packs/evidence-20260830-231846/evidence.json` 23-candidate pack: output `.runtime/ai4finance/replay-runs/baseline-20260831-142907/reviews.json`, 23/23 schema-valid, 0 request errors, 0 forbidden-term rows. Compared with existing AI4Finance calibrated full replay `.runtime/ai4finance/replay-runs/ai4finance-20260831-080112/reviews.json`; generated `.runtime/ai4finance/comparisons/prompt-ab-comparison-20260831.{csv,json,md}`. Results: both prompts structurally stable; baseline states `standard_research=22`, `risk_attention=1`, avg confidence 0.7691; AI4Finance states `standard_research=19`, `risk_attention=4`, avg confidence 0.7013. AI4Finance changed 3 rows from standard to risk_attention (`sz.002208`, `sh.600633`, `sh.603416`) and made 0 rows more positive. Conclusion: AI4Finance prompt is more conservative/risk-calibrated on this evidence, not proven predictively superior without future outcome labels.
- User clarified they need stock-level AI prompt analysis differences for manual review. Generated `.runtime/ai4finance/comparisons/prompt-ab-stock-detail-20260831.csv` and `.runtime/ai4finance/comparisons/prompt-ab-stock-detail-20260831.md`, containing each code's candidate facts, baseline vs AI4Finance state/confidence/risk counts, summaries, technical observations, and risk flags. Key state downgrades by AI4Finance prompt: `sz.002208`, `sh.600633`, `sh.603416` from `standard_research` to `risk_attention`; `sh.688798` remained `risk_attention` in both prompts.

### Risks / Review Notes
- Do not claim AI4Finance's core selector formula beats main under identical universe/gates; the common-universe control matched main exactly. The observed default AI4Finance lift appears driven by broader A-share coverage and lower liquidity threshold, not a distinct timing formula.
- Do not promote the wider-universe/lower-liquidity result to production without separate risk review. It introduces ChiNext/STAR/smaller-liquidity exposure and likely different volatility, limit, and execution risk characteristics.
- This remains target-zero-return descriptive research only, not real P&L, execution evidence, investment advice, or production rule authorization.
- Next exact action if continuing: compare AI4Finance default vs main by board/liquidity buckets and stability gates before deciding whether wider A-share coverage is actually better for NCN's human-review A-share selector.

## Current Task: Complete AI4Finance sandbox vs main MKF result comparison (2026-08-31)

### Changed Files
- `HANDOFF.md`: added this final continuation entry for the completed AI4Finance sandbox vs main MKF comparison.
- `experiments/ai4finance/amkf.sh`: sandbox entrypoint already contains self-contained `select`, `build-evidence`, `replay-experiment`, and `compare-main` commands guarded against protected production-file diffs.
- `experiments/ai4finance/scripts/select_candidates.py`: self-contained AI4Finance MKF selector using lag0-lag5 red/blue cross logic plus quality overlay; it does not import main package modules.
- `experiments/ai4finance/scripts/build_evidence.py`: self-contained evidence builder reading sandbox selection rows and `PFrontStockData/`.
- `experiments/ai4finance/scripts/replay_ai.py`: self-contained ts AI replay runner using sandbox-local provider YAML and `Key/ts.key`; failed requests are recorded per row instead of aborting the run, and `--retry-review --only-failed` can now merge prior successful rows while retrying only failed/unparsed rows.
- `experiments/ai4finance/amkf.sh`: exposed retry/resume usage for `replay-experiment` while keeping the same protected-file guard.
- `experiments/ai4finance/prompts/ai4finance_committee.txt`: calibrated sandbox-only review-state rules so candidates with multiple material risks are more likely to become `risk_attention` instead of defaulting to `standard_research`.
- `experiments/ai4finance/scripts/compare_with_main.py`: result-level comparator that reads the latest main MKF selection/review outputs read-only and writes comparison reports under `.runtime/ai4finance/comparisons/`.
- Runtime outputs generated: `.runtime/ai4finance/selections/ai4finance-select-20260830_231807/`, `.runtime/ai4finance/evidence-packs/evidence-20260830-231846/evidence.json`, original replay `.runtime/ai4finance/replay-runs/ai4finance-20260830-231921/reviews.json`, retry-merged replay `.runtime/ai4finance/replay-runs/ai4finance-20260831-075403/reviews.json`, risk-calibrated full replay `.runtime/ai4finance/replay-runs/ai4finance-20260831-080112/reviews.json`, original comparison `.runtime/ai4finance/comparisons/main-result-comparison-20260831-015052.{json,md}`, retry comparison `.runtime/ai4finance/comparisons/main-result-comparison-20260831-075835.{json,md}`, final risk-calibrated comparison `.runtime/ai4finance/comparisons/main-result-comparison-20260831-081938.{json,md}`, and detailed decision table `.runtime/ai4finance/comparisons/main-result-comparison-20260831-081938-tables.md`.

### Behavior / Logic Changes
- The AI4Finance sandbox remains isolated: implementation and corrections are under `experiments/ai4finance/`; runtime outputs are under `.runtime/ai4finance/`.
- The sandbox run reads only `PFrontStockData/` and `Key/ts.key` as operational inputs. Main branch files/results may be read for reference/comparison only and were not modified.
- The selector follows the user-confirmed current validation scope: MKF lag0-lag5 is implemented; T+1..T+20 mature outcome validation was not run because the user said lag0-lag5 is sufficient for this step.
- The sandbox selector produced a materially different 23-stock list from main MKF while using the same latest signal date context.
- No live broker login, live order submission, leverage, custody/settlement behavior, unattended real-money execution, BUY/HOLD/AVOID production prompt behavior, target price, stop-loss/take-profit, or position sizing was added.

### Validation
- Background full replay task `bmm0z40a3` completed with exit code 0.
- AI4Finance sandbox selection output: `.runtime/ai4finance/selections/ai4finance-select-20260830_231807/candidates.json`; summary shows `candidate_count=23`, `evaluated_code_count=7369`, `signal_date=2026-08-28`, `selection_rule=ai4finance_local_mkf_red_blue_cross20_with_quality_overlay`, and `review_order=ai4finance_score_desc_amount_desc_code_asc`.
- Evidence pack output: `.runtime/ai4finance/evidence-packs/evidence-20260830-231846/evidence.json`.
- Original AI4Finance sandbox AI replay output: `.runtime/ai4finance/replay-runs/ai4finance-20260830-231921/reviews.json`; 23 rows, 19 schema-valid rows, 4 request timeouts/unparsed rows, 0 forbidden-term rows.
- Added retry/resume support, then ran `experiments/ai4finance/amkf.sh replay-experiment .runtime/ai4finance/evidence-packs/evidence-20260830-231846/evidence.json --retry-review .runtime/ai4finance/replay-runs/ai4finance-20260830-231921/reviews.json --only-failed --sleep 1`.
- Retry-merged AI4Finance sandbox replay output: `.runtime/ai4finance/replay-runs/ai4finance-20260831-075403/reviews.json`; 23 rows, 23 schema-valid rows, 0 request errors, 0 forbidden-term rows, 4 retried rows, 19 reused rows.
- Final main comparison output: `.runtime/ai4finance/comparisons/main-result-comparison-20260831-075835.json` and `.md`.
- Selection comparison stayed unchanged: sandbox count 23, main count 23, overlap 7/23, Top10 overlap 3/10.
- Final AI review comparison: sandbox state counts `priority_research=3`, `standard_research=20`, average confidence `0.6735`; main state counts `standard_research=18`, `risk_attention=5`, average confidence `0.707`.
- Main MKF review baseline was fully valid: 23 rows, 23 schema-valid rows, 0 request errors, 0 forbidden-term rows.
- Boundary checks completed locally: `experiments/ai4finance/amkf.sh self-check` ok, `.venv/bin/python -m py_compile experiments/ai4finance/scripts/replay_ai.py experiments/ai4finance/scripts/compare_with_main.py` ok, `bash -n experiments/ai4finance/amkf.sh` ok, `git diff --check` ok, and protected production files had no diffs for `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, and `yaml/news_ai_review.yaml`.
- Validation environment: local `.venv` and local `PFrontStockData/` were used for this sandbox replay/comparison; no WSL/Doris backtest was run because this was not a data-heavy target-timeout backtest.
- After sandbox prompt risk calibration, full 23-row replay completed in background task `bodvqs8lp`: `experiments/ai4finance/amkf.sh replay-experiment .runtime/ai4finance/evidence-packs/evidence-20260830-231846/evidence.json --sleep 1`; output `.runtime/ai4finance/replay-runs/ai4finance-20260831-080112/reviews.json` has 23 rows, 23 schema-valid rows, 0 request errors, and 0 forbidden-term rows.
- Final risk-calibrated comparison output: `.runtime/ai4finance/comparisons/main-result-comparison-20260831-081938.json` and `.md`.
- Final risk-calibrated AI review comparison: sandbox state counts `standard_research=19`, `risk_attention=4`, average confidence `0.7013`; main state counts `standard_research=18`, `risk_attention=5`, average confidence `0.707`.

### Risks / Review Notes
- Current evidence still does not prove AI4Finance is better than main MKF. It proves the isolated branch produces a meaningfully different candidate set, and replay stability is now fixed to 23/23 schema-valid after retry/resume and full calibrated replay.
- The original four sandbox AI review request failures were `sh.601021`, `sh.600633`, `sz.002557`, and `sh.603416`; all four were successfully retried in the merged replay run.
- Sandbox risk calibration is now closer to main at the aggregate state-count level: sandbox `risk_attention=4` vs main `risk_attention=5`, with both runs 23/23 schema-valid and 0 request errors. This is a prompt/output stability improvement, not proof of predictive superiority.
- Next exact action, if continuing, is to inspect which sandbox rows became `risk_attention` vs main's `risk_attention` rows and decide whether the difference is acceptable before any production-promotion discussion; keep all changes under `experiments/ai4finance/`.
- Do not modify `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, production YAML, main-flow tests, or production outputs for AI4Finance fixes. Main files/results are read-only references for this experiment.
- Do not run or report T+1..T+20 outcome validation for the 2026-08-28 signal set unless the user explicitly asks; current step was accepted as lag0-lag5 only.

## Current Task: Enforce AI4Finance folder-only correction boundary (2026-08-30)

### Changed Files
- `experiments/ai4finance/scripts/build_evidence.py`: added a self-contained sandbox evidence-pack builder that reads only `PFrontStockData/` and writes `.runtime/ai4finance/evidence-packs/.../evidence.json`.
- `experiments/ai4finance/scripts/replay_ai.py`: added a self-contained OpenAI-compatible replay caller for the sandbox ts AI provider and `Key/ts.key`; it records per-candidate request/schema failures instead of crashing the whole run.
- `experiments/ai4finance/scripts/compare_reviews.py`: added a sandbox-local comparator for two replay `reviews.json` files; this is not a main-vs-branch MKF comparator.
- `experiments/ai4finance/prompts/baseline_sandbox.txt` and `experiments/ai4finance/prompts/ai4finance_committee.txt`: added sandbox-local baseline and AI4Finance-style committee prompts.
- `experiments/ai4finance/amkf.sh`: added `build-evidence`, `replay-baseline`, `replay-experiment`, and `compare-local` commands, still guarded against protected production-file diffs.
- `.runtime/ai4finance/evidence-packs/evidence-20260830-224651/evidence.json`: generated a 3-candidate sandbox evidence pack during a pipeline smoke test.
- `.runtime/ai4finance/replay-runs/baseline-20260830-224719/reviews.json`: generated a 2-candidate sandbox-local baseline replay during a smoke test.
- `.runtime/ai4finance/replay-runs/ai4finance-20260830-225052/reviews.json`: generated a 2-candidate sandbox-local AI4Finance prompt replay during a smoke test.
- `.runtime/ai4finance/comparisons/comparison-20260830-225225.{json,md}`: generated a 2-candidate sandbox-local comparison report; user clarified this is not the desired main MKF comparison.
- `HANDOFF.md`: added this handoff entry.

### Behavior / Logic Changes
- No production entrypoint, production YAML, scanner wrapper, output latest pointer, broker, order, leverage, or live-execution behavior changed.
- The sandbox chain is runnable without importing `src/ashare_edge_scout`, calling `main.sh`, calling `mkf.sh`, reading production YAML, or running main-flow pytest files.
- The only project data/key inputs used by the sandbox comparison are `PFrontStockData/` and `Key/ts.key`; sandbox configs/prompts/scripts live under `experiments/ai4finance/`.
- `build-evidence` currently selects candidates from recent adjusted parquet bars using sandbox-local simple metrics. This is a sandbox test input builder, not the production MKF selector.
- `replay_ai.py` catches external ts AI response interruptions such as `http.client.IncompleteRead` and records the failure per candidate so a long replay can still produce an output file.

### Validation
- Ran `experiments/ai4finance/amkf.sh build-evidence --top 3 --scan-limit 60` -> wrote `.runtime/ai4finance/evidence-packs/evidence-20260830-224651/evidence.json`.
- Ran `experiments/ai4finance/amkf.sh replay-baseline <evidence.json> --top 2` -> 2/2 schema valid, no request errors, no forbidden-term rows.
- First `replay-experiment <evidence.json> --top 2` hit external ts response interruption: `http.client.IncompleteRead`; updated replay script to catch this class of failure.
- Re-ran `experiments/ai4finance/amkf.sh replay-experiment <evidence.json> --top 2` -> 2/2 schema valid, no request errors, no forbidden-term rows.
- Ran `experiments/ai4finance/amkf.sh compare-local <baseline reviews.json> <experiment reviews.json>` -> comparison shows both runs schema_valid_count=2, request_error_count=0, forbidden_term_rows=0, forbidden_key_rows=0; avg_confidence baseline 0.75 vs experiment 0.65.
- Ran `experiments/ai4finance/amkf.sh self-check` -> `self_check: ok`.
- Ran `bash -n experiments/ai4finance/amkf.sh`.
- Ran `python -m py_compile` for the three sandbox scripts.
- Ran `git diff --check`.
- Confirmed protected production-file diff check produced no paths for `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, and `yaml/news_ai_review.yaml`.
- Validation environment: local `.venv` as the Python execution environment; no remote backtest was run and no full 23-candidate replay was run yet.

### Risks / Review Notes
- The 2-candidate replay only proves the isolated comparison pipeline runs; it does not prove AI4Finance prompt effectiveness.
- Because `build-evidence` is sandbox-local and not the MKF selector, its smoke-test comparison is not the user-requested branch-plan vs main MKF comparison.
- User clarified the real first step is to implement the AI4Finance correction plan inside `experiments/ai4finance/` only. Do not run larger sandbox-local A/B as if it answered the main MKF comparison question.
- Hard boundary from the user: all corrections must stay inside `experiments/ai4finance/`; do not modify, call, or reuse main-branch files except `PFrontStockData/` and `Key/ts.key`.

## Current Task: Add isolated AMKF sandbox runner (2026-08-30)

### Changed Files
- `experiments/ai4finance/amkf.sh`: added an isolated AI4Finance MKF sandbox runner with `help`, `status`, `guard`, `init-yaml`, and `self-check` commands.
- `experiments/ai4finance/yaml/ai_providers.yaml`: added sandbox-local ts AI provider config using `http://ts.dorisw.kdns.fr:18090/v1`, model `Qwen3.8-27B-oQ4e-mtp`, and project key path `../../../Key/ts.key`.
- `experiments/ai4finance/yaml/mkf_ai_review_sandbox.yaml`: added sandbox-local review prompt/config. It is self-contained and does not reference production YAML.
- `experiments/ai4finance/yaml/mkf_news_context_sandbox.yaml`: added sandbox-local empty news context.
- `experiments/ai4finance/configs/ai4finance_mkf_experiment.yaml`: updated boundaries so the only allowed external project inputs are `PFrontStockData/` and `Key/ts.key`.
- `docs/research/ai4finance-production-integration-plan.md`, `experiments/ai4finance/README.md`, and `experiments/ai4finance/prompts/README.md`: updated sandbox documentation to remove main-flow reuse assumptions.
- `HANDOFF.md`: added this handoff entry.

### Behavior / Logic Changes
- No production entrypoint or MKF runtime behavior changed.
- `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, and `yaml/news_ai_review.yaml` were intentionally not modified.
- Per user correction, the AI4Finance test branch must not reuse main-branch project files except stock data and `Key/ts.key`; the runner no longer includes commands that run `main.sh`, `mkf.sh`, or main-flow pytest files.
- `amkf.sh guard` refuses to continue if protected production entry/config files have working-tree changes.
- `amkf.sh self-check` verifies sandbox-local config files exist, `PFrontStockData/` and `Key/ts.key` exist, and sandbox config/YAML do not reference production YAML, normal entrypoints, or main tests.
- Runtime outputs remain directed to `.runtime/ai4finance/`; no production latest pointer is written.

### Validation
- Ran `experiments/ai4finance/amkf.sh status` -> protected files clean.
- Ran `experiments/ai4finance/amkf.sh self-check` -> `self_check: ok`.
- Ran `bash -n experiments/ai4finance/amkf.sh`.
- Ran `git diff --check`.
- Confirmed `git diff --name-only -- main.sh mkf.sh scripts/edge_scout_scan.sh yaml/mkf_ai_review.yaml yaml/news_ai_review.yaml` produced no paths.
- Confirmed `experiments/ai4finance/configs` and `experiments/ai4finance/yaml` contain no references to production YAML, normal entrypoints, or main-flow tests. Allowed external references are `PFrontStockData/` and `Key/ts.key` only.
- Validation environment: local Mac `.venv` for shell/YAML/sandbox checks only; no backtest or AI replay was run.

### Risks / Review Notes
- This is sandbox scaffolding only; it does not yet implement evidence-pack building or AI replay.
- Do not add commands that call `main.sh`, `mkf.sh`, production YAML, `scripts/edge_scout_scan.sh`, or main-flow tests unless the user explicitly relaxes the isolation rule.
- If future sandbox code needs scanner/review logic, copy or implement experiment-local wrappers under `experiments/ai4finance/` instead of importing main-flow entrypoints/configs; continue allowing only `PFrontStockData/` and `Key/ts.key` as external project inputs.
- No live broker login, live order submission, leverage, unattended real-money execution, target price, position sizing, stop-loss/take-profit, return promise, or BUY/HOLD/AVOID production prompt behavior was added.

## Current Task: Compare AI4Finance sandbox branch against main (2026-08-30)

### Changed Files
- `.runtime/ai4finance/comparisons/main-vs-ai4finance-20260830-220201.md`: runtime comparison report for focused regression tests on AI4Finance branch vs `main`.
- `.runtime/ai4finance/comparisons/main-vs-ai4finance-help-20260830-220355.md`: runtime comparison report for `main.sh`/`mkf.sh` help output.
- `.runtime/ai4finance/logs/ai4finance-branch-tests-20260830-220201.log` and `.runtime/ai4finance/logs/main-tests-20260830-220201.log`: runtime test logs.
- `HANDOFF.md`: added this comparison handoff entry.

### Behavior / Logic Changes
- No production entrypoint or MKF runtime behavior changed.
- AI4Finance branch HEAD and `main` HEAD are both `37beb16 Checkpoint MKF AI review production prompt work`.
- Current AI4Finance branch differences from `main` are only uncommitted sandbox scaffolding and `HANDOFF.md`; no diffs in `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, or `yaml/news_ai_review.yaml`.
- Sandbox files remain isolated from normal `main.sh` / `mkf.sh` command paths.

### Validation
- Ran on AI4Finance branch: `.venv/bin/python -m pytest tests/test_main_script.py tests/test_mkf_ai_review.py -q` -> `47 passed in 44.80s`.
- Temporarily stashed sandbox WIP, switched to `main`, and ran the same command -> `47 passed in 44.73s`.
- Restored AI4Finance branch WIP after main comparison.
- Compared `./main.sh help` output between `main` and AI4Finance branch: identical.
- Compared `./mkf.sh help` output between `main` and AI4Finance branch: identical.

### Risks / Review Notes
- The runtime comparison reports are under `.runtime/ai4finance/` and are not intended for commit unless the user explicitly wants persisted evidence.
- Continue keeping AI4Finance sandbox work outside `main.sh`, `mkf.sh`, formal YAML, and production output paths until a separate promotion decision.

## Current Task: Create isolated AI4Finance integration sandbox skeleton (2026-08-30)

### Changed Files
- `docs/research/ai4finance-production-integration-plan.md`: added the sandbox plan, boundaries, reference value, evaluation rubric, and promotion gate.
- `experiments/ai4finance/README.md`: added sandbox purpose, non-goals, runtime-output rules, and promotion rule.
- `experiments/ai4finance/configs/ai4finance_mkf_experiment.yaml`: added sandbox-only config documenting inputs, runtime output roots, boundaries, and target-timeout evaluation method.
- `experiments/ai4finance/prompts/README.md`: added prompt-sandbox rules and forbidden production-promotion content.
- `experiments/ai4finance/reports/README.md`: added report-output guidance.
- `HANDOFF.md`: added this handoff entry.

### Behavior / Logic Changes
- No production entrypoint or MKF runtime behavior changed.
- `main.sh`, `mkf.sh`, `scripts/edge_scout_scan.sh`, `yaml/mkf_ai_review.yaml`, and `yaml/news_ai_review.yaml` were intentionally not modified.
- The new sandbox is discussion/experiment scaffolding only. It is not called by the normal MKF flow and does not write production outputs.
- The sandbox explicitly forbids live broker login, live order submission, leverage, unattended real-money execution, BUY/HOLD/AVOID production labels, target prices, position sizing, stop-loss/take-profit instructions, or return promises.
- Recommended next exact action, if continuing implementation, is to add read-only sandbox scripts under `experiments/ai4finance/` that write only to `.runtime/ai4finance/`: evidence-pack builder, replay runner, and output evaluator.

### Validation
- Confirmed current branch before changes: `ai4finance-production-integration`.
- Confirmed no production entrypoint diffs after skeleton creation: `git diff --name-only -- main.sh mkf.sh scripts/edge_scout_scan.sh yaml/mkf_ai_review.yaml yaml/news_ai_review.yaml` produced no paths.
- Ran focused regression tests: `.venv/bin/python -m pytest tests/test_main_script.py tests/test_mkf_ai_review.py -q` -> `47 passed in 46.44s`.
- Ran whitespace check after handoff update: `git diff --check`.

### Risks / Review Notes
- Keep sandbox outputs in `.runtime/ai4finance/`; do not write experimental outputs to `output/edge_scout/latest.json` or production latest pointers.
- Do not wire sandbox commands into `main.sh` or `mkf.sh` unless the user explicitly requests a promotion step after validation.
- Any future production promotion must be a separate change with regression tests and explicit boundary review.

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
