# Reviewer Handoff

## Task: Commit structured NCN checkpoint

### Changed Files
- Staged the accumulated NCN package extraction, portfolio/demo/paper and PMKF/MKF research integration, centralized AI configuration, operator documentation, preregistration/evidence set, and root-JSON migration as one coherent checkpoint.
- Created branch `chore/ncn-structured-research-checkpoint` because commits are not made directly on `main`.
- Intentionally excluded imported reference material and local session artifacts: `CNstock-main/`, `CNstock-main.zip`, `session-ses_ff63.md`, and `session-ses_ffae.md`.

### Behavior / Logic Changes
- This entry records Git packaging only; runtime and research behavior are described in the task-specific entries below.

### Validation
- Staged snapshot contains 255 intended files; `CNstock-main/`, `CNstock-main.zip`, session notes, local Claude state, credentials, runtime data, and output directories are excluded.
- Staged path/credential-marker review found only documented environment-variable names, key-file paths, and interactive password handling; no credential value is staged.
- `git diff --cached --check` passed.
- Full local suite passed immediately before commit: `497 passed, 3 skipped` in 56.16 seconds.
- The immediately preceding migration validation also passed on Doris (`4 passed`) and locally (`40 passed`).

### Risks / Review Notes
- The checkpoint is intentionally broad because the working tree contains interdependent package extraction, compatibility aliases, documentation, tests, configuration, and evidence accumulated across prior authorized phases.
- No push is authorized by this commit request.
- Next exact action: inspect the staged snapshot for secrets and unintended imported files, then commit with the required co-author trailer.

## Task: Migrate root-level research JSON artifacts

### Changed Files
- Moved 20 root-level research JSON artifacts into versioned `docs/research/results/<topic>/` and `docs/research/archive/legacy/` paths; the three Git-tracked reports were moved with Git rename preservation.
- Added `docs/research/README.md` defining the evidence, legacy archive, ignored exploratory output, and runtime-state taxonomy.
- `scripts/probe_cninfo_repurchase_counts.py`: the default sample now resolves to `docs/research/results/stage1/precision70-stage1-2021-2026.json` through a named constant.
- `scripts/remote_test_env.sh`: the remote study remains in `.runtime/`, while `study_fetch` now defaults to the structured strategy evidence path and creates its destination parent directory.
- Updated direct preregistration and archived-handoff references for Precision70, RSRS/MHPG, and target-touch evidence.
- `tests/test_standalone_boundary.py`, `tests/test_remote_test_env.py`, and `tests/test_probe_cninfo_repurchase_counts.py`: added regression coverage for root-artifact absence and the two structured defaults.

### Behavior / Logic Changes
- Root-level JSON research artifacts are no longer a supported storage location.
- Current/reviewable study evidence is versioned under `docs/research/results/`; legacy next-day v1 evidence lives under `docs/research/archive/legacy/`.
- Ad hoc/smoke reports should use ignored `output/edge_scout/research/`; active jobs remain under `.runtime/`.
- No scanner, selection, AI, Web, Demo/Paper, publication, or strategy threshold behavior changed.

### Validation
- Root-path and JSON integrity passed: all 20 migrated basenames are absent from the repository root, and all 20 `docs/research/**/*.json` files parse successfully. A comprehensive active-reference scan found no remaining consumer that expects a migrated artifact at root; remaining bare basenames are intentional regression checks or historical records.
- WSL was attempted first; TCP port 22 accepted the connection but SSH closed before command execution, so it could not run tests.
- Doris was attempted second with its required `.venv-doris/bin/python` (Python 3.13.15); focused default-path tests passed (`4 passed`). Only the two scripts and two focused tests required by that run were synchronized, without destructive sync or data/output changes.
- Local fallback focused suite passed (`40 passed`): migration boundaries, remote fetch default, CNInfo probe default, Precision70, and repurchase classification.
- `py_compile`, shell syntax for the affected/controller scripts, moved-JSON parsing, root-artifact guard, and `git diff --check` passed.
- Migration-specific Git status was reviewed: the three previously tracked reports are recorded as moved/added at their structured paths in the current index state; the remaining migrated reports and supporting files are intentionally untracked pending the user's normal commit workflow.

### Risks / Review Notes
- Historical handoff entries retain their original text unless a direct path reference was actively misleading; do not treat historical command transcripts as current invocation guidance.
- `pmkf-mkf-t5-quality-smoke.json` is retained as migrated historical evidence under `docs/research/results/pmkf-mkf/`; new smoke output must use ignored `output/edge_scout/research/`.
- No validation requiring market data or strategy recomputation was needed because this migration changes artifact locations and defaults only.
- Next exact action: review and commit the migration together with the intended broader working tree; do not regenerate research JSON at repository root.

## Task: Store the shareable NCN operator manual in repository documentation

### Changed Files
- Added `docs/USER_MANUAL.html`: self-contained, theme-aware, responsive offline HTML rendering of the Chinese NCN operator manual, with sidebar navigation and print styles.
- `docs/USER_MANUAL.md`: links to the browser-openable HTML version.
- `README.md`: links to both Markdown and offline HTML operator manual formats.
- `HANDOFF.md`: replaced the Artifact-publishing blocker with the completed repository-documentation delivery.
- No source, configuration, AI, scan, selection, Web, or output behavior changed.

### Behavior / Logic Changes
- The shareable manual is now a versioned repository document rather than a Claude Artifact. It can be opened locally from `docs/USER_MANUAL.html` without a claude.ai login or external assets.

### Validation
- Read `AGENTS.md`, relevant prior handoff entries, and the full HTML source before copying.
- Confirmed `docs/USER_MANUAL.html` is self-contained, begins with title `NCN 操作手册`, contains no script tag, and has valid UTF-8 content.
- `git diff --check -- README.md docs/USER_MANUAL.md docs/USER_MANUAL.html HANDOFF.md` passed.

### Risks / Review Notes
- The HTML and Markdown manuals contain operational facts that may need synchronized updating when commands, AI configuration, or safety boundaries change.
- No Artifact publication remains pending.

## Task: Synchronize README with current NCN scope

### Changed Files
- `README.md`: replaced obsolete read-only-scanner-only positioning with the current phased production-adjacent research/demo/paper/PMKF/AI/audit scope; added the operator manual link; corrected Web description to include Demo Portfolio and Paper Monitor while retaining no-broker/no-live-order boundaries.
- `HANDOFF.md`: recorded the documentation synchronization.
- No source, config, scan, selection, AI, Web runtime, or output behavior changed.

### Behavior / Logic Changes
- None. README now matches current governance and implementation rather than the earlier scanner-only phase.

### Validation
- Searched README for the obsolete phrases (`does not contain`, `does not expose portfolio`, old standalone scanner tagline); none remain.
- Confirmed `docs/USER_MANUAL.md` exists and the README link resolves locally.
- `git diff --check -- README.md docs/USER_MANUAL.md HANDOFF.md` passed.

### Risks / Review Notes
- README remains a concise overview; detailed operating procedures belong in `docs/USER_MANUAL.md`.
- Next exact action: review both documents together; Artifact publishing remains pending until a claude.ai subscription login is available.

## Task: Write the NCN operator user manual

### Changed Files
- `docs/USER_MANUAL.md`: new Chinese user manual covering setup, command entrypoints, daily/SMC/MKF workflows, unified AI config, Web, Demo/Paper, audit, outputs, operations, troubleshooting, safety, and quick reference.
- `/tmp/ncn-user-manual.html`: local self-contained, theme-aware shareable rendering with sidebar navigation, responsive tables, print styles, and the same operational boundaries.
- `HANDOFF.md`: recorded documentation delivery and publish limitation.
- No source, config, model, scan, selection, watchlist, publication, or runtime behavior changed.

### Behavior / Logic Changes
- None. Documentation reflects the current production-adjacent research/demo/paper authorization and explicitly distinguishes research from broker/live execution.
- The manual documents that `--top` limits terminal display only, central AI switching occurs only in `yaml/ai_providers.yaml`, and AI smoke uses explicit isolated fixtures.

### Validation
- Read current AGENTS/HANDOFF/README, command help, strategy YAML and central AI YAML before drafting.
- Manual validation passed: 776 Markdown lines, final newline, required boundary flags and current `494 passed, 3 skipped` baseline present; HTML title/theme/responsive markers present; `git diff --check` passed for repository documentation.
- Artifact publish was attempted but blocked because this session authenticates with `ANTHROPIC_AUTH_TOKEN` rather than a claude.ai subscription login. No auth settings were changed.

### Risks / Review Notes
- README still contains older top-level scope wording that says portfolio/paper are absent; the user manual uses current governance and implementation instead. Update README separately if it should become the authoritative overview.
- The HTML remains at `/tmp/ncn-user-manual.html`; publishing later requires a claude.ai login with Artifact access.
- Next exact action: review `docs/USER_MANUAL.md`; optionally update README scope wording and publish the existing HTML after login.

## Task: Repair Doris authentication and complete bounded AI smoke

### Changed Files
- Local ignored `Key/ts.key`: securely synchronized from Doris oMLX `auth.api_key`; secret content was never printed or committed, and local permissions are `0600`.
- `yaml/ai_providers.yaml`: added `chat_template_kwargs.enable_thinking=false` to the selected Doris Qwen backend so MKF/news receive final JSON rather than long reasoning output.
- `scripts/smoke_ai_provider.py`: accepts JSON objects embedded in Markdown/prose by extracting the first complete object, matching business parser behavior.
- `HANDOFF.md`: recorded authentication, response-contract diagnostics, bounded smoke artifacts, and validation.

### Behavior / Logic Changes
- Doris authentication now succeeds with the server's existing API key; the oMLX service and server configuration were not changed or restarted.
- All AI workflows continue to use central `local_finance` / `Qwen3.8-27B-4bit` through `http://ts.dorisw.kdns.fr:18090/v1`.
- Qwen thinking is disabled at the central backend level for structured NCN review prompts; this applies consistently to MKF and SMC/news.
- Smoke reviews used isolated three-candidate fixtures and `.runtime/ai-smoke` output roots; official selections, watchlist, latest, prospective archive, and formal review roots were not modified.

### Validation
- Credential SHA-256 mismatch was confirmed before synchronization; synchronized local key hash matches Doris oMLX `auth.api_key`. No key value was exposed.
- `/v1/models` passed in ~0.05-0.14s, returned 11 models, and listed `Qwen3.8-27B-4bit`.
- Tiny JSON chat passed twice after parser hardening in ~1.3-1.7s, with the configured model returned.
- Initial MKF calls with thinking enabled returned `{}` or long truncated reasoning; a one-candidate diagnostic with `enable_thinking=false` passed the existing MKF parser. No review rule was weakened.
- Isolated MKF smoke: 3/3 AI successes, states `priority_research=1`, `standard_research=2`, no unavailable/risk states; manifest hashes, central provider/model/provenance, secret absence, forbidden action labels/keys all passed.
- Isolated SMC/news smoke: 3/3 AI successes, states `priority_review=2`, `standard_review=1`, no unavailable/risk-excluded states; manifest hashes, provider/model/provenance and secret absence passed.
- Official SMC `human_review_summary.csv` timestamp remained 2026-08-21; only the isolated 2026-08-22 fixture summary was written.
- Final focused suite passed (`76 passed`); full suite passed (`494 passed, 3 skipped`); compileall, shell syntax and `git diff --check` passed.

### Risks / Review Notes
- The first attempted `--top 10` MKF smoke was stopped because `--top` only limits terminal display and would process all 49 candidates. It produced no review run; subsequent smoke used explicit three-row fixture manifests.
- Single MKF calls took roughly 5-60 seconds depending on JSON/thinking mode; the successful three-candidate run completed within the bounded command timeout. Keep 120s provider timeout.
- `chat_template_kwargs` is provider-specific OpenAI-compatible metadata; other backends do not inherit it because it is configured only on `local_finance`.
- Continue using explicit selection-run fixtures for future smoke. Do not use `--top` as a processing limit.
- Next exact action: review smoke artifacts under `.runtime/ai-smoke`; only then consider a larger fixed-candidate validation or normal AI review run.

## Task: Centralize all NCN AI provider/model control

### Changed Files
- Renamed `yaml/mkf_ai_providers.yaml` to the single authoritative `yaml/ai_providers.yaml` using schema `ncn_ai_providers_v1`.
- Added `src/ashare_edge_scout/ai_providers.py` for shared provider validation, key resolution, error redaction, OpenAI-compatible transport, and client construction.
- Updated `yaml/mkf_ai_review.yaml` and `yaml/news_ai_review.yaml` to reference only the central provider file; removed inline news provider/model configuration.
- Refactored `mkf_ai_review.py` and `news_ai_review.py` to share provider/client logic while retaining workflow-specific prompts, parsers, fail-closed rows, and immutable artifacts.
- Added `scripts/smoke_ai_provider.py` for no-publication `/models` and optional tiny JSON chat smoke.
- Added `tests/test_ai_provider_config.py`; extended MKF/news tests for central config, override rejection, shared provider identity, credential precedence, smoke gating, and summary provenance.
- Updated README and HANDOFF. No selection, watchlist, latest, prospective archive, or candidate artifact was modified.

### Behavior / Logic Changes
- One edit in `yaml/ai_providers.yaml` now switches every AI-backed NCN workflow. Business YAML files cannot override provider, model, endpoint, credentials, timeout, temperature, seed, response format, or enabled state.
- Active providers in the central inventory are Doris `local_finance` (`Qwen3.8-27B-4bit`) and DeepSeek (`deepseek-v4-flash`). Disabled templates include DeepSeek Chat/Pro, legacy LM Studio finance 8B, Tongyi, Kimi, and Zhipu.
- Doris base URL is explicitly `http://ts.dorisw.kdns.fr:18090/v1`; the loader strips trailing slash only and never changes scheme/path or silently falls back.
- Key precedence is non-empty `api_key_env`, then non-empty `api_key_file_env` path, then configured ignored key file. Empty env values no longer mask key-file fallback. Inline secrets are rejected.
- Unknown/disabled/missing providers or credentials fail closed. Global `enabled:false` is the only intentional no-client state. Provider failures never switch silently to another backend.
- Both MKF and SMC/news summaries now bind central config path/SHA/schema/provider/model/client status and request defaults without writing secrets or base URLs.

### Validation
- Shared provider core tests passed (`10 passed`); focused unified MKF/news/main suite passed (`76 passed`).
- Summary provenance suite passed (`52 passed`).
- Full local suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest -q --tb=short` (`494 passed, 3 skipped`).
- Compileall, shell syntax, and `git diff --check` passed.
- Real no-publication smoke used the central loader and explicit Doris `/v1` endpoint. `/v1/models` returned `401 Invalid API key`, exit code `3`; the smoke stopped before chat as designed. No candidate AI request or publication was made.

### Risks / Review Notes
- Doris authentication remains the only blocker. Fix `EDGE_SCOUT_LOCAL_AI_API_KEY` or `Key/ts.key` on the service side/client side, then rerun `scripts/smoke_ai_provider.py --models-only`.
- Do not run chat or candidate review until `/models` succeeds. After auth, run tiny JSON chat, then explicit-selection-run SMC/news (5) and MKF (10) reviews in isolated output roots.
- DeepSeek remains configured but is not a runtime fallback; switching requires editing central `provider` deliberately.
- Historical HANDOFF references to `mkf_ai_providers.yaml` describe prior state and were intentionally not rewritten.
- Next exact action: resolve Doris 401 authentication, rerun models/chat smoke, then resume bounded candidate review tasks 10-12.

## Task: Probe Doris AI connectivity and identify unified-config requirement

### Changed Files
- `HANDOFF.md`: recorded live connectivity findings and the new requirement for one central AI control YAML.
- No provider YAML, source, selection, watchlist, publication, or output artifact was changed by the probe.

### Behavior / Logic Changes
- None. The planned MKF/SMC small-sample reviews were paused before candidate calls.
- User requirement clarified: every AI-backed NCN feature must consume one central provider/model control YAML so one edit switches all AI calls.

### Validation
- Existing configured `https://ts.dorisw.kdns.fr:18090` failed TLS with `SSL: WRONG_VERSION_NUMBER`, indicating that port serves plain HTTP rather than HTTPS.
- `http://ts.dorisw.kdns.fr:18090/models` reached the server but returned 404; `http://ts.dorisw.kdns.fr:18090/v1/models` reached the OpenAI-compatible API but returned 401 with the current configured credential.
- No key content was logged. No `/chat/completions` request or candidate AI smoke was run after authentication failed.

### Risks / Review Notes
- Correct endpoint shape is likely `http://ts.dorisw.kdns.fr:18090/v1`; authentication must be fixed before AI smoke.
- Current architecture still has separate MKF and SMC/news provider config loaders; manually keeping two YAML files aligned does not satisfy the user's one-file switching requirement.
- Next exact action: design and implement a shared AI provider loader/YAML referenced by all AI feature configs, then resolve Doris authentication and resume bounded smoke tests.

## Task: Switch all NCN AI review defaults to Doris Qwen

### Changed Files
- `yaml/news_ai_review.yaml`: changed SMC/news AI default provider from DeepSeek to Doris local, endpoint `https://ts.dorisw.kdns.fr:18090`, model `Qwen3.8-27B-4bit`, key file `Key/ts.key`, and env override `EDGE_SCOUT_LOCAL_AI_API_KEY`.
- `tests/test_news_ai_review.py`: added repository-config assertions for the Doris endpoint/model/key resolution.
- `HANDOFF.md`: recorded the provider switch and validation state.
- MKF provider config was already using the same Doris endpoint/model and was not changed.

### Behavior / Logic Changes
- Both MKF AI committee and SMC/news AI review now default to the Doris-hosted OpenAI-compatible `Qwen3.8-27B-4bit` model.
- Credential priority remains environment override first, then ignored local `Key/ts.key`; no secret content was read or logged.
- DeepSeek definitions remain available as explicit fallback configurations but are no longer the default provider.

### Validation
- Focused AI/config/main-script suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_news_ai_review.py tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`61 passed`).
- Python compile, shell syntax, and `git diff --check` passed.
- Confirmed `Key/ts.key` exists and both provider loaders resolve to Doris without reading/logging key content.
- No real `/chat/completions` request was sent, so endpoint path, TLS/auth, model availability, JSON discipline, and latency are not yet live-validated.

### Risks / Review Notes
- If Doris expects `/v1/chat/completions` rather than `/chat/completions`, add `/v1` to both configured base URLs after a bounded connectivity smoke.
- Keep DeepSeek definitions until Doris live smoke validates connectivity and contract compliance; do not silently fall back on runtime error because AI review must fail closed.
- Next exact action: run a bounded no-publication connectivity/model smoke, then a fixed small-candidate AI review smoke before full review runs.

## Task: Inventory root-level research JSON artifacts

### Changed Files
- `HANDOFF.md`: recorded the read-only root JSON inventory and migration recommendation.
- No JSON file, generator script, documentation reference, Git index state, or output path was changed.

### Behavior / Logic Changes
- None. The project root contains 20 JSON research artifacts generated by evaluation scripts through caller-supplied `--output` paths; they are not runtime configuration.
- Three are Git-tracked (`joint-strategy-2021-2026.json`, `signal-study-2018-2026.json`, `walk-forward-strategy-2023-2026.json`); the remaining 17 are untracked and not ignored.
- Recommended generated-artifact taxonomy: completed reports under `output/edge_scout/research/`, active checkpoint/log/pid state under `.runtime/research/`, and legacy non-reproducible schema artifacts under an archive subdirectory.

### Validation
- Listed all root `*.json`, inspected size/schema/top-level keys, checked `git check-ignore`/`git ls-files`, read `.gitignore`, and traced every artifact to its generator, `--output` contract, and exact path references in scripts/docs/HANDOFF.
- No tests or writes were run because this was a read-only inventory.

### Risks / Review Notes
- Do not move the three tracked reports into ignored `output/` without deciding whether their evidence should remain version-controlled; tracked evidence should instead move to `docs/research/results/` if version retention is required.
- `precision70-stage1-2021-2026.json` is the default sample input for `scripts/probe_cninfo_repurchase_counts.py`; moving it requires updating that default and two preregistration documents.
- `nextday-validation-2021-present.json` uses legacy `ncn_nextday_validation_v1` semantics and current code cannot exactly regenerate it; archive it separately from current v2 next-day-direction results.
- `signal-study-2018-2026.json` is fetched by `scripts/remote_test_env.sh`; moving it requires updating remote result/log/pid/fetch defaults.
- Exact PMKF/MKF, RSRS, Shengbei/KDJ, Futu and target-touch references in HANDOFF/docs/control scripts must be updated with any move.
- Next exact action: ask the user whether the three tracked reports should remain version-controlled; then plan or execute a path-aware migration rather than moving files blindly.

## Task: CNstock-inspired scan/publication/audit refactor Phase 4b

### Changed Files
- Added `src/ashare_edge_scout/publication/` with the unchanged `publish_scan_results` implementation; flat `publisher.py` is now a `sys.modules` alias.
- Added `src/ashare_edge_scout/audit/prospective.py`; flat `prospective_audit.py` is now a module alias, and `scripts/audit_prospective_watchlist.py` imports the canonical path.
- Added `src/ashare_edge_scout/scan/scanner.py`; flat `scanner.py` is now a module alias.
- Scanner implementation retains all public/private helpers and now imports canonical data/signals/publication paths. Scanner-owned `_write_manifest` and `_write_latest` remain unchanged in scanner.
- Added publisher/audit/scanner alias identity and scanner private-symbol identity assertions to `tests/test_standalone_boundary.py`.
- Added the previously missing module-level `get_parquet_latest_date_coverage_details` scanner import required by the existing freshness branch.
- Did not move `operations.py`, SMC/news prospective/replay, portfolio event audit, data audit, selectors, AI/news modules, Web static assets, or CLI/shell entrypoints.

### Behavior / Logic Changes
- Intended behavior is unchanged; this is a package-boundary refactor only.
- Scanner orchestration now lives under `ashare_edge_scout.scan`; immutable run publication under `ashare_edge_scout.publication`; prospective maturity audit under `ashare_edge_scout.audit`.
- Old flat imports remain the same module objects as canonical implementations, preserving private imports and monkeypatch behavior.
- Publication fail-closed gates, artifact filenames/headers/serialization, manifest/source hashes, prospective snapshot schema, atomic run/latest publication, and latest run-directory semantics remain unchanged.
- Prospective canonical selection, tamper detection, data-revision/pending handling, audit schema, and evidence gates remain unchanged.
- No CNstock runtime dependency, broker login/order submission, leverage, unattended execution, `/force_buy`, real account IDs, or real-money P&L was added.

### Validation
- Phase 4b focused baseline passed: `56 passed, 3 skipped`.
- Publication gate passed: `40 passed`; flat/canonical publisher module identity and compile passed. Existing publisher/audit tests preserved file set, manifest hashes, prospective source hashes, atomic/latest and fail-closed contracts.
- Audit gate passed: `35 passed`; audit CLI help, flat/canonical module and public symbol identity, SMC/news deferred regressions, and compile passed.
- Scanner gate passed: `56 passed, 3 skipped`; scanner CLI helps, flat/canonical module identity, public/private helper identity, old monkeypatch paths, and compile passed.
- Full local suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest -q --tb=short` (`478 passed, 3 skipped`).
- Static checks passed: compileall for src/scripts/tests, JS syntax, shell syntax, and `git diff --check`.
- Local Web smoke passed for health/demo/paper/PMKF; live orders and production remained false; `/force_buy` and `/api/force_buy` returned 404.
- Local scanner smoke successfully used the moved scanner/publication imports and fail-closed on the known local data issue `missing_value: Record 103 field 'turn' must not be None`; no validation was weakened.
- Remote-first: WSL SSH timed out during banner exchange and was unavailable. Doris temporary `~/NCN-claude-validation-phase4b` used the validated `.venv-doris`; full suite passed (`478 passed, 3 skipped`) plus compileall and shell syntax.

### Risks / Review Notes
- Keep flat scanner/publisher/audit aliases until a later deliberate compatibility removal cycle.
- Scanner private helpers are current script/test contracts; do not rename or hide them without a separate migration.
- Do not consolidate scanner `_write_manifest`/`_write_latest` into publication without proving active/dead paths and artifact parity.
- `operations.py` remains a mixed freshness/locking/atomic-write/retention boundary and was intentionally deferred.
- `smc_news_prospective.py` remains mixed archive/validation/audit/write logic and was intentionally deferred rather than misclassified under audit.
- Existing local `sh.600000` data has missing `turn` at record 103; do not weaken data validation.
- Next exact action: review Phase 4b before planning any AI/research/operations decomposition; no further mechanical package move is recommended without a new steelman/design pass.

## Task: CNstock-inspired data/signals base-layer refactor Phase 4a

### Changed Files
- Added `src/ashare_edge_scout/data/` with implementations for daily bars, data sources, intraday data, data contracts, and research reference prices.
- Added `src/ashare_edge_scout/signals/` with implementations for candle rules/patterns, indicators, confirmations, entry plan, candle timing/confirmation, start signals, discovery, and signal scoring.
- Converted all moved flat modules into `sys.modules` module aliases so old imports, module identity, and monkeypatch behavior continue to target the new implementations.
- Updated runtime consumers to direct `data.*`/`signals.*` imports: admission, scanner, publisher, selectors, AI review, research modules, PMKF candidates, portfolio paper snapshot, Web app/routes, and selected scripts.
- Kept scanner/admission at root and preserved scanner/admission module-level patch names.
- Made `pmkf_mkf/__init__.py` lazy to remove an eager-import cycle exposed by the new signals package.
- Added representative old/new module identity assertions to `tests/test_standalone_boundary.py`.
- Did not move operations, calendar, scanner, admission, publisher, selectors, AI modules, Web static assets, or script entrypoints.

### Behavior / Logic Changes
- Intended runtime behavior is unchanged; this is a package-boundary refactor only.
- Data loading/contracts/reference prices now live under `ashare_edge_scout.data`; candle/timing/discovery/scoring logic now lives under `ashare_edge_scout.signals`.
- Old flat paths remain module aliases and are the same module objects as the new paths.
- Scanner selection rules, hard gates, tiering, publication schema, Web routes, demo/paper semantics, and PMKF/MKF research behavior remain unchanged.
- No CNstock runtime dependency, broker login/order submission, leverage, unattended execution, `/force_buy`, real account IDs, or real-money P&L was added.

### Validation
- Data baseline before edits: focused suite `43 passed`.
- Data hard-gate after migration: `63 passed`; all five data module alias identity checks passed; compile passed.
- Signals hard-gate initially exposed an import cycle through eager `pmkf_mkf/__init__.py`; after converting it to lazy exports, the signals/scanner suite passed (`125 passed, 3 skipped`) and all ten signal alias identities passed.
- Runtime consumer focused suite passed (`159 passed`); Web/compatibility suite passed (`49 passed`).
- Full local suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest -q --tb=short` (`478 passed, 3 skipped`).
- Static checks passed: full package/scripts compileall, JS syntax, shell syntax, and `git diff --check`.
- Local Web smoke passed for health/demo/paper/PMKF endpoints with `allow_live_order_submission=false`, `production_enabled=false`; `/force_buy` and `/api/force_buy` returned 404.
- Local scanner smoke `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh single-local sh.600000` successfully launched and completed the new import path; it fail-closed on the existing local data-quality issue `missing_value: Record 103 field 'turn' must not be None`, not an import/structure regression.
- Remote-first: WSL SSH timed out during banner exchange and was unavailable. Doris validation used temporary `~/NCN-claude-validation-phase4a`. Initial full run had four environment-only failures because the temp directory lacked `.venv/bin/python`; after linking `.venv` to the validated `~/NCN/.venv-doris`, the full Doris suite passed (`478 passed, 3 skipped`), plus compile and shell syntax checks.

### Risks / Review Notes
- Keep all flat module aliases until a deliberate later migration and at least one stable cycle.
- Do not split operations freshness/locking/retention yet; operations remains a mixed operational boundary.
- Keep scanner and admission at root until Phase 4b design explicitly handles their extensive monkeypatch/private-helper contracts.
- `reference_prices`, `signal_scoring`, and discovery are now structurally relocated but remain behaviorally unchanged; future edits must continue to run scanner/publisher/full-suite gates.
- Existing local `sh.600000` data has a missing `turn` field at record 103; do not weaken validation to make scanner smoke pass.
- Next exact action: review Phase 4a, then plan Phase 4b for scan/publication/audit boundaries rather than moving them mechanically.

## Task: CNstock-inspired gradual PMKF/MKF subpackage refactor Phase 3

### Changed Files
- Added `src/ashare_edge_scout/pmkf_mkf/__init__.py` with the public PMKF/MKF research surface.
- Moved implementations into `pmkf_mkf/core.py`, `features.py`, `research.py`, `candidates.py`, and `quality.py`.
- Converted flat `pmkf.py`, `pmk_features.py`, `research_mkf.py`, `mkf_candidate_selector.py`, and `research_pmkf_mkf_t5_quality.py` into module-alias compatibility wrappers. The alias approach preserves monkeypatch behavior for existing tests, not just symbol imports.
- Updated runtime consumers to use the new package directly: scanner/signal scoring/reference prices/candle confirmation/research Futu ranking/MKF AI review and Web PMKF/MKF routes.
- Updated `tests/test_research_web.py` to verify PMKF function identity through the new and flat paths.
- No CNstock runtime dependency, broker/order path, `/force_buy`, live trading, leverage, or real-money P&L was added.

### Behavior / Logic Changes
- PMKF core smoothing, PMK features, MKF research rules, candidate selection, and T+5 quality comparison now have a coherent `ashare_edge_scout.pmkf_mkf` domain boundary.
- Existing flat imports remain valid as module aliases; monkeypatches against old paths continue to affect the implementation module.
- Web PMKF/MKF dashboard continues to read precomputed reports or bounded single-code research data only; no all-universe Web scan was introduced.
- PMKF/MKF outputs remain research-only and do not become autonomous portfolio or execution authority.

### Validation
- Local Phase 3 focused suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_edge_scout_pmkf.py tests/test_edge_scout_pmk_features.py tests/test_research_mkf.py tests/test_mkf_candidate_selector.py tests/test_research_pmkf_mkf_t5_quality.py tests/test_mkf_ai_review.py tests/test_demo_portfolio_state.py tests/test_paper_trading_state.py tests/test_paper_trading_snapshot.py tests/test_research_web.py tests/test_research_web_demo_portfolio.py tests/test_research_web_paper.py tests/test_research_web_pmkf_mkf.py tests/test_standalone_boundary.py -q --tb=short` (`78 passed`).
- Local static checks passed: Python compile for PMKF/MKF package and wrappers; `node --check src/ashare_edge_scout/web_static/app.js`; shell syntax; `git diff --check`.
- Local Web smoke passed after `./scripts/edge_scout_web_control.sh restart`: health, demo status, paper status, PMKF/MKF summary and bounded single-code endpoint returned 200 with `allow_live_order_submission=false`.
- Remote-first validation: WSL SSH timed out during banner exchange and was unavailable. Doris `.venv-doris/bin/python` in temporary `~/NCN-claude-validation-pmkf` ran the same focused suite successfully (`78 passed`), plus PMKF/MKF Python compile and shell syntax checks.

### Risks / Review Notes
- Keep flat module aliases until scripts/tests are deliberately migrated and a stable cycle confirms direct `pmkf_mkf` imports.
- Do not move PMKF/MKF AI/news modules into this package unless their read-only, no-autonomous-decision boundary is preserved.
- Do not introduce CNstock PMKF thresholds as production or return claims; current artifacts remain research classification evidence only.
- Existing top handoff entries from other maintenance tasks were preserved below this entry.
- Next exact action: review the three subpackage boundaries (`web`, `portfolio`, `pmkf_mkf`) before planning Phase 4 data/scan/audit extraction.

## Task: Generalize NCN strategy rules into AI_Temp template

### Changed Files
- `/Users/artx/Local/Git/AI_Temp/AGENTS.md`: expanded the generic agent/OpenCode template with minimum-customization project identity, project efficiency strategy, generalized steelman gate, research/experiment preregistration, evidence quality, output/selection quality, validation, and handoff rules.
- `/Users/artx/Local/Git/AI_Temp/CLAUDE.md`: expanded the shorter Claude Code template with the same generalized NCN-derived strategy rules.
- `/Users/artx/Local/Git/AI_Temp/HANDOFF.md`: added a top handoff entry for the template update.
- `HANDOFF.md`: recorded this cross-repository template maintenance task.

### Behavior / Logic Changes
- `AI_Temp` is now designed so a new project mostly replaces `[PROJECT_NAME]`, `[PROJECT_DESCRIPTION...]`, and `[PROJECT_KEYWORDS...]`; optional domain/output/phase fields can be inferred or filled explicitly.
- NCN-specific strategy discipline was generalized into project-agnostic rules: improve the next concrete project decision, prefer smaller higher-quality selected outputs, require explainable selection/ranking logic, preregister experiments, stop failed directions, preserve evidence quality, and record autonomous negative results.
- Steelman gating now applies to strategy research, selection/ranking/watchlist logic, data validation design, backtest or experiment methodology, architecture changes, ambiguous bugs, security-sensitive work, production-adjacent changes, and conclusion-affecting changes.
- Project-specific NCN trading/governance boundaries were intentionally not copied into the generic template.
- No NCN source code, config, scanner/watchlist logic, tests, or runtime behavior changed.

### Validation
- Read NCN `AGENTS.md` and newest `HANDOFF.md` before work.
- Read the existing `/Users/artx/Local/Git/AI_Temp` template files before editing.
- Read back the changed top sections of AI_Temp `AGENTS.md`, `CLAUDE.md`, and `HANDOFF.md`.
- Ran a Python readability/whitespace/final-newline check over `/Users/artx/Local/Git/AI_Temp/AGENTS.md`, `CLAUDE.md`, and `HANDOFF.md`; it passed.

### Risks / Review Notes
- `AI_Temp` is inside a broader parent Git tree, so `git -C AI_Temp status` reports many unrelated parent-directory untracked paths and normal `git diff` does not show the untracked template content. Only the three listed AI_Temp template files were intentionally changed.
- Next exact action: when applying AI_Temp to another project, replace project name, description, and keywords first; fill optional domain/output/phase only if inference would be ambiguous.

## Task: CNstock-inspired gradual portfolio subpackage refactor Phase 2

### Changed Files
- Added `src/ashare_edge_scout/portfolio/__init__.py` as the public NCN portfolio/paper boundary.
- Moved implementations into `src/ashare_edge_scout/portfolio/demo.py`, `paper_state.py`, `paper_snapshot.py`, and `paper_risk.py`.
- Converted flat `demo_portfolio_state.py`, `paper_trading_state.py`, `paper_trading_snapshot.py`, and `paper_risk.py` into compatibility wrappers that re-export the new portfolio modules.
- Updated `src/ashare_edge_scout/web/app.py`, `web/routes/demo.py`, and `web/routes/paper.py` to use `ashare_edge_scout.portfolio` implementations directly.
- Updated `tests/test_research_web.py` to verify the new portfolio import path and flat-wrapper identity.
- No live broker/order path, `/force_buy`, CNstock import, web API contract, static asset, or shell entrypoint was changed.

### Behavior / Logic Changes
- Demo portfolio state, audit JSONL, paper status/history, paper data freshness, and paper risk normalization now have a CNstock-inspired `portfolio/` package boundary.
- Existing flat imports remain valid and resolve to the new implementations, minimizing downstream migration risk.
- Web runtime now imports portfolio behavior from the new package rather than the compatibility wrappers.
- Safety semantics remain unchanged: paper-only state, no broker connection, no live order submission, `production_enabled=false`, and no real account/P&L fields.

### Validation
- Local focused portfolio/Web suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_demo_portfolio_state.py tests/test_paper_trading_state.py tests/test_paper_trading_snapshot.py tests/test_edge_scout_config.py tests/test_research_web.py tests/test_research_web_demo_portfolio.py tests/test_research_web_paper.py tests/test_research_web_pmkf_mkf.py tests/test_standalone_boundary.py -q --tb=short` (`37 passed`).
- Local static checks passed: Python compile for portfolio, wrappers, Web modules; `node --check src/ashare_edge_scout/web_static/app.js`; shell syntax; `git diff --check`.
- Local Web smoke passed after `./scripts/edge_scout_web_control.sh restart`: health, demo portfolio list/status, paper status, and PMKF/MKF summary returned 200 with `allow_live_order_submission=false`.
- Remote-first validation: WSL SSH timed out during banner exchange and was unavailable. Doris main tree lacked the new test file, so code was synced to temporary `~/NCN-claude-validation-portfolio`; Doris `.venv-doris/bin/python` ran the same focused suite successfully (`37 passed`), plus Python compile and shell syntax checks.

### Risks / Review Notes
- Flat compatibility wrappers should remain until scripts/tests are deliberately migrated and a stable cycle confirms the new package paths.
- Do not add broker abstractions, virtual execution semantics, live account identifiers, order IDs, leverage, or unattended execution to `portfolio/`.
- `portfolio/paper_snapshot.py` intentionally reports local research data freshness, not execution-feed freshness.
- Next exact action: after review, Phase 3 can group PMKF/MKF research modules under `pmkf_mkf/` with equivalent compatibility wrappers.

## Task: CNstock-inspired gradual Web subpackage refactor Phase 1c

### Changed Files
- `src/ashare_edge_scout/web/app.py`: new implementation home for the NCN Web console, copied from the former `research_web.py` implementation and adjusted to import from the parent package and keep static assets at the existing `web_static` path.
- `src/ashare_edge_scout/web/__init__.py`: exports the main Web entrypoints (`create_context`, `make_handler`, `serve`, `main`, context/error types).
- `src/ashare_edge_scout/web/context.py`, `src/ashare_edge_scout/web/payloads.py`: facade modules for gradual extraction of context and payload builders.
- `src/ashare_edge_scout/web/routes/demo.py`: now owns demo portfolio list/status/factors payloads and demo mutation handling; `web/app.py` delegates demo routes to it.
- `src/ashare_edge_scout/web/routes/paper.py`: now owns paper status/data-status payloads and re-exports paper history payload; `web/app.py` delegates paper routes to it.
- `src/ashare_edge_scout/web/routes/pmkf_mkf.py`: now owns PMKF/MKF reports/summary/code payloads and bounded OHLCV fallback loader; `web/app.py` delegates PMKF/MKF routes to it.
- `src/ashare_edge_scout/web/routes/market.py`: now owns dashboard, candle, snapshot, code-normalization, research-alert, and candle-annotation helpers.
- `src/ashare_edge_scout/web/routes/watchlist.py`: now owns research watchlist GET and mutation payload helpers.
- `src/ashare_edge_scout/web/errors.py`: new standalone `ResearchWebError` definition to avoid route/app circular imports.
- `src/ashare_edge_scout/research_web.py`: reduced to a compatibility wrapper that re-exports existing public symbols and preserves `python -m ashare_edge_scout.research_web` for scripts and process detection.
- `tests/test_research_web.py`: added coverage that new `ashare_edge_scout.web` and `ashare_edge_scout.web.routes.*` import paths work while old imports continue to work.
- No `web_static` files, shell scripts, web-control process checks, config, demo/paper state, PMKF/MKF logic, scan logic, broker/order/live execution paths, or CNstock imports were changed.

### Behavior / Logic Changes
- Web implementation now has a CNstock-inspired package boundary under `ashare_edge_scout.web`, but runtime behavior and script entrypoints remain compatible.
- `scripts/edge_scout_web.sh` still launches `-m ashare_edge_scout.research_web`, and `scripts/edge_scout_web_control.sh` can still detect `ashare_edge_scout.research_web` in the managed process command.
- Demo, paper, PMKF/MKF, market, and watchlist route modules now contain their domain payload/mutation helpers; `web/app.py` is reduced to context/server wiring plus compatibility wrappers.
- Static assets remain at `src/ashare_edge_scout/web_static` and are still packaged by the existing `pyproject.toml` package-data setting.
- Live-trading surfaces remain absent: no CNstock runtime import, no Flask/Waitress, no `/force_buy`, no broker login/order submission, no leverage, no unattended execution, no real account IDs, no real-money P&L.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_research_web.py tests/test_research_web_demo_portfolio.py tests/test_research_web_paper.py tests/test_research_web_pmkf_mkf.py tests/test_edge_scout_web_control.py tests/test_standalone_boundary.py -q --tb=short` (`24 passed`), including new market/watchlist route import assertions.
- Local static checks passed: Python compile for `research_web.py` and new `web` modules; `node --check src/ashare_edge_scout/web_static/app.js`; `bash -n scripts/edge_scout_web.sh scripts/edge_scout_web_control.sh main.sh`; `git diff --check`.
- Local Web smoke passed after `./scripts/edge_scout_web_control.sh restart`: `/api/health`, `/api/demo-portfolios`, `/api/demo-portfolio/status?portfolio_id=default`, `/api/paper/status?portfolio_id=default`, `/api/pmkf-mkf/summary`, and `/api/pmkf-mkf/code?code=sh.600000` all returned 200 with `allow_live_order_submission=false`.
- Remote-first validation attempted: WSL SSH to `10.20.98.161:22` timed out during banner exchange, so WSL was unavailable.
- Doris validation used `~/NCN-claude-validation-web-refactor` with `~/NCN/.venv-doris/bin/python`: focused tests passed (`24 passed`), Python compile passed, and shell syntax passed. Doris node was not used because previous validation found node unavailable; local node check passed.

### Risks / Review Notes
- This phase extracted demo/paper/PMKF helper groups, but did not yet extract market/candle/snapshot/watchlist routes from `web/app.py`.
- Compatibility wrapper `src/ashare_edge_scout/research_web.py` must remain until scripts/process checks/tests are deliberately migrated in a later phase.
- Do not move `web_static` until package-data, tests, and static serving are updated together.
- Existing top handoff entries about MKF AI provider/model selection were preserved below this entry; they may still matter for AI review tasks.
- Next exact action: Phase 2 can move demo/paper state modules into `portfolio/` wrappers, after reviewing the now-complete Web route extraction.

## Task: Point MKF AI provider to Doris local Qwen endpoint

### Changed Files
- `yaml/mkf_ai_providers.yaml`: changed default `AI_PROVIDER` to `local_finance`; updated local finance backend to `https://ts.dorisw.kdns.fr:18090`, model `Qwen3.8-27B-4bit`, and key file `Key/ts.key`.
- `HANDOFF.md`: recorded this configuration change.
- No source code, tests, scanner logic, SMC admission/ranking, watchlist, paper/demo portfolio, or production behavior changed.

### Behavior / Logic Changes
- MKF AI review now defaults to the Doris local OpenAI-compatible endpoint when the provider YAML is used.
- Existing `api_key_env: EDGE_SCOUT_LOCAL_AI_API_KEY` remains as an override; if that env var is set, it takes precedence over `Key/ts.key` in the existing loader.
- The configured key file path is referenced only; no secret file content was read, created, or modified.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py -q --tb=short` (`16 passed`).
- No live request was sent to `https://ts.dorisw.kdns.fr:18090` and no Doris remote command was run.

### Risks / Review Notes
- Confirm the Doris endpoint exposes an OpenAI-compatible `/chat/completions` path relative to the configured base URL. If the server expects `/v1/chat/completions`, set `base_url` to `https://ts.dorisw.kdns.fr:18090/v1` instead.
- Keep `Key/ts.key` uncommitted and out of logs. Do not paste or read the key content unless explicitly needed for local troubleshooting.
- Model choice guidance: prefer a clean/instruct `Qwen3.8-35B` over 27B if available and stable; otherwise keep the configured clean `Qwen3.8-27B-4bit` / `Qwen3.6-27B` baseline. Do not use `Uncensored`, `Heretic`, `abliterated`, or `CRACK` variants as NCN defaults because this project needs boundary-following, JSON discipline, and no trading-action leakage.
- Next exact action: keep `Qwen3.8-27B-4bit` for the first 20-candidate MKF smoke test; only switch to a clean 35B model after JSON validity and forbidden-action checks pass.

## Task: Select local LLM for NCN on Doris Maxstudio 64G

### Changed Files
- `HANDOFF.md`: recorded local-model selection research and recommendation.
- No source, config, YAML provider, scanner, MKF AI review, watchlist, paper/demo portfolio, or runtime behavior changed.

### Behavior / Logic Changes
- None. User asked for an internet-informed local-model recommendation for current NCN, running on Doris / Maxstudio 64G, and clarified the model does not need to run concurrently with omlx or NCN backtests.
- Recommended primary candidate: `Qwen/Qwen3-32B-MLX-4bit` served through an OpenAI-compatible local endpoint, with Qwen thinking disabled or tightly controlled for NCN's JSON-only MKF AI committee prompt.
- Dedicated finance models are worth testing as challengers, not as the immediate default: validate `DianJin-R1-32B` first because it targets finance/securities use cases, but keep Qwen3-32B-MLX-4bit as the deployment baseline until licensing/runtime, JSON discipline, and NCN prompt behavior are proven.
- Recommended challengers for validation: `DianJin-R1-32B` as finance-domain challenger and `DeepSeek-R1-Distill-Qwen-32B` as reasoning challenger, but not defaults until licensing/runtime and JSON/system-prompt behavior are validated.

### Validation
- Read `AGENTS.md`, newest `HANDOFF.md`, relevant internet/Doris memories, `yaml/mkf_ai_providers.yaml`, `yaml/mkf_ai_review.yaml`, and the MKF AI client/prompt path in `src/ashare_edge_scout/mkf_ai_review.py`.
- Internet sources checked: official Qwen3-32B model card, official Qwen3-32B MLX 4-bit card, Qwen DianJin repository, official DeepSeek-R1-Distill-Qwen-32B model card, and finance benchmark/context sources.
- No Doris command, model download, local server launch, or NCN AI review run was performed in this task.

### Risks / Review Notes
- A local model recommendation is not validated scanner win-rate evidence; it only selects a read-only MKF/news/technical-context review assistant until tested on fixed NCN prompts.
- Do not switch scanner selection, SMC admission/ranking, watchlist, paper/demo portfolio behavior, or production behavior based on model prose alone.
- Next exact action: user showed existing local oMLX models including Qwen3.8-27B-4bit, Qwen3.6-35B-A3B variants, Ornith-1.0/1.5-35B variants, Gemma-4-31B, and gpt-oss-20b variants. Do not download DianJin immediately; first baseline existing Qwen3.8-27B-4bit or Ornith-1.x-35B-4bit against NCN's fixed MKF AI review prompt. Avoid uncensored/crack/abliterated variants as defaults because NCN needs boundary-following, JSON discipline, and no trading-action leakage. If dedicated finance testing is still needed after baseline, convert `DianJin/DianJin-R1-32B` to MLX 4-bit or use GGUF via llama.cpp, then compare with the same fixed candidate set.

## Task: Integrate Portfolio/SuperTrader demo-paper-PMKF features into NCN Web

### Changed Files
- `yaml/edge_scout_v1.yaml`: added `demo_portfolio`, `paper_trading`, and `paper_risk` config sections while keeping `allow_live_order_submission=false` and `production_enabled=false`.
- `src/ashare_edge_scout/config.py`: validates demo/paper enablement, state-root boundaries, caps, live-order fail-closed flags, and paper risk limits.
- `src/ashare_edge_scout/demo_portfolio_state.py`: new native NCN demo portfolio state module with safe portfolio IDs, allowed paper-only position states, atomic JSON state, factor listing, import/reset/settings helpers, and append-only audit JSONL.
- `src/ashare_edge_scout/paper_risk.py`, `src/ashare_edge_scout/paper_trading_state.py`, `src/ashare_edge_scout/paper_trading_snapshot.py`: new paper-only risk/status/history/data-freshness modules.
- `src/ashare_edge_scout/research_web.py`: added demo portfolio, paper monitor, audit/history, and bounded PMKF/MKF routes into the existing stdlib `HTTPServer`; `/api/paper/intent` returns 403 by default; `/force_buy` and `/api/force_buy` remain absent.
- `src/ashare_edge_scout/web_static/index.html`, `app.js`, `style.css`: added manual-refresh Demo Portfolio, Paper Monitor, PMKF/MKF, and Audit/Risk panels with visible `Paper-only`, `No broker connection`, `Live orders off`, and `No live order submission` labels.
- Added tests: `tests/test_demo_portfolio_state.py`, `tests/test_paper_trading_state.py`, `tests/test_paper_trading_snapshot.py`, `tests/test_research_web_demo_portfolio.py`, `tests/test_research_web_paper.py`, `tests/test_research_web_pmkf_mkf.py`.
- Updated tests: `tests/test_edge_scout_config.py`, `tests/test_research_web.py`.
- No CNstock Flask/Waitress app, CNstock runtime import, background trading loop, broker login, live order submission, leverage, `/force_buy`, all-universe Web scan, destructive log deletion, arbitrary multipart upload, real account IDs, or real-money P&L was added.

### Behavior / Logic Changes
- NCN Web now exposes safe native demo/paper endpoints: `/api/demo-portfolios`, `/api/demo-portfolio/status`, demo add/remove/update/settings/import/reset-capital mutations, `/api/demo-factors`, `/api/paper/status`, `/api/paper/history`, and `/api/paper/data-status`.
- Every demo mutation writes append-only `output/edge_scout/audit_logs/demo_portfolio_events.jsonl` and mutation responses include fail-closed boundary flags.
- Paper status is simulated only, reads NCN demo portfolio/audit state, reports local research-data freshness warnings, and does not imply execution freshness.
- PMKF/MKF Web integration includes precomputed report summary/list endpoints plus bounded single-code analysis; it does not run all-universe scans in request handling.
- Single-code PMKF/MKF uses bounded OHLCV parquet reading and records a warning if the stricter candle payload is unavailable due to non-critical local data-field quality.
- Existing research watchlist/K-line behavior remains present; new panels use manual refresh or explicit actions, not the 1-second scheduler.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_edge_scout_config.py tests/test_research_web.py tests/test_demo_portfolio_state.py tests/test_paper_trading_state.py tests/test_paper_trading_snapshot.py tests/test_research_web_demo_portfolio.py tests/test_research_web_paper.py tests/test_research_web_pmkf_mkf.py tests/test_standalone_boundary.py -q --tb=short` (`36 passed`).
- Local static checks passed: Python compile for changed backend modules; `node --check src/ashare_edge_scout/web_static/app.js`; `bash -n main.sh scripts/edge_scout_web.sh scripts/edge_scout_web_control.sh`; `git diff --check`.
- Local Web smoke passed after `./scripts/edge_scout_web_control.sh restart`: `/api/health`, `/api/demo-portfolios`, `/api/demo-portfolio/status?portfolio_id=default`, `/api/paper/status?portfolio_id=default`, `/api/pmkf-mkf/code?code=sh.600000` returned 200; `/force_buy` and `/api/force_buy` returned 404.
- Remote-first validation attempted: WSL SSH to `10.20.98.161:22` timed out during banner exchange, so WSL was unavailable.
- Doris validation used a temporary synced directory `~/NCN-claude-validation-web-migration` with `~/NCN/.venv-doris/bin/python`: focused tests passed (`36 passed`) and Python compile plus shell syntax passed. Doris `node` was unavailable, and `git diff --check` was not applicable in the non-git temp directory; both checks passed locally.

### Risks / Review Notes
- This is demo/paper/simulation infrastructure only, not a live-trading authorization. Do not add broker credentials, live order APIs, leverage, unattended execution, real account IDs, or real-money P&L without a future governance update.
- Demo portfolio mutations are local unauthenticated Web endpoints, consistent with the existing local-only Web console; keep server bound to localhost and do not expose it remotely without adding access control.
- PMKF/MKF single-code endpoint intentionally tolerates non-critical field gaps for dashboard display; strict candle research still surfaces quality warnings when full daily-bar validation fails.
- The working tree had many pre-existing tracked/untracked changes before this task. Stage only the files listed in this entry if committing this migration.
- Next exact action: if continuing, manually inspect the running UI in a browser and then add optional factor-save/import UX or paper evaluate-once only after this MVP is reviewed.

## Task: Update governance to phased production-adjacent mode

### Changed Files
- `AGENTS.md`: changed NCN boundary from strictly read-only scanner to phased production-adjacent project governance. Current phase allows portfolio-style demo analysis, paper/simulation workflows, PMKF/MKF dashboards, risk controls, audit logs, and operational hardening; live broker login/order submission/leverage/unattended real-money execution remain prohibited until future explicit authorization.
- `CLAUDE.md`: updated boundary pointer to reference phased production-adjacent rules and the current no-live-trading authorization boundary.
- `yaml/edge_scout_v1.yaml`: changed `mode` to `phased_production_adjacent`, added `allow_demo_portfolio: true` and `allow_paper_trading: true`, while keeping `allow_live_order_submission: false` and `production_enabled: false`.
- `src/ashare_edge_scout/config.py`: allows both `read_only_research` and `phased_production_adjacent` modes while preserving fail-closed live order and production checks.
- `src/ashare_edge_scout/research_web.py`: accepts the new phased mode for existing research Web context.
- `tests/test_edge_scout_config.py`: updated coverage for the new mode while confirming legacy read-only mode still validates.
- `HANDOFF.md`: recorded the governance change.
- No Portfolio/SuperTrader source migration, broker integration, live order path, execution adapter, real portfolio storage, P&L, return calculation, scanner/MKF/SMC selection rule, watchlist, or prospective archive behavior was implemented in this step.

### Behavior / Logic Changes
- Governance now authorizes a staged path toward production-adjacent research/trading support, specifically demo/paper/simulation and risk/audit hardening.
- True live trading remains disabled and unauthorized by default: `production_enabled=false`, `allow_live_order_submission=false`.
- Existing config validation and research Web continue to work under the new mode without enabling live execution.

### Validation
- Local config/Web tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_edge_scout_config.py tests/test_research_web.py -q --tb=short` (`19 passed`).
- Static checks passed: Python compile for `src/ashare_edge_scout/config.py` and `src/ashare_edge_scout/research_web.py`; `git diff --check` for governance/config/Web test files.
- Remote validation was not run for this governance-only change.

### Risks / Review Notes
- This governance update is not a live-trading authorization. Do not add real broker login, real order submission, leverage, or unattended real-money execution without another explicit governance update and runtime safety design.
- Future `Portfolio_web` / `PSuperTrader_Web` migration can now target demo/paper/simulation and PMKF/MKF research-analysis workflows, but must keep live broker actions fail-closed.
- Next exact action: inspect CNstock `Portfolio_web.py` and `PSuperTrader_Web.py` routes/data flows, then plan a staged NCN migration that separates demo/paper state from any future live execution.

## Task: Requested conversion to production-adjacent trading system

### Changed Files
- `HANDOFF.md`: recorded the new direction request and boundary blocker.
- No source, config, requirements, Web, scanner, MKF, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- None. User requested converting NCN into a production-ready quasi-trading system after clarifying they want full `Portfolio_web` / `PSuperTrader_Web` functionality, not read-only demo-only migration.
- User then explicitly stated they are the project author and want the project converted to production.
- Current checked-in project instructions in `AGENTS.md`/`CLAUDE.md` still explicitly prohibit adding broker login, orders, leverage, paper trading, backtesting, return calculation, live trading, portfolio accounting, P&L, personalized buy/sell instructions, and portfolio semantics. `yaml/edge_scout_v1.yaml` must keep `production_enabled: false`.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before responding.
- No zip inspection, code changes, tests, installs, web starts, or data updates were run for this direction change.

### Risks / Review Notes
- Do not implement trading/portfolio/super-trader behavior inside NCN under the current checked-in project instructions.
- Safe alternatives: keep NCN as a read-only signal/research engine and create a separate downstream project for execution-risk design, or update project governance/instructions outside this task before any trading-system architecture work.
- Next exact action is to ask the user whether they want a separate project boundary for a trading system, or a non-trading production-readiness hardening plan for NCN.

## Task: Generate safe requirements for CNstock web demo dependencies

### Changed Files
- `requirements.txt`: new NCN virtualenv requirements file combining current `pyproject.toml` runtime/test dependencies with safe read-only CNstock web/news demo dependencies.
- `HANDOFF.md`: recorded the dependency extraction and validation.
- No Web source, scanner, MKF, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- None. This step generated dependency documentation/install input only.
- Inspected `CNstock-main.zip` for `Portfolio_web.py`, `PSuperTrader_Web.py`, `requirements.txt`, and `requirements_rpi.txt`.
- External imports from the CNstock web files were narrowed to safe/demo dependencies: `flask`, `werkzeug`, `waitress`, `requests`, `akshare`, plus existing NCN dependencies.
- `requirements.txt` deliberately keeps NCN's current `numpy>=2.0`, `pandas>=2.2`, `pyarrow>=18.0` constraints instead of copying CNstock's older `numpy<2.0` trading-system pin.
- Excluded CNstock heavy/trading-adjacent dependencies not needed for a read-only demo requirements file: `torch`, `torchvision`, `scipy`, `scikit-learn`, `filterpy`, and trading/portfolio/P&L/execution-specific runtime semantics.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before work, per startup-continuity rules.
- Listed relevant archive files in `CNstock-main.zip`: `CNstock-main/PSuperTrader_Web.py`, `CNstock-main/Portfolio_web.py`, `CNstock-main/requirements.txt`, `CNstock-main/requirements_rpi.txt`.
- Extracted imports from both web files with AST parsing.
- Dry-run dependency resolution passed without installing packages: `.venv/bin/python -m pip install --dry-run -r requirements.txt`.
- Static whitespace passed: `git diff --check -- requirements.txt HANDOFF.md`.

### Risks / Review Notes
- User clarified the future web migration is demo-only and will not connect to a trading system; keep that boundary explicit in any follow-up migration.
- Future migration may reuse UI/layout/demo display concepts from CNstock web files, but must not introduce broker login, orders, live trading, portfolio accounting, P&L, returns, or personalized buy/sell behavior into NCN.
- Next exact action, if continuing, is a read-only inspection of `Portfolio_web.py` and `PSuperTrader_Web.py` routes/templates/data flows and a plan for a demo-only NCN page or separate demo script.

## Task: Add CNstock-style MKF AI provider YAML

### Changed Files
- `yaml/mkf_ai_providers.yaml`: new CNstock-inspired provider YAML with default `AI_PROVIDER: deepseek`, DeepSeek backend, and `local_finance` OpenAI-compatible backend for future local financial-analysis AI deployment.
- `yaml/mkf_ai_review.yaml`: now references `ai_config: yaml/mkf_ai_providers.yaml` and `news_config: yaml/mkf_news_context.yaml`, keeping review/technical settings separate from provider and news settings.
- `src/ashare_edge_scout/mkf_ai_review.py`: `load_mkf_ai_config()` now loads standalone AI provider YAML, converts CNstock-style `ENABLE_AI`/`AI_PROVIDER`/`backends` into the existing provider structure, resolves key files, supports provider-level `enabled`, `api_key`, env keys, and records AI config path/SHA/style in `summary.json`.
- `tests/test_mkf_ai_review.py`: updated test configs to use standalone provider YAML and added coverage for DeepSeek default plus `local_finance` backend loading.
- No MKF candidate selection rule, SMC admission/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- MKF AI provider configuration is now learnable/editable in a dedicated YAML, mirroring CNstock-style top-level AI keys while retaining NCN read-only boundaries.
- Default provider remains DeepSeek via `Key/deepseek.key`.
- A local OpenAI-compatible provider is preconfigured at `http://127.0.0.1:1234/v1` with model `local-finance-ai`; switching later should only require changing `AI_PROVIDER` to `local_finance` and model/base URL as needed.
- Existing injected clients and disabled/missing-key fail-closed behavior remain compatible.

### Validation
- Local MKF AI tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py -q --tb=short` (`16 passed`).
- Local combined related suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_news_context.py tests/test_mkf_ai_review.py tests/test_main_script.py tests/test_news_ai_review.py tests/test_mkf_candidate_selector.py tests/test_research_mkf.py -q --tb=short` (`83 passed`).
- Static checks passed: Python compile for `src/ashare_edge_scout/mkf_news_context.py`, `src/ashare_edge_scout/mkf_ai_review.py`, `scripts/review_mkf_ai.py`; `bash -n main.sh scripts/edge_scout_scan.sh`; `git diff --check` for touched MKF/news/provider files.
- Remote validation was not retried in this follow-up; immediately prior attempt found WSL SSH closing after TCP connect and Doris remote copy missing current test files.

### Risks / Review Notes
- `local_finance` is only a configurable OpenAI-compatible endpoint placeholder; no local model is bundled, launched, or validated here.
- Do not add CNstock trading, portfolio, PRE-BUY/BUY, score-pass, position, return, or execution semantics through the AI YAML.
- Provider YAML changes affect only MKF AI review calls; they must not affect MKF candidate selection, SMC/News flows, watchlist, prospective archive, or production behavior.
- Working tree has many pre-existing tracked/untracked changes; stage only intended files if committing and never include `Message/`, `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Add CNstock-style news context to MKF AI committee

### Changed Files
- `src/ashare_edge_scout/mkf_news_context.py`: added CNstock-compatible deterministic news context module with `Message/{normalized_code}_{YYYYMMDD}.json` cache contract, Google News RSS, AKShare Eastmoney news, Eastmoney announcement API, risk-word extraction, no-data sentinel, and stale-cache cleanup.
- `yaml/mkf_news_context.yaml`: new standalone, CNstock-style uppercase YAML for MKF news settings and risk-word lists; default online fetch/refresh is enabled with cache reuse.
- `yaml/mkf_ai_review.yaml`: points MKF AI review to the standalone news YAML while keeping AI provider and technical-context settings separate.
- `src/ashare_edge_scout/mkf_ai_review.py`: bumped schema to `ncn_mkf_ai_review_v3`, passes separate `cnstock_news_context` into AI payload, writes `news_contexts.json`, hashes it in `manifest.json`, records news summary/boundaries, and carries news status/risk words on review rows.
- `scripts/review_mkf_ai.py`: terminal progress now shows CNstock-compatible news context status and final machine-readable `news_contexts`, `news_cache_dir`, and cache-status counts.
- `scripts/edge_scout_scan.sh`: MKF one-click summary now surfaces MKF news context path/cache directory/status counts from the exact AI review run.
- `tests/test_mkf_news_context.py`: new tests for CNstock-style YAML/cache path/schema, cache-hit no-network behavior, no-data fail-closed behavior, risk-word extraction, and cleanup.
- `tests/test_mkf_ai_review.py`, `tests/test_main_script.py`: updated MKF AI and shell-flow coverage for news context payload/artifacts/summary and one-click output.
- `.gitignore`: added `Message/` so CNstock-compatible local news cache files are not committed.
- No MKF candidate selection rule, SMC admission/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- MKF AI committee now receives two explicit inputs per candidate: existing local candlestick/OHLCV technical context and a new CNstock-compatible deterministic news context.
- News context uses CNstock-style cache files under `Message/` with minimal schema `date`, `news_txt`, `fatal_risks`, `attn_risks`; richer source/cache metadata is only in MKF AI `news_contexts.json`.
- Default MKF one-click behavior is online news refresh with same-day cache reuse, controlled by `yaml/mkf_news_context.yaml`.
- If news dependencies/network/providers fail and no cache exists, the context fails closed with `暂无新闻数据`; AI prompt requires sentiment/fundamental roles to state evidence unavailable and forbids invented facts.
- Existing forbidden action labels and no-PMKF/no-Futu/no-trading boundaries remain in force. News risk words can add review risk flags but do not remove candidates or change selection/admission/ranking.

### Validation
- Local focused MKF tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_news_context.py tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`46 passed`).
- Local related regressions passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_news_ai_review.py tests/test_mkf_candidate_selector.py tests/test_research_mkf.py -q --tb=short` (`36 passed`).
- Local combined related suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_news_context.py tests/test_mkf_ai_review.py tests/test_main_script.py tests/test_news_ai_review.py tests/test_mkf_candidate_selector.py tests/test_research_mkf.py -q --tb=short` (`82 passed`).
- Static checks passed: Python compile for `src/ashare_edge_scout/mkf_news_context.py`, `src/ashare_edge_scout/mkf_ai_review.py`, `scripts/review_mkf_ai.py`; `bash -n main.sh scripts/edge_scout_scan.sh`; `git diff --check` for touched MKF/news files.
- WSL primary validation attempted: TCP to `10.20.98.161:22` succeeded but SSH closed immediately, so no WSL tests could run.
- Doris second-priority readiness attempted: `.venv-doris/bin/python --version` returned Python 3.13.15, but `~/NCN/tests/test_mkf_ai_review.py` was absent in the remote copy, so no Doris test run was possible without a separate source sync.

### Risks / Review Notes
- This is still a read-only MKF AI research-layer enrichment, not validated win-rate/profit evidence and not investment advice.
- Do not use `news_contexts.json` or news risk words to change MKF candidate selection, SMC admission/ranking, watchlist order, prospective evidence, or production without a separate validation gate.
- `akshare` is optional at runtime; if absent, that source fails closed while Google RSS/Eastmoney announcements can still run. Provider/network failures must not be converted into invented news.
- Working tree has many pre-existing tracked/untracked changes; stage only intended files if committing and never include `Message/`, `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Migrate MKF AI committee with candlestick technical context

### Changed Files
- `src/ashare_edge_scout/mkf_ai_review.py`: upgraded MKF AI review schema to v2, added single-call committee role payload, Japanese candlestick/OHLCV technical context, stronger forbidden-action parsing, local candlestick-aware fallback score, `technical_contexts.json`, and explicit no-PMKF/no-Futu boundaries.
- `scripts/review_mkf_ai.py`: updated terminal wording to `MKF AI 委员会只读复核` and progress display to include technical context status, candle confirmation score, and top candlestick patterns when available.
- `yaml/mkf_ai_review.yaml`: added `review.technical_context` configuration with `use_pmkf_kalman: false` and `use_futu_fields: false` safeguards.
- `tests/test_mkf_ai_review.py`: added/updated coverage for committee output, Japanese candlestick context payload, forbidden action/position/return terms, config rejection of PMKF/Futu context switches, and `technical_contexts.json` artifacts.
- `HANDOFF.md`: recorded implementation and validation.
- No MKF red/blue candidate selection rule, SMC admission/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- MKF candidate selection remains exactly the current immutable MKF red/blue source (`mkf_red_blue_cross20_under80_v1_and_existing_hard_gates`). The AI committee consumes those published MKF candidate runs only after schema/hash validation.
- The AI review prompt is now a single-call structured committee simulation with roles `technical_analyst`, `sentiment_analyst`, `fundamental_analyst`, `bullish_researcher`, `bearish_researcher`, `chief_strategist`, and `risk_manager`; it still outputs only NCN review states, not trading actions.
- Technical context now uses local adjusted daily bars through the signal date, English Japanese-candlestick/OHLCV fields, `candlestick_masks`, `compute_candle_confirmation_features`, recent daily bar shape summaries, and the immutable MKF snapshot.
- PMKF Kalman and Futu-derived fields are explicitly excluded: summary and artifact boundaries include `pmkf_kalman_used=false`, `futu_fields_used=false`, and the context records mark `excluded_contexts.pmkf_kalman_used=false`, `futu_fields_used=false`, `cnstock_context_used=false`.
- AI responses are rejected if they contain action/position/return vocabulary such as `BUY`, `HOLD`, `AVOID`, `SELL`, `WAIT`, `PRE-BUY`, `max_position_pct`, `stop_loss`, `target_price`, or `pnl`.
- Review publication now writes `technical_contexts.json` and includes it in the manifest SHA-256 map. AI failure still fail-closes to `ai_unavailable` without mutating source candidates.

### Validation
- Focused MKF AI tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py -q --tb=short` (`15 passed`).
- Compile passed: `PYTHONPATH=src .venv/bin/python -m py_compile src/ashare_edge_scout/mkf_ai_review.py scripts/review_mkf_ai.py`.
- Candlestick/news regressions passed on rerun: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_news_ai_review.py tests/test_edge_scout_candle_confirm.py tests/test_edge_scout_bearish_candles.py -q --tb=short` (`28 passed`). Initial parallel run showed one transient `test_review_cli_writes_ai_merged_human_summary` failure, but isolated rerun and sequential group rerun passed.
- MKF selection regressions passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_candidate_selector.py tests/test_research_mkf.py -q --tb=short` (`16 passed`).
- Main script regressions passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py -q --tb=short` (`24 passed`).
- Static whitespace passed: `git diff --check -- src/ashare_edge_scout/mkf_ai_review.py scripts/review_mkf_ai.py yaml/mkf_ai_review.yaml tests/test_mkf_ai_review.py`.
- Disabled-AI local smoke passed with temporary output root and local `PFrontStockData`: selected 49 MKF candidates for `2026-08-21`, review status `success`, `technical_contexts.json` present, first context status `ok`, and summary boundaries `pmkf_kalman_used=false`, `futu_fields_used=false`. A previous smoke using the real DeepSeek config timed out after 10 minutes; no repo files were changed by that timed-out run.

### Risks / Review Notes
- This remains an experimental, read-only research prioritization layer; do not claim validated win-rate/profit improvement from AI committee output.
- The committee is a single LLM call that simulates roles; it is not true independent multi-agent consensus.
- Do not reintroduce CNstock Futu/MHPG/DXBD/BULLCLUSTER terms, PMKF Kalman context, BUY/PRE-BUY/SELL/WAIT labels, position sizing, or target/stop/return fields.
- Do not feed committee results back into MKF candidate selection, SMC ranking/admission, watchlist ordering, prospective archive, or production without a separate validation gate.
- Working tree still has pre-existing large changes; stage only intended files if committing.

## Task: Implement and run local PMKF/MKF T+5 quality comparison

### Changed Files
- `src/ashare_edge_scout/research_pmkf_mkf_t5_quality.py`: new read-only comparison module for A=current red/blue MKF, B=CNstock-style PMKF/Kalman backbone, C=B plus red/blue timing confirmation.
- `scripts/evaluate_pmkf_mkf_t5_quality.py`: new standalone local JSON-report CLI; not wired into `main.sh` or production/menu flow.
- `tests/test_research_pmkf_mkf_t5_quality.py`: new regression tests for PMKF score parity, A/B/C mask relationships, T+5 label, path risk, and report metadata.
- `pmkf-mkf-t5-quality-smoke.json`: local short-window smoke output.
- `pmkf-mkf-t5-quality-2021-2026.json`: local full comparison output.
- `HANDOFF.md`: recorded implementation, validation, and result summary.
- No SMC admission/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- Added a standalone research comparison only. It reads local `PFrontStockData`, applies the same `production_gate_mask` universe gate to all candidates, and compares:
  - A `A_mkf_red_blue`: `production_gate_mask AND mkf_red_blue_cross20_under80_mask`.
  - B `B_pmkf_backbone`: `production_gate_mask AND cnstock_base_score >= 75.0` using CNstock-compatible Kalman/PMKF score semantics with `futu_bonus=0.0`.
  - C `C_pmkf_plus_mkf_timing`: B plus the current red/blue MKF timing confirmation.
- Futu/start-signal layer is explicitly excluded: no `compute_start_signals`, no `start_signal_count`, no `futu_bonus`, no MHPG/DXBD/BULLCLUSTER participation.
- PMKF Kalman meaning for this work: a 2-state Kalman smoother estimates `[price, velocity]`, constrains velocity with a pseudo-observation near zero, then calculates 20-day smoothed-price momentum. It is a trend-quality/backbone filter, not the red/blue oscillator MKF timing signal and not an AI decision layer.
- T+5 label is classification-only: next 5 stock-tradable closes after T must reach +3% and never close below -3%; path metrics track max excursion/drawdown and target/risk first state from daily high/low.
- Output report flags `research_only`, `classification_only`, `production_enabled=false`, `watchlist_modified=false`, `smc_admission_modified=false`, `broker_orders_enabled=false`, `pnl_modeled=false`, `futu_signals_ignored=true`.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_research_pmkf_mkf_t5_quality.py -q --tb=short` (`5 passed`).
- Local compile passed: `PYTHONPATH=src .venv/bin/python -m py_compile scripts/evaluate_pmkf_mkf_t5_quality.py src/ashare_edge_scout/research_pmkf_mkf_t5_quality.py`.
- Static whitespace passed: `git diff --check -- scripts/evaluate_pmkf_mkf_t5_quality.py src/ashare_edge_scout/research_pmkf_mkf_t5_quality.py tests/test_research_pmkf_mkf_t5_quality.py`.
- Local smoke run passed: `PYTHONPATH=src .venv/bin/python -B scripts/evaluate_pmkf_mkf_t5_quality.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2025-01-01 --end-date 2025-03-31 --workers 2 --output pmkf-mkf-t5-quality-smoke.json`; sample codes `3196`, C mature `n=34`, C win rate `0.5294`, C risk-first `0.3529`.
- Local full run passed per user instruction to run on this machine: `PYTHONPATH=src .venv/bin/python -B scripts/evaluate_pmkf_mkf_t5_quality.py --data-root PFrontStockData --config yaml/edge_scout_v1.yaml --start-date 2021-01-01 --end-date 2026-08-21 --workers 8 --output pmkf-mkf-t5-quality-2021-2026.json`; sample codes `3196`, date range observed `2021-01-04` to `2026-08-21`.
- Full local `full_requested_range` mature results: A `n=54676`, win `0.3293`, Wilson lower `0.3253`, risk-first `0.4306`, median drawdown `-0.0323`, median MFE `0.0322`; B `n=48561`, win `0.3172`, Wilson lower `0.3131`, risk-first `0.4826`, median drawdown `-0.0717`, median MFE `0.0592`; C `n=666`, win `0.3498`, Wilson lower `0.3146`, risk-first `0.4505`, median drawdown `-0.0574`, median MFE `0.0553`.
- Full local audit period `2024_present`: A `n=29181`, win `0.3339`, risk-first `0.4078`, median drawdown `-0.0299`; B `n=26742`, win `0.3238`, risk-first `0.4816`, median drawdown `-0.0688`; C `n=358`, win `0.3575`, risk-first `0.4274`, median drawdown `-0.0504`.

### Risks / Review Notes
- Do not promote C into scanner/watchlist/SMC/production yet. C has higher point-estimate win rate than A/B, but small full-sample size (`n=666`) and Wilson lower (`0.3146`) does not clearly beat A's point win (`0.3293`); C drawdown is worse than A though better than B.
- B alone has higher median MFE but materially worse risk-first and median drawdown than A; it should not replace A without additional gating.
- PMKF threshold is frozen at `75.0`; do not retune after seeing these results.
- Outputs are local current-vintage adjusted-data classification evidence only, not execution, orders, portfolio return, P&L, or personalized trading advice.
- Working tree still has large pre-existing changes; stage only intended files if committing.

## Task: Read CNstock PMKF source logic

### Changed Files
- `HANDOFF.md`: recorded the read-only source inspection and corrected PMKF/AI committee understanding.
- No source, config, selector, SMC ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- None. This was a read-only inspection of `CNstock-main.zip` internals.
- Inspected `CNstock-main/Pmkf_scan.py`, `CNstock-main/scan/base.py`, `CNstock-main/scan/futu_signals.py`, `CNstock-main/yaml/PmkfConfig.yaml`, and the PMKF profit-max milestone summaries.
- Corrected understanding: CNstock PMKF first performs deterministic PMKF/factor scoring and gating, then the AI committee acts as a conservative risk-review/adjustment layer over the strongest candidates; it is not the primary candidate generator.
- User clarified on 2026-08-21: do not consider Futu signals for the current PMKF alignment discussion.
- Current answer boundary: NCN one-click `mkf` candidate source is not equivalent to CNstock PMKF Kalman-smoothed 20-day momentum; NCN has a separate Kalman-compatible score path in `discovery.py`/`pmkf.py`, while `mkf_candidate_selector.py` uses red/blue oscillator cross-up-20 rules from `research_mkf.py`.

### Validation
- Local zip inspection only; no tests/backtests were run.
- Located key logic at `Pmkf_scan.py` definitions `calculate_enhanced_score`, `MultiAgentCommittee`, `AIAgent.analyze`, and main final-filter flow; PMKF filter implementation is in `scan/base.py`, while Futu startup/risk signals are in `scan/futu_signals.py`.

### Risks / Review Notes
- Do not treat AI committee output as a validated buy trigger. In CNstock source it is explicitly constrained as a risk review layer with WAIT/veto behavior under hard technical risks.
- Do not promote this understanding into NCN scanner changes without a separate validation gate and full-sample next-day/rolling validation.
- Working tree has large pre-existing tracked/untracked changes; stage only intended files if committing.

## Task: Separate MKF AI scoring from unscored rows

### Changed Files
- `src/ashare_edge_scout/mkf_ai_review.py`: moved `ai_unavailable` to the end of persisted review ordering, after `risk_attention`.
- `scripts/review_mkf_ai.py`: changed display label from `AI不可用` to `AI未评分`; terminal main list now shows only AI-scored rows and prints AI-unscored codes in a separate `AI未评分清单（不参与上方AI排序）` section.
- `tests/test_mkf_ai_review.py`: added regression coverage that `ai_unavailable` rows sort after `risk_attention`.
- `tests/test_main_script.py`: added CLI display coverage that unscored rows do not appear in the main AI-scored display section.
- `HANDOFF.md`: recorded the user-facing scoring semantics correction.
- No MKF formula, candidate selection, SMC selector/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- MKF AI output now treats failed/unavailable AI calls as unscored rows rather than as a normal AI-ranked class.
- The main terminal section is titled `MKF AI 评分排序（仅展示AI有效评分；只读研究，未经胜率验证）` and excludes `ai_unavailable` rows.
- Rows without valid AI output are listed separately as `AI未评分清单（不参与上方AI排序）`; they remain in JSON/CSV for auditability but should not be interpreted as AI-scored picks.
- Persisted ordering is now `priority_research`, `standard_research`, `insufficient_evidence`, `risk_attention`, then `ai_unavailable`; within state it still sorts by confidence desc, local_score desc, code asc.
- AI scoring basis remains: the AI sees the immutable MKF candidate row plus local daily context; local fallback score uses MKF low-zone breakout quality, inter-line confirmation, overheating risk, 5-day volume ratio, and recent 5-day close return.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py tests/test_main_script.py::test_review_mkf_ai_excludes_unavailable_rows_from_scored_display -q --tb=short` (`8 passed`).
- Local compile checks passed: `PYTHONPATH=src .venv/bin/python -m py_compile scripts/review_mkf_ai.py src/ashare_edge_scout/mkf_ai_review.py`.
- Local MKF/main regression passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`31 passed`).
- Static diff whitespace passed: `git diff --check -- scripts/review_mkf_ai.py src/ashare_edge_scout/mkf_ai_review.py tests/test_mkf_ai_review.py tests/test_main_script.py`.
- Per user instruction for this local flow issue, no WSL/Doris validation was run.

### Risks / Review Notes
- This still must not be described as validated profitability probability. It is AI-scored research priority based on provided technical context only.
- `AI未评分` rows are audit/failure rows and should not be used in the AI-ranked shortlist.
- Working tree still has pre-existing large tracked/untracked changes; stage only intended files if committing.

## Task: Add detailed MKF AI progress output

### Changed Files
- `src/ashare_edge_scout/mkf_ai_review.py`: extended the progress callback payload with candidate close, amount, MKF red/blue values, turnover, completion confidence/local score/risk flags, and per-candidate error label when applicable.
- `scripts/review_mkf_ai.py`: expanded live progress lines to show code, stage, close, amount in 亿, red/blue MKF values, and on completion the normalized review state, confidence, local score, top risk flags, and error label.
- `tests/test_mkf_ai_review.py`: added regression coverage that progress callbacks include candidate and result details.
- `HANDOFF.md`: recorded this local usability improvement.
- No MKF candidate formula, candidate selection rules, SMC selector/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- `MKF AI复核进度` is no longer just `index/total code - stage`; it now includes enough local context to see what is being processed while the external AI provider is slow.
- Example shape: `MKF AI复核进度：1/49 sz.002484 - 调用AI研究分层 | close=64.33 amount亿=33.34 red=41.37 blue=25.63`.
- Completion lines additionally show `state=... conf=... local=... risk=...` and `error=...` for fallback rows.
- The callback type was widened to accept optional detail payloads; existing callers without detail are not required.

### Validation
- Local focused MKF AI detail tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py tests/test_main_script.py::test_mkf_review_small_streams_ai_output_before_summary -q --tb=short` (`7 passed`).
- Local compile checks passed: `PYTHONPATH=src .venv/bin/python -m py_compile scripts/review_mkf_ai.py src/ashare_edge_scout/mkf_ai_review.py`.
- Local MKF/main regression passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`29 passed`).
- Static diff whitespace passed: `git diff --check -- scripts/review_mkf_ai.py src/ashare_edge_scout/mkf_ai_review.py tests/test_mkf_ai_review.py`.
- Per user instruction for this issue, validation stayed local; no WSL/Doris test was run.

### Risks / Review Notes
- External AI calls can still be slow or partial, but the terminal now shows per-candidate details and completion/fallback state instead of opaque progress.
- MKF AI states remain independent read-only research prompts, not buy/sell advice, SMC admission/ranking evidence, watchlist ordering, prospective evidence, or production input.
- Working tree still has pre-existing large tracked/untracked changes; stage only intended files if committing.

## Task: Stream MKF one-click AI review output locally

### Changed Files
- `scripts/edge_scout_scan.sh`: changed the MKF one-click AI stage from command-substitution capture to `tee` streaming capture, so `review-mkf-ai` progress prints live while output is still parsed for final summary fields.
- `tests/test_main_script.py`: added regression coverage that MKF AI progress appears before `MKF候选源一键流程摘要`, while existing partial-artifact handling and exact-run binding still pass.
- `HANDOFF.md`: recorded this local-flow fix.
- No MKF candidate formula, candidate selection rules, SMC selector/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- Root cause of the apparent hang: `cmd_mkf_review` captured the whole `review-mkf-ai` subprocess output in `$(...)` before printing it. During external AI calls there was no visible progress, so the menu looked stuck after `MKF AI 研究分层：...`.
- New behavior: `review-mkf-ai` output is streamed through `tee` in real time and also saved to a temp file for parsing `status=`, `run_directory=`, `timestamped_csv=`, and count fields.
- Existing degraded behavior remains: exit code 3 with a published AI artifact is summarized as `mkf_ai_review=<status>`; true failures without artifact still return failure.
- This is a local execution/usability fix only; it does not make external AI deterministic and does not change candidate content.

### Validation
- Local shell syntax passed: `bash -n scripts/edge_scout_scan.sh main.sh`.
- Local focused MKF shell tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py::test_mkf_review_small_streams_ai_output_before_summary tests/test_main_script.py::test_mkf_review_small_keeps_partial_ai_artifact_summary tests/test_main_script.py::test_edge_scout_mkf_commands_invoke_bound_clis -q --tb=short` (`3 passed`).
- Local main-script regression passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py -q --tb=short` (`23 passed`).
- Static diff whitespace passed: `git diff --check -- scripts/edge_scout_scan.sh tests/test_main_script.py`.
- Per user instruction for this issue, validation was kept local; no remote WSL/Doris test was run for this flow fix.

### Risks / Review Notes
- If the external AI provider is slow, the command can still take time, but candidate-by-candidate progress is now visible instead of hidden behind shell capture.
- MKF small and MKF AI labels remain independent read-only research prompts, not SMC admission/ranking evidence, watchlist ordering, production input, or trading advice.
- Working tree still has pre-existing large tracked/untracked changes; stage only intended files if committing.

## Task: Fix MKF small one-click partial AI handling

### Changed Files
- `scripts/edge_scout_scan.sh`: changed `cmd_mkf_review` so `review-mkf-ai` exit code 3 with a published `run_directory` and `timestamped_csv` is treated as degraded/partial completion, allowing the one-click flow to print the final summary and artifact paths.
- `tests/test_main_script.py`: added regression coverage that `mkf-review-small` preserves summary output and `mkf_ai_run`/`mkf_ai_csv` when the AI review exits 3 after publishing a partial artifact.
- `HANDOFF.md`: recorded diagnosis, fix, and validation.
- No candidate selection rules, MKF formula, SMC selector/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- Root cause: the menu command `MKF小资金一键流程（自动更新/AI分层，ADV20 5000万）` routes correctly to `mkf-review-small`, and its candidate selection was deterministic and correct, but the shell wrapper returned immediately on any nonzero AI review status.
- `scripts/review_mkf_ai.py` intentionally returns exit code 3 for `status=partial` or `status=ai_failed` even after writing an AI artifact. Before this fix, `cmd_mkf_review` returned that 3 before printing the final one-click summary, so the menu appeared failed/incomplete and did not expose `mkf_ai_run`/`mkf_ai_csv`.
- New behavior: if AI review returns 3 but printed both `run_directory=` and `timestamped_csv=`, the one-click flow prints `mkf_ai_review=<status>` plus artifact paths and exits successfully as a degraded read-only result. If AI review truly fails without an artifact, the one-click flow still returns the failure code.

### Validation
- Local focused shell tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py::test_mkf_review_small_keeps_partial_ai_artifact_summary tests/test_main_script.py::test_edge_scout_mkf_commands_invoke_bound_clis -q --tb=short` (`2 passed`).
- Local main-script regression passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py -q --tb=short` (`22 passed`).
- Local MKF/main regression passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`27 passed`).
- Static checks passed: `bash -n main.sh`; `bash -n scripts/edge_scout_scan.sh`; `git diff --check -- scripts/edge_scout_scan.sh tests/test_main_script.py`.
- WSL first-priority validation attempted: TCP to `10.20.98.161:22` succeeded but SSH closed immediately, so WSL tests could not run.
- Doris second-priority readiness checked: `ts.dorisw.kdns.fr` reachable, `.venv-doris/bin/python` is Python 3.13.15, and `tests/test_main_script.py` exists. Doris tests were not run because current local changes have not been synced to the remote copy in this step.

### Risks / Review Notes
- This fix changes only one-click flow status/reporting semantics for already-published partial AI artifacts; it does not make external AI deterministic or validated.
- A `partial` or `ai_failed` MKF AI artifact remains read-only degraded research output. Do not treat it as clean AI success, SMC admission/ranking evidence, watchlist ordering, prospective evidence, or production input.
- The working tree has pre-existing large tracked modifications and untracked MKF files from prior sessions; if committing, stage only intended files and inspect status/diff carefully.

## Task: Compare MKF menu run and Claude rerun paths

### Changed Files
- `HANDOFF.md`: recorded the read-only path comparison.
- No source, config, output artifact content, selector, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- None. This was a read-only comparison of MKF output paths and hashes.

### Validation
- Compared menu-side candidate run `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_193339/` with Claude rerun candidate run `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_194542/`.
- Both selection runs report `status=success`, `signal_date=2026-08-21`, `selection_profile=small_capital`, `effective_min_adv20_cny=50000000.0`, and `candidate_count=49`.
- Both `candidates.json` files have identical SHA-256 `a76eb4562a9444bece1aabe48b188bef512d82d9a8bcf2f6b6175d9866f92329`, so the deterministic candidate selection content is the same.
- Only one post-19:30 MKF AI review directory exists: `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260821_194716/`, created by the Claude rerun and bound to selection run `mkf-select-20260821_194542`; it has `status=partial`, `ai_success_count=48/49`, and one `ValueError` fallback.
- The menu-side run shown earlier stopped at `mkf_ai_review_failed: IncompleteRead(0 bytes read)` before publishing an AI review directory, so there is no menu AI review artifact to compare row-by-row.

### Risks / Review Notes
- The apparent mismatch is due to comparing the menu-side candidate-only run that failed during AI with the later Claude rerun's partial AI artifact. The candidate set is identical; the AI artifact exists only for the rerun.
- To compare AI labels exactly across runs, another full AI review must be run against the menu selection path after the `IncompleteRead` fix, e.g. `./main.sh review-mkf-ai --selection-run output/edge_scout/mkf_candidate_selections/mkf-select-20260821_193339 --top 20`; this may call the external AI provider again and labels may still vary.

## Task: User reports MKF menu/result mismatch

### Changed Files
- `HANDOFF.md`: recorded the mismatch report and pause point.
- No source, config, output artifact content, selector, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed in response yet.

### Behavior / Logic Changes
- None yet. User reported that the result opened from `./main.sh mkf-small --top 20` does not match their interactive main-menu choice `MKF小资金一键流程（自动更新/AI分层，ADV20 5000万）`.

### Validation
- No comparison has been run yet. Need exact user-side menu artifact path or output snippet before diagnosing whether the mismatch is candidate selection, AI ordering/labels, display top-N, or external AI nondeterminism.

### Risks / Review Notes
- Do not assume the opened CSV is the same run the user inspected. Compare exact `run_directory=`, `timestamped_csv=`, `mkf_ai_run=`, and `timestamped_csv=` paths from both executions before changing code.
- Keep the boundary: MKF small output and AI labels remain read-only research prompts, not validated trading advice or SMC/watchlist/production inputs.

## Task: Open latest MKF AI review CSV

### Changed Files
- `HANDOFF.md`: recorded that the latest MKF AI review CSV was opened locally.
- No source, config, selector, output artifact content, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- None. Opened the existing local CSV in the system default app for human inspection.

### Validation
- Opened `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260821_194716/mkf_ai_reviews_20260821_195838.csv` with macOS `open`.

### Risks / Review Notes
- The opened MKF AI review artifact has `status=partial`; `sz.002846` is AI-unavailable fallback.
- Treat all rows as independent read-only research review prompts, not buy/sell advice, production input, watchlist ordering, or validated win-rate evidence.

## Task: Rerun local MKF small-capital flow on 2026-08-21

### Changed Files
- `HANDOFF.md`: recorded this local rerun result.
- Ignored output artifacts created under `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_194542/` and `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260821_194716/`.
- No source, config, selector, SMC, watchlist, prospective archive, production, broker/order/P&L/return behavior was intentionally changed by the rerun.

### Behavior / Logic Changes
- None. This was a local execution of the existing `./main.sh mkf-small --top 20` flow after the `IncompleteRead` hardening fix.
- Data freshness check reported local BaoStock data already current at `2026-08-21` with latest coverage `7343/7357 = 0.9980970504281637`; no new download was run.
- MKF small-capital candidate selection succeeded for signal date `2026-08-21`, `selection_profile=small_capital`, `effective_min_adv20_cny=50000000`, `candidate_count=49`.
- MKF AI review published an artifact but returned `status=partial`, so the one-click shell exited with code 3 as designed. Summary: `ai_attempt_count=49`, `ai_success_count=48`, state counts `priority_research=23`, `standard_research=10`, `risk_attention=15`, `ai_unavailable=1`, `insufficient_evidence=0`; the single `ai_unavailable` code was `sz.002846` with `ai_error_counts={"ValueError":1}`.

### Validation
- Local command run: `./main.sh mkf-small --top 20`.
- Candidate output: `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_194542/`; timestamped CSV `mkf_candidates_20260821_194716.csv`.
- AI review output: `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260821_194716/`; timestamped CSV `mkf_ai_reviews_20260821_195838.csv`.
- No tests were run for this rerun; previous focused MKF AI tests after the code fix were already recorded in the prior handoff entry.

### Risks / Review Notes
- This is still an unvalidated independent read-only MKF research artifact, not a production/trading signal or win-rate proof.
- Do not promote MKF small output or AI labels into SMC ranking/admission, watchlist order, daily prospective evidence, or production without a separate validation gate.
- Because AI status is `partial`, treat `sz.002846` as AI-unavailable fallback and treat all AI labels as human-review prompts only.

## Task: Fix MKF AI IncompleteRead batch abort

### Changed Files
- `src/ashare_edge_scout/mkf_ai_review.py`: added `http.client` exception handling so truncated HTTP reads from the AI provider are treated as per-candidate AI unavailability instead of aborting the whole MKF review run.
- `tests/test_mkf_ai_review.py`: added regression coverage for `http.client.IncompleteRead` producing an `ai_unavailable` row and `ai_failed` summary status.
- No MKF candidate selector, SMC selector, ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior was changed.

### Behavior / Logic Changes
- The observed `mkf_ai_review_failed: IncompleteRead(0 bytes read)` came from the external AI review step after MKF candidate selection had already succeeded with 49 candidates for signal date `2026-08-21`.
- A single provider-side truncated response now fails closed for that candidate and allows the review artifact to be written with `status=partial` or `status=ai_failed`, preserving completed and fallback rows.
- The one-click `mkf-small` shell still returns nonzero for `partial`/`ai_failed` MKF AI summaries, so incomplete AI review is visible and not silently promoted as clean success.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_mkf_ai_review.py -q --tb=short` (`5 passed`).
- Local static checks passed: `PYTHONPATH=src .venv/bin/python -m py_compile src/ashare_edge_scout/mkf_ai_review.py scripts/review_mkf_ai.py`; `git diff --check -- src/ashare_edge_scout/mkf_ai_review.py tests/test_mkf_ai_review.py`.
- WSL first-priority validation attempted: TCP to `10.20.98.161:22` succeeded, but SSH closed immediately, so no WSL test run was possible.
- Doris second-priority validation attempted: `.venv-doris/bin/python --version` reported Python 3.13.15, but the remote `~/NCN` copy lacked the current `tests/test_mkf_ai_review.py`, so no Doris test run was possible without an additional source sync.

### Risks / Review Notes
- This fix addresses transport truncation only; it does not prove the external AI provider is reliable or that MKF AI labels improve win rate.
- If the user wants to finish the 2026-08-21 MKF AI review now, rerun `./main.sh mkf-small --top 20`; if the provider truncates again, the run should publish a failed-closed artifact instead of aborting without output.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended MKF files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Add MKF small-capital one-click flow

### Changed Files
- `main.sh`: added public `mkf-small` command and interactive menu item `MKF小资金一键流程（自动更新/AI分层，ADV20 5000万）`, routed to existing scan-level `mkf-review-small`.
- `scripts/edge_scout_scan.sh`: fixed `cmd_select_mkf` to parse/forward `--selection-profile` and `--min-adv20-cny`; removed selector-only profile/ADV20 args from MKF AI, SMC News AI, SMC select, and A-class select CLI invocations where they were unsupported or unsafe under `set -u`.
- `tests/test_main_script.py`: added help, direct delegation, shell one-click, exact MKF selection-run binding, AI-argument isolation, and menu-route coverage for `mkf-small` / `mkf-review-small`.
- `tests/test_mkf_candidate_selector.py`: added ADV20 override coverage and small-capital profile/effective ADV20 summary assertions.
- Ignored smoke outputs created under `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_171654/` and `output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260821_171834/`.

### Behavior / Logic Changes
- `./main.sh mkf-small [--as-of DATE] [--top N]` now runs the MKF one-click flow with `selection_profile=small_capital` and `effective_min_adv20_cny=50000000`.
- Small MKF keeps the existing NCN hard gates except the explicit MKF ADV20 override: Main Board prefixes, non-ST, listing age, price range, trading continuity, suspension, and near-limit-up filters remain unchanged.
- MKF AI review remains exact-selection-run driven and no longer receives selection-only liquidity/profile arguments; the small-capital provenance stays in the MKF selection artifact summary.
- Default `yaml/edge_scout_v1.yaml` ADV20 remains unchanged at 100,000,000; SMC admission/ranking, watchlist, prospective archive, production, broker/order/P&L/return behavior remain unchanged.
- While implementing this, existing shell template pollution was cleaned from non-MKF selector/review functions so `set -u` no longer references undefined `selection_profile`/`min_adv20_cny` in SMC select, A-class select, or News AI review paths.

### Validation
- Local static checks passed: `bash -n main.sh scripts/edge_scout_scan.sh`; `git diff --check`; `./main.sh help`; `./scripts/edge_scout_scan.sh help`.
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py tests/test_mkf_candidate_selector.py -q --tb=short` (`29 passed`).
- Local full suite passed: `PYTHONPATH=src .venv/bin/python -B -m pytest -q` (`434 passed, 3 skipped`).
- Local smoke with AI disabled passed: `EDGE_SCOUT_AUTO_UPDATE=0 EDGE_SCOUT_MKF_AI_CONFIG=<temp ai.enabled=false> ./main.sh mkf-small --top 10`; signal date `2026-08-20`, `mkf_candidate_count=33`, `selection_profile=small_capital`, `effective_min_adv20_cny=50000000`, AI review completed with `ai_unavailable` fallback labels.
- WSL primary validation was attempted first but failed: `./scripts/remote_test_env.sh check` reported SSH unreachable at `10.20.98.161:22`, and `sync-code` later timed out to the same host.
- Doris second-priority check confirmed `.venv-doris/bin/python` is Python 3.13.15, but the Doris `~/NCN` copy is not a git repo and lacked the newer MKF source modules; focused tests there failed during import before running. Further source upload to Doris was blocked by the tool's data-exfiltration policy, so Doris validation could not be completed in this session.

### Risks / Review Notes
- `mkf-small` is still an unvalidated independent read-only research profile, not a production/trading feature and not win-rate evidence.
- Do not promote MKF small output into SMC ranking/admission, watchlist order, daily prospective evidence, or production without a separate validation gate.
- The small-capital path intentionally does not include 科创板、北交所、创业板, ETF, or index candidates because the existing main-board hard gates remain in force.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Reconfirm MKF reuse and scan logic after formula fix

### Changed Files
- `HANDOFF.md`: recorded this read-only MKF logic confirmation.
- No source, script, config, test, data, SMC, watchlist, prospective archive, or production files were intentionally changed by this confirmation.

### Behavior / Logic Changes
- None. This was a read-only audit/confirmation of the corrected MKF implementation.

### Validation
- Re-inspected `src/ashare_edge_scout/research_mkf.py`, `src/ashare_edge_scout/mkf_candidate_selector.py`, `src/ashare_edge_scout/mkf_ai_review.py`, `scripts/edge_scout_scan.sh`, and relevant data-source helpers.
- Confirmed the corrected MKF red/blue scan uses daily Parquet bars from `PFrontStockData/` through `load_stock_records()` and not minute/intraday data.
- Confirmed migrated red/blue formula now matches the US scanner semantics: `momentum=(close-LLV(low,2))/(HHV(high,4)-LLV(low,4))*100`, `inter=RSV(31).MA(5)`, `near=RSV(5).MA(2)`, same-tradable-day red/blue cross from `<20` to `>=20`, current red/blue `<80`.
- Diagnostic on latest local data (`2026-08-20`) showed 7,355 Parquet files, 3,956 strict-loadable daily series, 175 raw latest-date MKF red/blue signals, and 17 candidates after existing NCN hard gates.
- Gate-drop diagnostics for the 175 raw signals were mostly expected hard-gate exclusions: non-main-board/prefix, insufficient ADV20, price, ST, listing age, limit-up, or trading-day coverage.

### Risks / Review Notes
- No remaining formula-reuse bug was found in the corrected MKF scan path.
- Important design choice: MKF candidate output currently reuses existing NCN hard gates, so it is not a literal all-7,355-file raw signal list; it is a read-only candidate source after main-board/liquidity/trading-quality gates. If the user wants a raw diagnostic export including ETFs/indices/ChiNext/STAR/invalid series, that should be a separate diagnostic mode, not the current candidate-source selector.
- Existing `load_stock_records()` strict validation means many local Parquet files are excluded before signal evaluation; this is consistent with existing NCN selector patterns but should be kept visible when interpreting “全市场”.
- Do not promote MKF into SMC ranking/admission, watchlist, daily prospective evidence, or production without a separate validation gate.

## Task: Diagnose and fix zero MKF candidate scan

### Changed Files
- `src/ashare_edge_scout/research_mkf.py`: added `mkf_red_blue_cross20_lines()` matching the migrated US MKF red/blue cross formula (`medlen=31`, `nearlen=5`) and changed `mkf_red_blue_cross20_under80_mask()` to use it instead of the older NCN strict green-exit `mkf_lines()` primitive.
- `src/ashare_edge_scout/mkf_candidate_selector.py`: changed candidate row MKF values to use `mkf_red_blue_cross20_lines()` so printed/exported values match the migrated red/blue signal.
- `tests/test_research_mkf.py`, `tests/test_mkf_candidate_selector.py`: updated monkeypatch targets and added formula parity coverage for the migrated red/blue MKF lines.
- `HANDOFF.md`: recorded the diagnostic and correction.

### Behavior / Logic Changes
- Root cause of zero candidates: the first MKF migration reused NCN's existing `mkf_lines()` research primitive, which belongs to the older strict green-zone exit study and does not match the US red/blue cross20 scanner formula. That made the signal too different/strict after A-share hard gates.
- The MKF candidate source now uses the migrated US daily-bar formula: `momentum=(close-LLV(low,2))/(HHV(high,4)-LLV(low,4))*100`, `inter=RSV(31).MA(5)`, `near=RSV(5).MA(2)`, then requires red(momentum) and blue(near) same-day cross from `<20` to `>=20` while both remain `<80`.
- Local latest daily data (`2026-08-20`) now produces 17 MKF candidates after existing NCN hard gates, confirming the all-zero result was an implementation mismatch rather than expected market behavior.
- SMC admission/ranking, News AI, watchlist, prospective archive, daily flow, production scanner, broker/order/P&L/return behavior remain unchanged.

### Validation
- Diagnostic count before fix showed NCN strict-line implementation had 17 raw latest-date signals but 0 after hard gates, while the migrated US red/blue formula had 175 raw latest-date signals and 17 after hard gates on daily data.
- Local smoke after fix passed: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-mkf --top 20`; signal date `2026-08-20`, `candidate_count=17`, output `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_153045/`.
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_research_mkf.py tests/test_mkf_candidate_selector.py tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`40 passed`).
- Static checks passed: `bash -n main.sh scripts/edge_scout_scan.sh`; Python compile for MKF modules; `git diff --check`.
- WSL primary validation passed: `./scripts/remote_test_env.sh check`, `./scripts/remote_test_env.sh sync-code`, then `./scripts/remote_test_env.sh test tests/test_research_mkf.py tests/test_mkf_candidate_selector.py -q --tb=short` (`15 passed`).

### Risks / Review Notes
- The corrected MKF candidate list is still an unvalidated independent research experiment. Do not promote it into SMC ranking/admission, watchlist, daily prospective evidence, or production without a future validation gate.
- The latest corrected run found 17 candidates on `2026-08-20`; this is not win-rate evidence and should only be used for manual research review.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended MKF files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Add MKF one-click flow

### Changed Files
- `scripts/edge_scout_scan.sh`: added `mkf-review` one-click flow that runs exact MKF candidate selection, parses the produced run path, and only runs MKF AI review when the candidate count is nonzero.
- `main.sh`: added `mkf-review` direct command and interactive menu item `MKF一键流程（自动更新/AI分层）`.
- `tests/test_main_script.py`: added/updated direct command and expect-driven menu routing coverage for the new MKF one-click flow.
- `HANDOFF.md`: recorded this follow-up one-click workflow.

### Behavior / Logic Changes
- `./main.sh mkf-review [--as-of DATE] [--top N]` and the new menu option now run MKF candidate-source scan first, then bind AI review to that exact MKF run rather than falling back to latest.
- If the MKF candidate count is `0`, the one-click flow skips AI review to avoid unnecessary external provider calls and prints a concise summary with `mkf_ai_review=skipped_no_candidates`.
- The one-click flow remains separate from SMC daily/select-review/archive/watchlist/production paths and does not change SMC admission/ranking or prospective evidence.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py tests/test_mkf_candidate_selector.py tests/test_mkf_ai_review.py tests/test_research_mkf.py -q --tb=short` (`39 passed`).
- Static checks passed: `bash -n main.sh scripts/edge_scout_scan.sh`; `git diff --check`.
- Local smoke with AI disabled passed: `EDGE_SCOUT_AUTO_UPDATE=0 EDGE_SCOUT_MKF_AI_CONFIG=<temp ai.enabled=false> ./main.sh mkf-review --top 10`; signal date `2026-08-20`, `mkf_candidate_count=0`, AI skipped.
- Normal external-AI smoke was not run in auto mode because it may send MKF candidate/context data to DeepSeek; this is intentional.
- WSL primary validation passed: `./scripts/remote_test_env.sh check`, `./scripts/remote_test_env.sh sync-code`, then `./scripts/remote_test_env.sh test tests/test_main_script.py -q --tb=short` (`21 passed`).

### Risks / Review Notes
- `mkf-review` is still an unvalidated independent research experiment. Do not wire it into SMC daily evidence, SMC ranking/admission, watchlist, or production without a separate validation gate.
- When future MKF candidates exist and AI is enabled, `mkf-review` may call the external configured AI provider; users should run/review that step knowingly.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended MKF workflow/menu files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Add MKF options to interactive main menu

### Changed Files
- `main.sh`: added MKF candidate-source and MKF AI review options to the interactive arrow-key menu and mapped them to existing `select-mkf`, local `select-mkf`, and `review-mkf-ai` commands.
- `tests/test_main_script.py`: added/updated expect-driven menu routing coverage after inserting the new MKF menu options.
- `HANDOFF.md`: recorded this follow-up menu integration.

### Behavior / Logic Changes
- Interactive `./main.sh` now shows three MKF entries: automatic-data MKF candidate-source scan, local-data MKF candidate-source scan, and MKF candidate-source AI research layering.
- The new menu routes call the already-added independent MKF commands only; SMC admission/ranking, News AI, daily flow, watchlist, prospective archive, production scanner, broker/order/P&L/return behavior remain unchanged.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_main_script.py tests/test_mkf_candidate_selector.py tests/test_mkf_ai_review.py tests/test_research_mkf.py -q --tb=short` (`39 passed`).
- Static checks passed: `bash -n main.sh scripts/edge_scout_scan.sh`; `git diff --check`.
- WSL primary validation passed: `./scripts/remote_test_env.sh check`, `./scripts/remote_test_env.sh sync-code`, then `./scripts/remote_test_env.sh test tests/test_main_script.py -q --tb=short` (`21 passed`).

### Risks / Review Notes
- MKF menu options are still independent unvalidated research experiment commands. Do not wire them into daily SMC+News evidence collection or SMC ranking/admission without a future validation gate.
- The MKF AI menu option may call the external configured AI provider when candidates exist and AI is enabled; users should understand candidate/context data may be sent to that provider.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended MKF/menu files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Migrate US MKF scan and AI review as isolated NCN candidate-source experiment

### Changed Files
- `src/ashare_edge_scout/research_mkf.py`: added `mkf_red_blue_cross20_under80_mask()` while preserving existing green-exit research behavior.
- `src/ashare_edge_scout/mkf_candidate_selector.py`: added independent immutable MKF red/blue cross20-under80 candidate-source selector.
- `scripts/select_mkf_candidates.py`: added CLI for the deterministic MKF candidate-source experiment.
- `src/ashare_edge_scout/mkf_ai_review.py`: added optional MKF AI research-priority review bound only to exact MKF candidate runs.
- `scripts/review_mkf_ai.py`: added CLI for optional MKF AI review.
- `yaml/mkf_ai_review.yaml`: added separate MKF AI provider config, distinct from SMC News AI config.
- `scripts/edge_scout_scan.sh`, `main.sh`: added `select-mkf`, `select-mkf-local`, and `review-mkf-ai` routes/help without wiring them into SMC daily/select-review/archive flows.
- `tests/test_research_mkf.py`, `tests/test_mkf_candidate_selector.py`, `tests/test_mkf_ai_review.py`, `tests/test_main_script.py`: added primitive, selector, AI-review, and command wiring coverage.

### Behavior / Logic Changes
- New MKF candidate-source experiment selects A-share rows on the signal date when MKF red (`momentum`) and blue (`near`) both cross from `<20` to `>=20` on the same tradable row while both remain `<80`, after existing NCN hard gates.
- MKF outputs are immutable and separate under `output/edge_scout/mkf_candidate_selections/`; they do not change SMC admission, SMC ranking, News AI states, watchlist, daily workflow, prospective archives, production scanner, broker behavior, orders, P&L, or returns.
- Optional MKF AI review consumes only exact MKF candidate runs and writes separate artifacts under `output/edge_scout/mkf_ai_reviews/`; normalized states are research labels (`priority_research`, `standard_research`, `risk_attention`, `insufficient_evidence`, `ai_unavailable`) and reject `BUY/HOLD/AVOID` action labels.
- The US “AI committee” was migrated as a single provider-compatible prompt persona plus deterministic fallback, not represented as true multi-agent consensus.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -B -m pytest tests/test_research_mkf.py tests/test_mkf_candidate_selector.py tests/test_mkf_ai_review.py tests/test_main_script.py -q --tb=short` (`38 passed`).
- Static checks passed: `bash -n main.sh scripts/edge_scout_scan.sh`; Python compile for new/changed MKF scripts/modules; `./main.sh help`; `./scripts/edge_scout_scan.sh help`; `git diff --check`.
- Local deterministic smoke passed with auto-update disabled: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-mkf --top 10`; signal date `2026-08-20`, candidate_count `0`, output `output/edge_scout/mkf_candidate_selections/mkf-select-20260821_135204/`.
- External MKF AI smoke with normal config was blocked by auto-mode data-exfiltration guard because it may send MKF candidate/context data to DeepSeek; not retried against the external provider.
- AI-disabled smoke passed using temporary `ai.enabled=false`: `./main.sh review-mkf-ai --selection-run output/edge_scout/mkf_candidate_selections/mkf-select-20260821_135204 --top 10`; wrote empty review run under `output/edge_scout/mkf_ai_reviews/`.
- WSL primary environment check passed (`10.20.98.161`, 20 CPU, 19Gi memory, project ready); after `./scripts/remote_test_env.sh sync-code`, focused WSL tests passed: `38 passed`.

### Risks / Review Notes
- MKF candidate-source and MKF AI review are unvalidated research experiments only. Do not promote them into SMC admission/ranking, watchlist order, SMC+News prospective evidence, daily workflow, or production behavior without a separate pre-registered validation gate.
- Real external AI review was intentionally not run in auto mode. To exercise DeepSeek, the user should run the command manually and accept the data-sharing prompt if desired.
- The latest local deterministic smoke found zero MKF candidates on `2026-08-20`; this is a valid empty artifact, not evidence that the signal is useful or useless.
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, stage only intended MKF files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Requested ../US MKF scan and AI committee migration

### Changed Files
- `HANDOFF.md`: recorded the new migration request and current clarification gate.

### Behavior / Logic Changes
- None yet. No NCN scanner, SMC selector, MKF logic, AI review/committee, watchlist ordering, prospective archive, Web, data, or tests were changed.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before responding, per startup-continuity rules.
- No inspection of `../US/`, code changes, scans, tests, backtests, data updates, or external AI calls have been run yet for this request.

### Risks / Review Notes
- This request affects scanner/watchlist research logic and is currently at the Problem Steelman Gate before implementation.
- Clarify whether the first migration target is a separate derived read-only review artifact only, or whether MKF/committee output may affect SMC admission, ranking, watchlist order, or prospective evidence after validation.
- Do not port US-market execution, portfolio, order, P&L, return, broker, hard buy/sell semantics, or US-market assumptions into NCN. Any migration must remain compatible with NCN's read-only A-share scanner boundaries.

## Task: Scope CNstock AI committee migration as read-only review artifact

### Changed Files
- `HANDOFF.md`: recorded the user's chosen scope for the migration direction.

### Behavior / Logic Changes
- None yet. No NCN scanner, SMC selector, News AI review, watchlist ordering, prospective archive, Web, data, or tests were changed.
- User chose to limit any CNstock-style AI committee migration to a derived read-only review artifact, not SMC admission/ranking or validated priority behavior.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before responding, per startup-continuity rules.
- No code, scans, tests, data updates, or external AI calls were run for this clarification.

### Risks / Review Notes
- Recommended next step is an implementation plan for a separate post-SMC committee-review artifact bound to an exact SMC selection run and optional exact News review run.
- Do not port CNstock trading, portfolio, execution, P&L, PRE-BUY/BUY semantics, or hard veto behavior into NCN.
- Do not let the committee output affect SMC admission, ranking, watchlist order, News AI states, prospective evidence, or production behavior until a separate prospective validation gate is defined and passed.

## Task: Requested CNstock AI committee migration into NCN

### Changed Files
- `HANDOFF.md`: recorded the requested direction and current pause point.

### Behavior / Logic Changes
- None yet. No NCN scanner, News AI review, SMC selection, prospective archive, Web, data, or tests were changed.

### Validation
- Prior read-only inspection confirmed CNstock has a `MultiAgentCommittee` in `/Users/artx/Local/Git/CNstock/Pmkf_scan.py` with technical/sentiment/fundamental analysts, bullish/bearish debate, chief strategist, risk manager, and code-level hard vetoes.
- Prior read-only inspection confirmed current NCN News AI review is single-provider-per-candidate plus deterministic rule classification, not a committee.

### Risks / Review Notes
- This request affects scanner/watchlist research conclusions and must go through the Problem Steelman Gate before implementation.
- Do not directly port CNstock trading, portfolio, execution, P&L, PRE-BUY/BUY semantics, or production behavior into NCN. Any migration must remain read-only and prospectively validated before affecting SMC admission/ranking.
- Awaiting the user's answer on whether the committee should initially be a derived post-SMC review artifact only, or allowed to affect human-review priority/order after validation.

## Task: Check whether CNstock uses an AI review committee

### Changed Files
- `HANDOFF.md`: recorded this cross-project read-only clarification.

### Behavior / Logic Changes
- None. No NCN or CNstock source, scanner, selector, AI review, data, or tests were changed.

### Validation
- Read current NCN `AGENTS.md` and newest `HANDOFF.md` before answering.
- Inspected `/Users/artx/Local/Git/CNstock/CLAUDE.md`, `AGENTS.md`, `Pmkf_scan.py`, `ai_report_analyzer.py`, `ai_web_analyzer.py`, `CHANGELOG.md`, and `yaml/PmkfConfig.yaml` with read-only searches/reads.
- Confirmed CNstock `Pmkf_scan.py` contains `MultiAgentCommittee`, enabled by `MULTI_AGENT_ENABLE`, with technical, sentiment, fundamental analysts, bullish/bearish debate, chief strategist aggregation, risk manager review, and code-level hard vetoes.

### Risks / Review Notes
- CNstock's committee is used as a conservative risk-review layer, not a standalone buy trigger: project history/config say AI mainly vetoes, reduces score, and explains after technical/rule candidate selection.
- Do not transfer CNstock's AI committee, trading, portfolio, execution, or P&L semantics into NCN without a separately authorized and prospectively validated read-only experiment.

## Task: Clarify whether AI analysis uses a review committee

### Changed Files
- `HANDOFF.md`: recorded this read-only clarification.

### Behavior / Logic Changes
- None. No scanner, selector, News AI review, SMC+News archive, Web, data, or tests were changed.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before answering, per project startup-continuity rules.
- Inspected `src/ashare_edge_scout/news_ai_review.py`, `yaml/news_ai_review.yaml`, and relevant README text for the News AI review path.
- Confirmed current implementation uses one configured OpenAI-compatible AI provider call per candidate, followed by deterministic rule classification; no multi-agent committee, judge panel, voting, or adversarial verifier path is implemented.

### Risks / Review Notes
- The current AI review remains experimental, read-only human-review prioritization. Do not describe it as validated win-rate evidence, a buy/sell recommendation, or an AI committee consensus.
- If a future AI review committee is desired, it should be designed as a separate prospective experiment with fixed prompts, independent reviewers, aggregation rules, cost limits, and promotion gates before changing scanner behavior.

## Task: Add optional post-SMC read-only recommendation analysis CSV

### Changed Files
- `src/ashare_edge_scout/post_smc_recommendation.py`: added deterministic post-SMC read-only human-review recommendation analysis builder, CSV writer, and terminal formatter.
- `scripts/analyze_post_smc_recommendation.py`: added CLI to write `post_smc_recommendation_analysis.csv` for an exact `--selection-run` and optional bound `--news-run`.
- `scripts/edge_scout_scan.sh`: added `post-smc-analysis` command and `select-review --post-smc-analysis|--no-post-smc-analysis`; enabled exact selection/news run binding before running the new analysis.
- `main.sh`: added interactive default-Yes prompt for the auto SMC menu item and direct `post-smc-analysis` dispatch/help text.
- `tests/test_post_smc_recommendation.py`: added row grouping, conservative News merge, CSV writing, empty candidate, and binding-safety tests.
- `tests/test_main_script.py`: added command delegation, shell exact-binding, and interactive menu default-Yes/explicit-No coverage.
- Ignored smoke outputs created under `output/edge_scout/selections/select-20260821_100902/` and `output/edge_scout/news_reviews/news-review-20260821_101051/`.

### Behavior / Logic Changes
- New analysis is a separate post-SMC artifact: `post_smc_recommendation_analysis.csv` in the SMC selection run directory.
- The analysis is derived/read-only and uses already frozen SMC candidate fields plus optional bound News AI review fields; it does not call or change SMC selector logic.
- Interactive `./main.sh` auto SMC menu now asks `是否进行 SMC 后人工复核建议分析（只读，默认Y）？`; Enter/Y runs `select-review --post-smc-analysis`, N runs `select-review --no-post-smc-analysis`.
- Non-interactive commands remain flag-driven and do not prompt. Plain `select-review` preserves prior behavior unless `--post-smc-analysis` is explicitly passed.
- Existing SMC admission, ranking, thresholds, candidate artifacts, News AI states/order, prospective archive rules, production, broker behavior, P&L, and return calculations are unchanged.

### Validation
- Static checks passed locally: `bash -n main.sh scripts/edge_scout_scan.sh`; `PYTHONPATH=src .venv/bin/python -m py_compile scripts/analyze_post_smc_recommendation.py src/ashare_edge_scout/post_smc_recommendation.py`; `git diff --check`.
- Local focused/regression tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_post_smc_recommendation.py tests/test_main_script.py tests/test_human_review_summary.py tests/test_news_ai_review.py tests/test_stock_selector.py -q` (`57 passed`).
- WSL primary environment check passed: `./scripts/remote_test_env.sh check` reached `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- WSL focused/regression tests passed after `./scripts/remote_test_env.sh sync-code`: `./scripts/remote_test_env.sh test tests/test_post_smc_recommendation.py tests/test_main_script.py tests/test_human_review_summary.py tests/test_news_ai_review.py tests/test_stock_selector.py -q` (`57 passed`).
- Local smoke passed with auto-update disabled: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-review --top 5 --post-smc-analysis`; generated `post_smc_analysis_csv=/Users/artx/Local/Git/Stock/NCN/output/edge_scout/selections/select-20260821_100902/post_smc_recommendation_analysis.csv` and duplicate prospective archive still skipped existing `2026-08-20` signal date.

### Risks / Review Notes
- The new CSV is for later research analysis and manual review prioritization only. Do not use it as validated win-rate evidence or promote it into SMC admission/ranking without future prospective gates.
- The working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, inspect/stage only intended files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Clarify how to analyze latest SMC+News grouped output

### Changed Files
- `HANDOFF.md`: recorded the read-only analysis clarification request.

### Behavior / Logic Changes
- None. No scanner, SMC ordering, News AI state, archive, validation, web, data, or tests were changed.

### Validation
- Read `AGENTS.md` and newest relevant `HANDOFF.md` before responding, per project startup-continuity rules.
- No scans, tests, data updates, backtests, or artifact reads were run for this clarification.

### Risks / Review Notes
- The pasted grouped output must be treated as read-only human-review prioritization, not buy/sell advice or validated win-rate evidence.
- Next exact action is to clarify whether the user wants same-day manual review prioritization, scanner-rule improvement, or prospective validation design before giving a concrete recommendation.

## Task: Add derived SMC human-review summary CSV and screen output

### Changed Files
- `src/ashare_edge_scout/human_review_summary.py`: added derived human-review grouping builder, selection/news artifact validation, atomic `human_review_summary.csv` writer, and terminal formatter.
- `scripts/select_stocks.py`: now writes SMC-only degraded `human_review_summary.csv`, prints `human_review_summary_csv=...`, and appends the full grouped summary after the existing detailed SMC output.
- `scripts/review_smc_news.py`: now upgrades the same selection-run CSV to News-AI-merged mode after a successful review and appends the grouped summary after existing News AI cards.
- `scripts/edge_scout_scan.sh`: daily final summary now preserves/surfaces `human_review_summary_csv`, using the News-merged path when News AI runs and the SMC-only path when News is skipped.
- `tests/test_human_review_summary.py`: added grouping, ordering/source-mode, CSV writing, empty-candidate, and binding-safety coverage.
- `tests/test_stock_selector.py`, `tests/test_news_ai_review.py`, `tests/test_main_script.py`: added regression assertions that the derived CSV/screen output exists while original SMC/News artifacts stay intact.
- Ignored outputs created during smoke validation: `output/edge_scout/selections/select-20260820_232313/` and `output/edge_scout/news_reviews/news-review-20260820_232510/`.

### Behavior / Logic Changes
- Every SMC selection run now gets `human_review_summary.csv` inside its own selection directory; `select`/`select-local` use `source_mode=smc_only_degraded`.
- A successful `review-news`/`select-review`/News-enabled `daily` rewrites that same CSV with `source_mode=news_ai_merged`, after validating the News run is bound to the exact selection candidates hash.
- The grouped screen output is appended after existing detailed SMC/News output; the existing detailed output is preserved.
- The grouping is derived and read-only only. It does not alter `StockSelectionRow`, `candidates.csv`, timestamped SMC CSV, `candidates.json`, SMC admission/order/thresholds, News AI prompts/states/order, production, broker behavior, returns, or P&L.
- The derived CSV is intentionally not added to the SMC manifest because it can be upgraded from SMC-only to AI-merged for the same immutable selection run.

### Validation
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_human_review_summary.py tests/test_stock_selector.py tests/test_news_ai_review.py tests/test_main_script.py -q` (`50 passed`).
- Static checks passed: `git diff --check`; `bash -n main.sh scripts/edge_scout_scan.sh`; `PYTHONPATH=src .venv/bin/python -m py_compile scripts/select_stocks.py scripts/review_smc_news.py src/ashare_edge_scout/human_review_summary.py`.
- Local smoke passed: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh select-local --top 5` generated 14 SMC candidates for `2026-08-20`, printed the existing detailed SMC table plus the new grouped summary, and wrote `human_review_summary.csv`.
- Local AI-merged smoke passed: `EDGE_SCOUT_AUTO_UPDATE=0 ./main.sh review-news --selection-run output/edge_scout/selections/select-20260820_232313 --top 5` printed existing News AI cards plus the new grouped summary and rewrote the selection CSV as News-merged.
- Local full suite passed: `PYTHONPATH=src .venv/bin/python -m pytest -q` (`408 passed, 3 skipped`).
- Remote validation attempted first: WSL TCP reached `10.20.98.161` but SSH closed immediately during `./scripts/remote_test_env.sh check`.
- Doris validation used the required project virtualenv: `cd "$HOME/NCN" && .venv-doris/bin/python --version` (`Python 3.13.15`). After user-approved cleanup/sync, Doris focused tests passed: `PYTHONPATH=src .venv-doris/bin/python -m pytest tests/test_human_review_summary.py tests/test_stock_selector.py tests/test_news_ai_review.py tests/test_main_script.py -q` (`50 passed`).
- Remote cleanup completed: removed the initial root-level Doris `$HOME/NCN` mis-sync files, then re-synced the relevant files to their correct project paths.

### Risks / Review Notes
- This feature is a derived review aid only; do not use `human_review_summary.csv` as prospective evidence, backtest label input, SMC admission/ranking input, or News AI promotion evidence.
- Current grouping rules are deterministic but not validated win-probability estimates. Treat them as human-review prioritization and keep the boundary note visible.
- The working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, inspect/stage only intended files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Interpret latest SMC scan result as example

### Changed Files
- `HANDOFF.md`: recorded the read-only interpretation request and inspected latest output artifacts.

### Behavior / Logic Changes
- None. No scanner, ranking, thresholds, News AI, prospective archive, Web behavior, data, or tests were changed.

### Validation
- Read `AGENTS.md` and current `HANDOFF.md` before answering, per project startup-continuity rules.
- Inspected latest selection `output/edge_scout/selections/select-20260820_225251/` and latest News review `output/edge_scout/news_reviews/news-review-20260820_225429/`.
- Latest selection has 14 SMC candidates for signal date `2026-08-20`; latest News AI summary has 14/14 successful AI attempts, `priority_review=0`, `standard_review=10`, `risk_excluded=4`.
- No tests, scans, data updates, or backtests were run.

### Risks / Review Notes
- Interpretation must remain read-only human-review prioritization, not personalized buy/sell advice.
- Existing contract remains: SMC candidate admission and deterministic order are fixed; diagnostics and News AI are review prompts only and must not be promoted without prospective evidence.
- In final answer, separate the 14 candidates into high-priority human review, cautious review, and temporary skip/risk-excluded buckets based on current fields only.

## Task: Add safe daily SMC+News one-key workflow

### Changed Files
- `main.sh`: added `daily [--top N]` CLI route, help text, and an interactive menu option for the daily SMC+News one-key workflow.
- `scripts/edge_scout_scan.sh`: added `daily` orchestration with automatic-date-only validation, data update after arg validation, exact SMC selection binding, duplicate prospective-archive preflight, optional News AI review/archive, maturity audit, and final concise human-review summary.
- `scripts/archive_smc_news_prospective.py`: added `--check-existing-signal-date` preflight mode and default signal-date duplicate skip before publishing a new SMC+News prospective archive.
- `src/ashare_edge_scout/smc_news_prospective.py`: added helper functions to resolve selection signal date and find an existing canonical SMC+News snapshot for that signal date.
- `tests/test_main_script.py`: added `daily` help/delegation/menu tests and daily shell-flow coverage for new-signal, duplicate-signal, and manual-as-of rejection paths.
- `tests/test_smc_news_prospective.py`: added duplicate preflight/helper/archive CLI skip coverage.
- Ignored outputs created during validation: a duplicate-check daily selection under `output/edge_scout/selections/select-20260820_213223/` and audit `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T133404Z.json`.

### Behavior / Logic Changes
- New `./main.sh daily [--top N]` / `./scripts/edge_scout_scan.sh daily [--top N]` runs the daily read-only workflow: update/check data, automatic-date SMC selection, duplicate signal-date preflight, News AI review and archive only when no canonical archive exists, then SMC+News maturity audit and a concise summary.
- `daily --as-of DATE` is rejected before data update/network checks; manual historical review remains `select-review --as-of DATE` and still does not enter prospective archive.
- Duplicate prevention is signal-date based. If a canonical SMC+News archive already exists for the selected signal date, `daily` skips News AI and new archive; direct archive CLI calls also skip publishing a second archive for the same canonical signal date.
- News AI remains human-review-only and unvalidated; no SMC admission, ranking, threshold, risk exclusion, production, broker, execution, P&L, or return behavior was changed.

### Validation
- Local static/syntax: `bash -n main.sh scripts/edge_scout_scan.sh`; Python compile for `scripts/archive_smc_news_prospective.py`, `src/ashare_edge_scout/smc_news_prospective.py`, `tests/test_main_script.py`, and `tests/test_smc_news_prospective.py`; `git diff --check` all passed.
- Local focused tests passed: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_main_script.py tests/test_smc_news_prospective.py tests/test_news_ai_review.py -q --tb=short` (`46 passed`).
- Local full suite passed: `PYTHONPATH=src .venv/bin/python -m pytest -q` (`404 passed, 3 skipped`).
- Help checks passed: `./main.sh help` and `./scripts/edge_scout_scan.sh help` both show `daily [--top N]`.
- Functional rejection check passed: `./main.sh daily --as-of 2026-08-20` exits `2` without running data update.
- Functional duplicate check passed on current data: `./main.sh daily --top 5` selected signal date `2026-08-20`, found existing canonical archive `smc-news-20260820_210521`, skipped News AI and archive, ran audit, and did not create a new `smc-news-*` archive.
- Remote validation: WSL TCP reached `10.20.98.161` but SSH session closed immediately during `./scripts/remote_test_env.sh check`; Doris was reachable, but default `python3` is unsupported `3.9.6`, so no remote test run was performed.

### Risks / Review Notes
- Current SMC+News evidence remains immature: latest daily audit still reports `canonical_smc_news_snapshots=2`, `mature_all_smc=0`, `parent_maturity_sufficient=False`, `promotion_evidence_sufficient=False`, `evidence_sufficient=False`.
- Do not rerun `daily` or `select-review` expecting a new prospective cohort while local latest signal date remains `2026-08-20`; it will intentionally skip the duplicate archive path.
- Next exact action after future rows advance beyond `2026-08-20`: run `./main.sh daily` once; it should collect the new automatic cohort, archive it once, then audit.
- Working tree still includes many pre-existing modified/untracked files from prior sessions. If committing, inspect/stage deliberately and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Continue SMC+News prospective evidence after 2026-08-20 data availability

### Changed Files
- `scripts/edge_scout_scan.sh`: fixed macOS Bash 3.2 `set -u` empty-array expansion failure in no-arg `select-review` by calling `cmd_select` without expanding an empty `original_args` array.
- `tests/test_main_script.py`: added no-argument `select-review` regression coverage for exact selection/news/archive binding.
- `HANDOFF.md`: recorded this continuation state.
- Ignored outputs created: `output/edge_scout/selections/select-20260820_205728/`, `output/edge_scout/news_reviews/news-review-20260820_205908/`, `output/edge_scout/smc_news_prospective/smc-news-20260820_210521/`, and `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T130536Z.json`.

### Behavior / Logic Changes
- `select-review` with no additional args now works under macOS `/bin/bash` 3.2 with `set -u`; argument-bearing behavior is unchanged.
- Local data freshness/update confirmed BaoStock and local latest trade date `2026-08-20`, coverage `7341/7355 = 0.9980965329707682`, so one new automatic SMC+News cohort was collected.
- New signal date `2026-08-20`; SMC candidate count 14; news review states: priority_review 0, risk_excluded 2, remaining reviewed candidates shown as cautious/standard-style output.
- New SMC+News prospective archive: `output/edge_scout/smc_news_prospective/smc-news-20260820_210521/`.

### Validation
- `./main.sh update` completed successfully and reported local data current at `2026-08-20`.
- Initial `./main.sh select-review` failed before selection due to `scripts/edge_scout_scan.sh: line 336: original_args[@]: unbound variable`; fixed and validated.
- `bash -n scripts/edge_scout_scan.sh main.sh` passed.
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_main_script.py -q` passed: `11 passed`.
- Retried `./main.sh select-review`; completed selection, news review, and prospective archive successfully.
- `./main.sh audit-smc-news` produced `canonical_smc_news_snapshots=2`, `mature_all_smc=0`, `parent_maturity_sufficient=False`, `promotion_evidence_sufficient=False`, `evidence_sufficient=False`.

### Risks / Review Notes
- Current status: evidence collection advanced but remains immature; no SMC/News selector, ranking, threshold, risk exclusion, or production behavior should be promoted.
- Do not rerun `./main.sh select-review` again for unchanged `2026-08-20` data; wait for rows after `2026-08-20` before collecting the next automatic cohort.
- Next exact action after future data is available: verify freshness, run `./main.sh select-review` once for the new signal date, then `./main.sh audit-smc-news`.
- The no-arg `select-review` shell fix is intentionally minimal; broader streaming-output improvements remain a separate optional task.

## Task: Recheck SMC+News prospective evidence availability

### Changed Files
- `HANDOFF.md`: recorded the data-availability recheck only.
- No scanner, selector, news review, archive, audit, or data files were changed.

### Behavior / Logic Changes
- None. `select-review` was deliberately not rerun because the latest local research date remains the existing archive signal date.

### Validation
- Local read-only Parquet scan: 7,351 files; maximum observed `date` remains `2026-08-19`.
- WSL primary environment check passed: `./scripts/remote_test_env.sh check` reached `10.20.98.161`; 20 CPU, 19Gi memory, project ready.
- No data update, selection, archive, or maturity audit was run.

### Risks / Review Notes
- Status: blocked on data newer than `2026-08-19`; the canonical SMC+News archive remains `output/edge_scout/smc_news_prospective/smc-news-20260820_152025/`.
- Do not rerun `./main.sh select-review` against this unchanged signal date; it would create duplicate prospective evidence.
- A prior `./main.sh update` approval was rejected. Do not retry it without renewed authorization.
- Next exact action once a data update is approved or newer rows are available: verify freshness, run `./main.sh select-review` once for the new cohort, then run `./main.sh audit-smc-news`.

## Task: Implement audit hardening fixes

### Changed Files
- `main.sh`, `scripts/edge_scout_scan.sh`, `scripts/remote_test_env.sh`, `README.md`: clarified SMC+News CLI/help wording, exact artifact binding, display-only `--top`, shell hygiene, and remote sync exclusions.
- `tests/test_edge_scout_scheduler.py`, `tests/test_main_script.py`, `tests/test_remote_test_env.py`: added/updated portability, CLI, and static hygiene coverage.
- `src/ashare_edge_scout/research_web.py`, `src/ashare_edge_scout/web_static/app.js`, `tests/test_research_web.py`: added dashboard manual-only fallback without latest publication and prevented `buy_reference` from being displayed as last/close.
- `src/ashare_edge_scout/data_sources.py`, `src/ashare_edge_scout/operations.py`, `src/ashare_edge_scout/scanner.py`, `scripts/check_edge_scout_data_update.py`, related tests: added explicit expected/readable/skipped/latest freshness denominator evidence while preserving compatibility tuple API.
- `src/ashare_edge_scout/news_ai_review.py`, `scripts/review_smc_news.py`, `src/ashare_edge_scout/smc_news_prospective.py`, `scripts/audit_smc_news_prospective.py`, related tests: added all-AI-failed technical-only status and split SMC+News parent maturity from promotion sufficiency.
- `docs/2026-08-20-smc-news-prospective-contract.md`: added durable SMC+News prospective/replay contract.
- `scripts/evaluate_signal_hit_rates.py`, `scripts/evaluate_joint_strategy.py`, `scripts/evaluate_v2_support_reclaim.py`, `scripts/evaluate_bullish_engulfing_confirmation.py`: added historical research metadata fencing without recalculating metrics.

### Behavior / Logic Changes
- `select-review` now parses exact `run_directory=` outputs and passes exact selection/news run paths into review/archive instead of falling back to latest artifacts; manual `--as-of` still skips prospective archiving.
- News review summary now records `ai_attempt_count` and `technical_context_candidate_count`; all attempted technical-only AI failures produce `technical_only_ai_failed` and CLI exit code 3 rather than clean success.
- SMC+News audit now exposes `parent_maturity_sufficient`, `promotion_evidence_sufficient`, requirements, and failure reasons; compatibility `evidence_sufficient` aliases promotion sufficiency, not parent maturity.
- Web dashboard can load manual research-watchlist rows even when no latest publication exists; malformed existing publications remain fail-closed.
- Freshness evidence now reports explicit denominator details while retaining the existing conservative coverage policy based on expected file count.
- Historical research outputs gained read-only/historical/prospective-boundary metadata; no SMC selector thresholds, ranking, target, horizon, or admission logic changed.

### Validation
- Static checks passed: `git diff --check`; `bash -n main.sh scripts/edge_scout_scan.sh scripts/edge_scout_web_control.sh scripts/remote_test_env.sh`; Python compile for changed scripts/modules; `node --check src/ashare_edge_scout/web_static/app.js`.
- Focused local audit-fix tests passed: `71 passed` for scheduler/main/remote/news/SMC+News/web/freshness/data-update tests.
- Full local suite passed: `PYTHONPATH=src .venv/bin/python -m pytest -q` (`396 passed, 3 skipped`).
- WSL primary environment check succeeded on `10.20.98.161`; sync-code no longer transferred `.claude/settings.local.json` (only `.claude/` directory entry appeared).
- Focused WSL audit-fix tests passed: `71 passed`.
- Full WSL suite passed: `./scripts/remote_test_env.sh test -q` (`396 passed, 3 skipped`).

### Risks / Review Notes
- Working tree still contains many pre-existing modified/untracked files from prior sessions. If committing, inspect/stage only intended files and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.
- The `select-review` shell implementation captures command output before printing it; progress still appears, but not streaming live during the child process. If live progress during long AI calls is required, replace with a tee/temp-file streaming capture helper.
- Historical raw-row label scripts were fenced with metadata only; deeper tradable-row refactors for old studies remain a separate task if those scripts are revived as evidence-bearing.
- Do not claim News AI improves precision from these changes; current SMC+News prospective archive remains pending and promotion sufficiency is false until future gates pass.

## Task: Full project audit synthesis

### Changed Files
- `HANDOFF.md`: recorded final read-only audit synthesis and validation status.
- No runtime/source/test files were intentionally changed by the final synthesis.

### Behavior / Logic Changes
- None. This was an audit only; no scanner, selector, web, data-update, research, or shell behavior changed.

### Validation
- Ran static checks locally: `git diff --check`, shell syntax for `main.sh scripts/edge_scout_scan.sh scripts/edge_scout_web_control.sh scripts/remote_test_env.sh`, Python compile for changed Python entrypoints, and `node --check src/ashare_edge_scout/web_static/app.js`; all passed.
- Ran focused local tests for changed flows: `tests/test_edge_scout_data_update.py tests/test_edge_scout_publisher.py tests/test_edge_scout_scanner.py tests/test_edge_scout_web_control.py tests/test_main_script.py tests/test_research_web.py tests/test_news_ai_review.py tests/test_smc_news_prospective.py tests/test_smc_news_replay.py tests/test_stock_selector.py`; `92 passed`.
- WSL primary environment check succeeded and focused WSL tests for the same set passed (`92 passed`).
- Local full suite passed: `388 passed, 3 skipped`.
- WSL full suite failed only at `tests/test_edge_scout_scheduler.py::test_launchd_plist_is_valid_and_runs_weekdays_after_close` because WSL lacks macOS `plutil`; this is a cross-platform test assumption, not evidence that the plist is invalid.
- Reviewed three independent audit streams: current diff correctness review, runtime/product-flow audit, and research/evidence-chain audit. Verified that `classify_tier()` currently never returns `rejected`, so the early runtime note about `tier_type == rejected` carrying `Tier` should not be reported as stated.

### Risks / Review Notes
- Highest-priority fixes to consider next: dashboard/manual watchlist should work without a latest publication; SMC+News audit should split parent-maturity from AI-promotion sufficiency; `select-review` should pass exact selection/news run paths instead of relying on latest resolution; research scripts using raw future rows should be fixed or clearly deprecated; all-AI-failed technical-only reviews should not report clean success.
- Medium fixes: help/README wording for `select-review --as-of`, 59.74% target-touch caveat, `review-news --top` display-only semantics, WSL/macOS `plutil` test portability, data coverage denominator naming, and UI header use of `buy_reference` as last/close fallback.
- Release hygiene risk remains high: working tree has many tracked and untracked changes; stage deliberately and never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files.

## Task: Current diff correctness review

### Changed Files
- `HANDOFF.md`: recorded this review handoff only.

### Behavior / Logic Changes
- No scanner, selector, web, data update, or research logic changed by this review.

### Validation
- Read `AGENTS.md` and newest `HANDOFF.md` before review.
- Inspected `git diff @{upstream}...HEAD` and `git diff HEAD`; working tree has tracked modifications plus many untracked files.
- Reviewed surrounding code for main menu dispatch, research label generation, joint/walk-forward study selection, and SMC news AI review status handling.

### Risks / Review Notes
- Findings to report: interactive SMC menu dispatch runs `select-review`; joint/walk-forward labels count suspension/calendar rows; joint strategy selection crashes on sparse yearly cells; signal hit-rate study has the same raw-row future-label issue; news AI review can report success when all technical-only AI calls fail.
- No tests or scans were run for this review.

## Task: Read-only audit of NCN runtime/product flows

### Changed Files
- `HANDOFF.md`: updated this continuation note only, per project handoff rule.
- Runtime/source/test files intentionally not changed; user requested a read-only audit.

### Behavior / Logic Changes
- None. No scanner, publisher, web, data-update, shell entrypoint, or test behavior changed.

### Validation
- Read `AGENTS.md`, `HANDOFF.md`, `main.sh`, `scripts/edge_scout_scan.sh`, `scripts/edge_scout_web_control.sh`, `scripts/edge_scout_web.sh`, `scripts/check_edge_scout_data_update.py`, `src/ashare_edge_scout/research_web.py`, `publisher.py`, `scanner.py`, `signal_scoring.py`, `data_sources.py`, `intraday_data.py`, `research_watchlist.py`, `news_ai_review.py`, `scripts/select_stocks.py`, `scripts/review_smc_news.py`, `src/ashare_edge_scout/web_static/app.js`, and focused tests.
- Used read-only `rg` searches for classifier/review/watchlist/boundary terms.
- No tests, scans, web starts, or data updates were run.

### Risks / Review Notes
- Audit findings to report: blocker candidate in `scanner.py` where rejected `tier_type` results can still carry a `Tier`; should-fix issues in `select-review` dropping `--top` for news/archive, data coverage denominator counting unreadable parquet files, shell/test mismatch, and Web dashboard requiring a publication despite manual monitor messaging.
- Exact next action if fixing: add focused regression tests for each finding before changing code, especially conservation/publication tests for rejected scanner rows and CLI propagation tests for `select-review --top`.
- Do not add trading/P&L/broker semantics; keep watchlists code-only and research-only.

## Current Continuation State

### Task
- Continue SMC+News prospective evidence collection/maturity checks without changing selector logic.
- Current SMC+News prospective archive: `output/edge_scout/smc_news_prospective/smc-news-20260820_152025/`.
- Archive signal date: `2026-08-19`; 25 candidates; review states: standard 18, risk_excluded 4, ai_unavailable 2, insufficient_evidence 1, priority_review 0.

### Changed Files
- `HANDOFF.md`: compressed active continuation state.
- `docs/handoff-archive-2026-08-20.md`: archived the pre-compression handoff verbatim.
- Recent ignored audit output: `output/edge_scout/smc_news_prospective_audits/smc-news-audit-20260820T082251Z.json`.

### Behavior / Logic Changes
- No scanner, SMC selector, news review, replay, web, or prospective archive behavior changed during the compression.
- Current evidence still does not support changing SMC admission, ranking, thresholds, risk exclusions, news-review states, or production behavior.

### Validation
- Latest maturity audit: `./main.sh audit-smc-news` produced `smc-news-audit-20260820T082251Z.json`; canonical snapshots 1, mature_all_smc 0, `evidence_sufficient=false`.
- Audit details: all 25 observations from `smc-news-20260820_152025` remain `pending`.
- Read-only local data check found 7,351 Parquet files; latest available research date max remains `2026-08-19`, so data has not advanced beyond the archive signal date.
- WSL primary environment was reachable in the latest check: `./scripts/remote_test_env.sh check` reached `10.20.98.161`, 20 CPU, 19Gi memory, project ready.
- A prior `./main.sh update` tool call in this continuation was rejected by user/tool approval; do not retry that exact command without renewed user approval.

### Risks / Review Notes
- Do not rerun `select-review` solely on the same stale `2026-08-19` signal date to create duplicate prospective archives.
- Next exact action when data update is approved or new BaoStock/local rows are available: run data freshness/update, then `./main.sh select-review` to collect a new automatic cohort, then `./main.sh audit-smc-news`.
- Keep `replay-smc-news` separate as simulation-only artifact audit; never use replay or historical backfill as prospective win-rate evidence.

## Stable NCN Boundaries

- NCN is a standalone, read-only A-share research scanner.
- Do not add broker login, orders, leverage, paper trading, portfolio accounting, return/P&L calculation, live-trading behavior, or personalized buy/sell instructions.
- Keep `yaml/edge_scout_v1.yaml` with `production_enabled: false`.
- `PFrontStockData/` contains adjusted research data only; never use it as execution, matching, or return input.
- Runtime imports must stay within `ashare_edge_scout` or declared third-party dependencies; do not depend on `Stock/CN`, `CNstock`, or `a_share_short_swing`.
- `config/research_watchlist.json` is an ignored codes-only research watchlist; do not add cost, quantity, cash, transactions, P&L, or portfolio semantics.

## Current SMC Phase-1 Contract

- Phase-1 objective is selected-stock precision / false-positive reduction for read-only human review, not profit proof.
- Fixed selector workflow: after T-1 closes, select unchanged `smc_medium_buy` candidates passing existing Main Board, non-ST, listing-age, price, liquidity, trading-status, suspension, and near-limit-up hard gates.
- Entry reference for validation is next stock-tradable T open; target-touch contract is `T_open * 1.03`, observed only on T+1 through T+5 highs, excluding T high.
- Selector output does not fetch T open, place/simulate buys or sells, model fills, track P&L, or calculate returns.
- Ranking is deterministic human-review order: fewer warning annotations first, then higher T-1 amount, then code. Warnings do not remove primary candidates. `--top` limits display only; saved output contains all candidates.
- Historical Phase-1 result: 100,893 mature candidates, 60,277 target touches, 40,616 non-touches, 59.7435% target-touch rate, Wilson 95% 59.4405%-60.0457%, same-entry-date admitted baseline 53.5627%, lift +6.1808pp.
- Stability summary: selection 2021-2023 was 60.0024%; audit 2024-present was 59.5638%; frozen stability gates passed.
- Evidence file retained: `t-open-plus3-five-day-win-rate-2021-present.json`; result SHA-256 `4f25a889c3081c558873048a7086d5e26aa3def7725664c79f30392b2e575355`; code-list SHA-256 `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`.
- Interpretation boundary: 59.74% is historical daily-high target-touch classification, not realized profit. T open is not proof of a buy fill, and daily high is not proof a queued +3% sell filled. Fees, taxes, slippage, limit-state execution, and T+5 fallback exits are not modeled.
- Do not retune SMC thresholds, target, horizon, warning exclusions, or gates from this inspected result.

## SMC Diagnostics / A-Class / Futu Results

- SMC selector schema is `ncn_smc_stock_selector_v4`; diagnostics are annotation-only: `base_breakout_start`, `pullback_reacceleration`, `high_position_chase`, `unclassified_start_diagnostic`.
- Diagnostics do not affect admission, ranking, `smc_medium_buy`, risk warning count, or saved candidate count.
- WSL SMC diagnostic/risk/quality validations found no tested single-risk exclusion, positive-quality group, or fixed additive quality score that passed pre-registered gates. Do not promote them.
- `diag_high_position_chase` is visible for human review but not validated as a high-priority selector; do not exclude it automatically.
- `diag_pullback_reacceleration` underperformed and should not be used as a priority group.
- A-class base-breakout selector exists separately under `output/edge_scout/a_class_selections`; do not merge into SMC flow without explicit validation. Historical validation had only 7 mature observations despite high point estimate, so do not promote A-class V1.
- Futu MKF/DXBD/GDING confluence tests did not justify standalone promotion. `DXBD+GDING` carried the effect but was weak as standalone and underperformed inside SMC; MKF-inclusive pairs/all-three are rejected.

## News AI Review Contract

- `./main.sh review-news --top N` reviews the latest immutable SMC selection by default; `--selection-run DIR` selects one explicitly.
- `./main.sh select-review` runs automatic SMC selection, news+K-line AI review, and SMC+News prospective archive when the source selection is prospectively eligible.
- Review output is immutable under ignored `output/edge_scout/news_reviews/<run-id>/` and bound to the source `candidates.json` hash.
- News cache is `.runtime/news_cache/<code>.json`, 7-day retention, 6-hour refresh, per-source cap 100. Immutable review outputs preserve raw `items`, filtered `ai_evidence_items`, and `technical_context`.
- Current recommendation: keep the default 7-day news window for short-cycle SMC review; if longer event context is needed, build a separate immutable long-horizon event/risk archive, not by extending mutable `.runtime/news_cache`.
- AI states are `priority_review`, `standard_review`, `risk_excluded`, `insufficient_evidence`, and `ai_unavailable`.
- Favorable AI cannot bypass SMC and cannot become a buy recommendation. API/news/model failures fail closed and never produce priority.
- `priority_review` is experimental human-review ordering only. Promotion gates: unchanged future SMC candidates, >=300 mature reviewed observations, >=120 publication dates, >=50 codes, >=20% parent-candidate retention, >=+3pp target-touch precision versus same-date parent SMC, priority Wilson lower 95% above parent precision, and positive annual lifts. If gates miss, reject without prompt/threshold mining.

## Prospective Evidence Contracts

### Market Prospective Snapshot
- Automatic market publications can freeze `prospective_snapshot.json`; manual `--as-of` snapshots are permanently excluded.
- For repeated signal dates, only the earliest valid publication is canonical.
- Fixed prospective label: from archived T close, among next five tradable closes at least one reaches +3% and none closes below -3%; fewer than five is `pending`; archived/current T-close mismatch is `data_revision` and excluded.
- First valid market snapshot: `output/edge_scout/market-20260816_084616/prospective_snapshot.json`, 395 baseline rows, 6 selected rows.
- First audit: `output/edge_scout/prospective_audits/audit-20260816T004911Z.json`, all 6 selected pending, `evidence_sufficient=false`.

### SMC+News Prospective Archive
- Current canonical SMC+News archive: `output/edge_scout/smc_news_prospective/smc-news-20260820_152025/`, signal date `2026-08-19`, 25 candidates.
- Archive schema: `ncn_smc_news_prospective_v1`; read-only/classification-only; production disabled; bound by source selection/news review hashes.
- Old news-review runs lacking prospective eligibility are correctly rejected and must not be backfilled.
- Current audits report mature_all_smc 0 and `evidence_sufficient=false` because local data has not advanced beyond `2026-08-19`.

### SMC+News Replay
- `./main.sh replay-smc-news --dry-run` is descriptive simulation-only artifact audit. It may inspect valid current-schema news-review artifacts, but it is not point-in-time/prospective evidence.
- Replay output path is `output/edge_scout/smc_news_replay/`; do not use replay cohorts to change SMC admission/ranking or to claim news/AI improves win rate.

## Strategy Research Decisions Not To Repeat

- Do not port Astock formula weights, reported Sharpe, hard-coded 65% values, `WinRate_V2`, stockAI model probabilities, CNstock market-state labels, branch thresholds, AI/news scores, portfolio rules, or execution logic into NCN.
- Local reference projects (`AlphaGPT`, `Astock`, `stock`, `stock1`, `stockAI`, `CNstock`, `CNstock-branches`) did not provide credible directly transferable evidence.
- Main issues in rejected reference work: same-date cross-section used as time series, YAML profile renames bypassing intended filters, OHLCV formula mining, hard-coded/uncalibrated win-rate labels, and stock-block `TimeSeriesSplit` instead of global-date/purged validation.
- RSRS/MHPG, strict MkF green-zone exit, Shengbei+KDJ, Futu indicator ranking/combination, Nison candlestick variations, bullish engulfing confirmation, rising-three-methods, share-repurchase count, Dragon-Tiger institutional net buying, CNInfo earnings forecast/express PDF coverage, and daily-bar SMC quality composites all failed frozen gates or coverage requirements. Do not re-mine those same historical windows for threshold variants.
- Walk-forward adaptive strategy evaluation selected rules on 508/868 dates but produced 31.57% selected-candidate precision versus 32.01% admitted baseline; do not promote adaptive selector, `mhpg`, `mhpg_regime`, or `setup`.
- Further win-rate work requires genuinely new revision-safe point-in-time information or unchanged prospective evidence. A 70% precision claim requires pre-registered sample, annual coverage, out-of-sample stability, and confidence-bound gates.

## Web / Runtime Notes

- Web server remains stdlib serial `HTTPServer`; avoid threaded PyArrow reads because Python 3.14 concurrent reads caused native crashes.
- `/api/health` is the managed web-control liveness endpoint; avoid requiring a publication for health checks.
- Sina/Eastmoney intraday data have no exchange latency SLA; preserve provider/source timestamps, freshness, forming-bar state, warnings, bounded retry/cache behavior, and explicit last-observation fallback.
- Manage Web only through `./scripts/edge_scout_web_control.sh start|stop|restart|status` or `main.sh`.

## Test Environment Priority

1. WSL: host `10.20.98.161`, port `22`, user `adminwsl`; first choice when reachable and set up. Use `scripts/remote_test_env.sh` when applicable.
2. Doris: host `ts.dorisw.kdns.fr`, port `56731`, user `chinaadmin`; second choice, especially for Doris data layer/backtests. Default `python3` was previously unsupported `3.9.6`; use a verified compatible isolated interpreter.
3. Local MacBook Air: last resort for backtests/validation unless WSL/Doris are unavailable or unsuitable.

- WSL/P16V: 32 GB total but omlx may reserve ~30 GB. Check memory before heavy work; set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
- Doris/Maxstudio: 64 GB total, about 34 GB available after omlx; 12-16 workers may be feasible for CPU-bound tasks, 8-10 for memory-bound.
- Local MacBook Air: 24 GB; up to 8 workers safe for most local tasks, 4-6 for memory-heavy studies.
- Record environment, worker count, and observed memory/pressure in handoff for every backtest or substantive validation.

## Commands To Remember

- Setup: `./scripts/setup.sh`
- Default tests: `.venv/bin/python -m pytest -q`
- Focused tests: `.venv/bin/python -m pytest tests/test_news_ai_review.py -q`
- Interactive menu: `./main.sh`
- Automatic SMC + chained news/K-line AI review + prospective archive: `./main.sh select-review`
- SMC selection only: `./main.sh select` or `./main.sh select-local`
- Manual AI review: `./main.sh review-news [--selection-run DIR] [--top N]`
- SMC+News maturity audit: `./main.sh audit-smc-news`
- Simulation-only replay dry run: `./main.sh replay-smc-news --dry-run`
- Market prospective audit: `./main.sh audit`
- Web management: `./scripts/edge_scout_web_control.sh start|stop|restart|status`
- After Web changes: focused Python test, `node --check src/ashare_edge_scout/web_static/app.js`, and `git diff --check`.

## Git / File Safety

- The working tree has many pre-existing modified/untracked files from prior sessions. If committing, inspect full status/diff and stage only intended files.
- Never include `Key/`, `.runtime/`, `output/`, pycache, logs, or credential-like files in commits.
- `docs/handoff-archive-2026-08-20.md` contains the full pre-compression handoff for historical detail.
