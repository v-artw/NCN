# Claude Code Instructions for NCN

## Startup Continuity

- Before starting any substantive work, read `AGENTS.md` and the newest relevant entry in `HANDOFF.md`.
- Treat `HANDOFF.md` as the continuation state from prior sessions and other agents.
- Do not assume prior chat context is available after restart.
- If the user asks to continue, first summarize the current state from `HANDOFF.md` in one or two sentences, then proceed.

## Shutdown / Handoff

- Before ending a task, pausing, asking another agent to continue, or reporting a blocker, update `HANDOFF.md`.
- The handoff entry must let a fresh agent continue without reading the old conversation.
- Include task status, files changed or intentionally not changed, validation completed, validation pending, next exact action, and risks or directions that must not be repeated.

## Problem Steelman Gate

For complex, ambiguous, high-risk, or direction-setting work, do not answer or implement immediately. First steelman the user's problem and surface what would make the answer specific:

1. State the assumptions the user may be making but has not said out loud.
2. State what missing information would significantly change the answer.
3. State the most common mistake people make when asking this type of question.
4. State what could go wrong if the project acts on a plausible but unverified answer.
5. Ask the single most useful clarifying question for this specific situation.

Apply this gate to strategy research, scanner/watchlist logic, data validation design, backtest methodology, architecture changes, ambiguous bugs, and any change that could affect research conclusions. Skip it for simple bug fixes, clearly specified mechanical edits, formatting, git inspection, focused validation, and other tasks where the success criteria are already explicit.

After the user answers, give the recommendation, reasoning, validation target, what not to do yet, and the smallest next action. Optimize for reducing false confidence, avoiding overfitting, preserving validation consistency, and minimizing unnecessary code changes.

## Boundaries

- Follow `AGENTS.md` for project rules, NCN phased production-adjacent boundaries, validation priority, remote resource priority, and strategy-research stop rules.
- Current authorization is phased production-adjacent work: portfolio-style demo analysis, paper/simulation workflows, PMKF/MKF dashboards, risk controls, and audit hardening are allowed; live broker login, live order submission, leverage, or unattended real-money execution still require a future explicit governance update.
- Do not duplicate long project policy here; keep durable project policy in `AGENTS.md`.
