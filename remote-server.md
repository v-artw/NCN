# NCN Remote Server Guide

This document is the shared operational reference for AI tools working on NCN remote environments. It contains connection metadata and safe commands only. Do not add passwords, private keys, API keys, or other credentials here.

## Mandatory Pre-Read Rule

- Before any AI tool uses WSL, Doris, or another remote server for tests, backtests, sync, setup, or artifact retrieval, read this file first.
- Do not rediscover the same Doris/WSL connection, Python, permission, and resource rules from scratch in every session.
- If a remote command is blocked by Claude Code permission policy or auto-mode classification, do not repeatedly retry variants that do the same thing. Apply the recovery rules in this document, then ask the user only if the next action is genuinely permission-sensitive.
- For backtests, use remote resources aggressively within the documented hardware limits. Do not fall back to local while WSL or Doris is reachable and has the required environment.

## Non-Negotiable Boundaries

- NCN is a phased production-adjacent A-share research workbench. Remote validation may cover research, Demo Portfolio, paper/simulation, PMKF/MKF, AI review, risk controls, and audit workflows.
- Do not add or validate live broker login, live order submission, leverage, custody/settlement behavior, unattended real-money execution, real account identifiers, or real-money P&L.
- Use remote systems for validation and bounded research computation only.
- Do not modify remote data, delete remote outputs, or run destructive Git commands unless the user explicitly requests it.
- Do not copy `Key/`, `.env*`, `.runtime/`, `output/`, or `config/research_watchlist.json` between machines.
- Record substantive remote validation in `HANDOFF.md`: environment used, command, worker count for studies, and relevant result.

## Environment Priority

Always attempt environments in this order. Fall back only when the earlier environment is unreachable, lacks a supported Python environment, or is unsuitable for the workload.

1. WSL, first choice for normal tests when reachable.
2. Doris, second choice and preferred for larger data-backed studies.
3. Local MacBook Air, last resort.

## WSL Test Host

| Field | Value |
| --- | --- |
| Host | `10.20.98.161` |
| SSH port | `22` |
| User | `adminwsl` |
| Project directory | `/home/adminwsl/NCN` |
| Default private key | `~/.ssh/id_ed25519` |
| Intended use | Remote pytest, bounded Linux validation |
| Recent status | SSH was recently unreliable: timeout or closure during banner exchange. Recheck before use. |

Use the project wrapper rather than constructing ad hoc sync commands:

```bash
./scripts/remote_test_env.sh check
./scripts/remote_test_env.sh sync-code
./scripts/remote_test_env.sh sync-data
./scripts/remote_test_env.sh setup
./scripts/remote_test_env.sh test tests/test_news_ai_review.py -q
```

Run the complete remote preparation and default test suite only when data synchronization is actually required:

```bash
./scripts/remote_test_env.sh all
```

The wrapper uses key-only SSH with a 10-second connection timeout and synchronizes source/configuration while excluding Git metadata, virtual environments, runtime/output directories, data during `sync-code`, local watchlist, and environment files. `sync-data` separately copies `PFrontStockData/`.

Override only when a different approved WSL endpoint is necessary:

```bash
NCN_REMOTE_TEST_HOST=host NCN_REMOTE_TEST_USER=user \
NCN_REMOTE_TEST_PORT=22 NCN_REMOTE_TEST_DIR=/home/user/NCN \
NCN_REMOTE_TEST_KEY="$HOME/.ssh/id_ed25519" \
./scripts/remote_test_env.sh check
```

For an interactive remote shell:

```bash
./scripts/remote_test_env.sh shell
```

### WSL Capacity And Resource Use

| Field | Value |
| --- | --- |
| Hardware | ThinkPad P16V / WSL2 |
| CPU | 20 logical CPUs observed |
| Physical RAM | 32 GB documented; current `check` may show lower available WSL allocation such as 19 GiB |
| Project path | `/home/adminwsl/NCN` |
| Best use | Normal pytest, Linux validation, bounded full-universe backtests when memory is sufficient |
| Worker guidance | 4-8 workers for most NCN CPU-bound backtests; choose 8 when memory headroom is healthy, reduce to 4 if WSL allocation or `omlx` pressure is tight |

- The `omlx` service can reserve about 30 GB on the Windows host, so always inspect current WSL memory with `free -h` before substantial studies.
- Use WSL fully when it is online: do not choose local merely to avoid remote setup overhead.
- For compute jobs set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and `NUMEXPR_NUM_THREADS=1`.
- If WSL is reachable and `.venv` is ready, run the confirmed backtest there instead of local. Keep long jobs detached or bounded by clear output/log paths.
- Do not run memory-heavy exploratory grids on WSL with high workers if `free -h` shows limited headroom; switch to Doris for larger grids.

### WSL Study Lifecycle

The wrapper manages the checkpointed signal-hit-rate study without leaving an interactive terminal open:

```bash
./scripts/remote_test_env.sh study-start --workers 4
./scripts/remote_test_env.sh study-status
./scripts/remote_test_env.sh study-fetch result.json
./scripts/remote_test_env.sh study-stop
```

Its default remote artifacts are under `.runtime/`; they are intentionally not synced as source code.

### WSL Recovery (Windows Host)

If SSH is reachable at TCP level but does not return an SSH banner, the Windows/WSL host needs repair. From an elevated Windows PowerShell session in this repository, run:

```powershell
.\scripts\start_wsl_then_bootstrap_remote_test_windows.ps1
```

This starts the `Ubuntu` WSL distribution, installs/starts OpenSSH, enables key-only access, recreates the Windows-to-WSL port proxy, and permits local-subnet access on port `22`. It requires administrator privileges and must not be run remotely by an AI without user authorization.

## Doris / Maxstudio Host

| Field | Value |
| --- | --- |
| Host | `ts.dorisw.kdns.fr` |
| SSH port | `56731` |
| User | `chinaadmin` |
| Project directory | `~/NCN` |
| Default private key | `~/.ssh/id_ed25519` |
| Intended use | Data-backed backtests and larger bounded studies |
| Recent status | SSH reachable; system `python3` was `3.9.6`, which is unsupported by NCN. Install or use an isolated verified `>=3.12,<3.15` virtual environment. |

Use explicit, key-only SSH options. Verify the host and Python environment before syncing or executing:

```bash
ssh -p 56731 -i "$HOME/.ssh/id_ed25519" -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  chinaadmin@ts.dorisw.kdns.fr \
  'cd "$HOME/NCN" && hostname && python3 --version && test -x .venv-doris/bin/python && .venv-doris/bin/python --version'
```

### Doris Permission / Startup Recovery

Repeated issue: launching a Doris remote backtest sometimes gets blocked by Claude Code's permission policy or auto-mode classifier, especially when the command includes long SSH, environment variables, shell redirection, backgrounding, or setup/install steps. Do not waste tokens by rediscovering this each time.

Use this escalation path:

1. Prefer a simple foreground SSH command with explicit key-only options, `cd "$HOME/NCN"`, and `.venv-doris/bin/python`. Avoid unnecessary shell tricks, global environment writes, package installation, or destructive cleanup.
2. If a long command is blocked, split it into safe phases: connectivity check, exact file sync, environment check, then the backtest command. Keep each command readable and bounded.
3. If setup/install is the blocked operation, do not use system `python3` as a fallback. Doris NCN work must use `.venv-doris/bin/python`; ask the user to run the setup command manually with `! <command>` only if the venv is missing or broken.
4. If the backtest itself is blocked only because of command shape, simplify the command rather than changing the methodology or falling back to local.
5. If a full Doris grid result already exists and the user only asks for a subgrid extraction, reuse the already completed larger grid result after verifying schema/method/output path, instead of launching a redundant Doris run.
6. When a Doris launch is genuinely blocked and no verified prior output exists, state the exact blocked action and ask for permission or for the user to run the one command. Do not repeatedly try near-identical SSH commands.

Safe Doris command shape for foreground backtests:

```bash
ssh -p 56731 -i "$HOME/.ssh/id_ed25519" -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  chinaadmin@ts.dorisw.kdns.fr \
  'cd "$HOME/NCN" && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv-doris/bin/python scripts/example.py --workers 12 --output .runtime/example.json'
```

### Unsupported System Python

If the remote system `python3` is outside NCN's supported range (`>=3.12,<3.15`), do not run tests or backtests with it. Create an isolated virtual environment in the remote project directory using an already available compatible interpreter, then use that virtual environment for every NCN command.

```bash
# Replace python3.14 with the compatible interpreter confirmed on the remote host.
ssh -p 56731 -i "$HOME/.ssh/id_ed25519" -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  chinaadmin@ts.dorisw.kdns.fr \
  'cd "$HOME/NCN" && python3.14 -m venv .venv-doris && .venv-doris/bin/python -m pip install --upgrade pip && .venv-doris/bin/python -m pip install -e ".[test]"'
```

Do not replace or modify the remote system Python. If no compatible interpreter is installed, report that blocker and request authorization before installing one. Recent validated work used `.venv-doris/bin/python`; verify it before reuse:

```bash
.venv-doris/bin/python --version
```

Synchronize only intended files. Example for a focused test change:

```bash
rsync -az -e "ssh -p 56731 -i $HOME/.ssh/id_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10" \
  src/ashare_edge_scout/example.py \
  chinaadmin@ts.dorisw.kdns.fr:NCN/src/ashare_edge_scout/

rsync -az -e "ssh -p 56731 -i $HOME/.ssh/id_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10" \
  tests/test_example.py \
  chinaadmin@ts.dorisw.kdns.fr:NCN/tests/
```

Do not use broad `--delete` synchronization against Doris unless the user explicitly authorizes it.

Run focused tests and every remote backtest with the verified virtual environment, never `python3` directly:

```bash
ssh -p 56731 -i "$HOME/.ssh/id_ed25519" -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  chinaadmin@ts.dorisw.kdns.fr \
  'cd "$HOME/NCN" && .venv-doris/bin/python -m pytest tests/test_example.py -q'
```

### Doris Capacity And Resource Use

| Field | Value |
| --- | --- |
| Hardware | Maxstudio / Apple M4 Max |
| CPU | Benchmark on first use with `sysctl -n hw.logicalcpu`; plan for high-concurrency CPU-bound work after confirming |
| Physical RAM | 64 GB |
| Effective NCN headroom | About 34 GB when `omlx` reserves about 30 GB |
| Project path | `$HOME/NCN` |
| Required Python | `$HOME/NCN/.venv-doris/bin/python` |
| Best use | Larger data-backed backtests, full-universe grids, heavier MKF/PMKF studies |
| Worker guidance | 12-16 workers for CPU-bound studies when memory pressure is low; 8-10 workers for memory-bound studies or when `omlx` must stay responsive |

- Doris should be used fully for larger backtests when WSL is unavailable, memory-constrained, or unsuitable. Do not fall back to local because of prior setup friction if Doris is reachable and `.venv-doris/bin/python` works.
- Check memory pressure before a backtest using `memory_pressure` and verify that `omlx` remains responsive when relevant.
- For long calculations, set BLAS/OpenMP thread counts to `1` per worker and use a detached process with a PID, log, checkpoint/output file, and explicit status checks when the user has authorized long remote execution.
- Prefer 12 workers as the conservative Doris default for full-universe NCN backtests; increase to 16 only after confirming low memory pressure and CPU-bound workload.
- Preserve remote outputs under `.runtime/` until copied back and validated. Do not delete remote evidence unless the user explicitly asks.

## Common Validation Rules

- Supported Python is `>=3.12,<3.15`. Do not validate with an unsupported interpreter.
- When a remote system Python is incompatible, install/use a project-local virtual environment from a compatible interpreter and run all remote tests, scans, and backtests through its `bin/python`.
- Run the smallest relevant test first. Use the full suite only when scope warrants it.
- For strategy research, pre-register the hypothesis, fixed candidate set, thresholds, budget, and pass/fail implementation decision before computation.
- Remote research artifacts must be copied back and hash-checked before they are relied upon. Preserve immutable output evidence; do not overwrite a completed result.
- Never expose the local proxy or persist proxy variables globally. If a remote task requires Internet access, use a session-scoped reverse SSH tunnel to local `127.0.0.1:1082`, then verify it with a bounded request before downloading anything.

## Local Fallback

If WSL is unavailable and Doris is unavailable or has no supported Python environment, use the local project environment:

```bash
.venv/bin/python -m pytest tests/test_example.py -q
```

State the WSL and Doris failure reason plus the local command in `HANDOFF.md`.

## Useful Project Commands

```bash
./scripts/setup.sh
.venv/bin/python -m pytest -q
./scripts/edge_scout_web_control.sh status
git diff --check
```

For Web changes, also run:

```bash
node --check src/ashare_edge_scout/web_static/app.js
```
