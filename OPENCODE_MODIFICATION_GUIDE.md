# OpenCode Modification Guide

This guide explains how to modify the project's OpenCode model routing, user model config, agent model selection, permissions, and validation steps.

## Current Design Intent

The project uses two OpenCode model roles:

- `gsykj/gpt-5.6-sol`: high-judgment model for strategy, architecture, A-share signal/risk reasoning, win-rate improvement logic, unclear debugging, and test design.
- `openai/Ornith-1.0-35B-4bit`: bounded execution model for mechanical, explicit, and easily verifiable tasks such as git inspection, push preparation, simple file discovery, formatting checks, concise documentation updates, and `HANDOFF.md` drafting.

The first project phase prioritizes improving selected-stock win rate as read-only research-selection quality. Do not turn this into portfolio return optimization, trading execution, transaction simulation, or personalized trading advice.

## Files To Modify

### 1. `AGENTS.md`

Modify this when changing project-level rules that other coding agents should follow.

Relevant sections:

- `OpenCode Role`
- `Current Project Phase`
- `OpenCode Model Routing`
- `OpenCode Handoff`

Use `AGENTS.md` for durable policy, not temporary experiment notes.

### 2. `/Users/artx/.config/opencode/opencode.json`

Modify this when adding or changing OpenCode providers, model IDs, default model, or model capabilities.

For tool-using coding agents, each custom model should declare:

```json
"tool_call": true
```

Example model entry:

```json
"Ornith-1.0-35B-4bit": {
  "name": "TS Ornith 1.0 35B 4bit",
  "attachment": true,
  "tool_call": true,
  "modalities": {
    "input": ["text", "image"],
    "output": ["text"]
  }
}
```

Do not commit or share this file if it contains API keys.

### 3. `.opencode/agent/*.md`

Modify a specific agent file when changing that agent's model, permissions, or workflow.

For example, `.opencode/agent/github-pusher.md` currently uses:

```yaml
model: openai/Ornith-1.0-35B-4bit
```

Change this only when the agent's task type changes.

Use `openai/Ornith-1.0-35B-4bit` for safe, bounded, mechanical agents.
Use `gsykj/gpt-5.6-sol` only for agents that need strategy, architecture, or A-share reasoning.

### 4. `HANDOFF.md`

Update this after each completed OpenCode task.

Keep the newest entry at the top and use this shape:

```markdown
## Short task title

### Task

- One concise summary bullet.

### Changed Files

- `file1`
- `file2`

### Behavior / Logic Changes

- Reviewer-relevant behavior change.

### Validation

- Exact command or check name.

### Risks / Review Notes

- Remaining risk, skipped validation, or `None`.
```

Do not paste large diffs, full logs, or long reasoning traces.

## How To Change Model Routing

### If a task affects scanner win rate or strategy quality

Use `gsykj/gpt-5.6-sol`.

Examples:

- Changing stock selection criteria.
- Reducing false positives.
- Designing multi-signal confirmation.
- Evaluating trend, volume-price, candle structure, liquidity, volatility, sector fit, or market regime risk.
- Refactoring scanner architecture.
- Debugging unclear failures that may affect correctness.
- Designing tests for research-selection logic.

### If a task is mechanical and easy to verify

Use `openai/Ornith-1.0-35B-4bit`.

Examples:

- `git status`, `git diff`, `git log`, branch and remote checks.
- Commit/push preparation after user confirmation.
- Simple file search and keyword lookup.
- JSON/config validation.
- Formatting checks.
- Short documentation updates.
- Concise `HANDOFF.md` drafting.
- Running tests and summarizing results.

### If unsure

Default to `gsykj/gpt-5.6-sol` when the task involves judgment, strategy, ambiguity, or correctness risk.
Default to `openai/Ornith-1.0-35B-4bit` only when success criteria are explicit and independently verifiable.

## GitHub Pusher Safety Rules

For `.opencode/agent/github-pusher.md`:

- Keep it on `openai/Ornith-1.0-35B-4bit` unless the role expands beyond safe git workflow execution.
- Allow safe read-only git inspection commands.
- Ask before `git add`, `git commit`, and `git push`.
- Deny force push, remote branch deletion, history rewriting, and automatic conflict handling.
- Do not allow code editing tools for this agent.

Important permission-order rule:

- OpenCode permission rules use later matching rules to override earlier matching rules.
- Put broad catch-all deny rules before specific allow/ask rules when the specific rules should remain usable.
- Put dangerous deny rules after broader ask rules when they must override the ask.

Good pattern:

```yaml
permission:
  bash:
    "*": deny
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git remote -v": allow
    "git rev-parse*": allow
    "git branch --show-current": allow
    "git branch -vv": allow
    "git branch *": ask
    "git branch -d*": deny
    "git branch -D*": deny
    "git add *": ask
    "git commit *": ask
    "git push *": ask
    "git push --force*": deny
    "git push -f*": deny
    "git push * --force*": deny
    "git push * -f*": deny
    "git push * --delete*": deny
```

Avoid putting `"*": deny` at the end, because it can override earlier allow rules and disable `bash` for the agent.

## Validation Checklist

Run these checks after modifying OpenCode config or agents.

### Validate JSON and model capabilities

```bash
node -e 'const fs=require("fs"); const p="/Users/artx/.config/opencode/opencode.json"; const c=JSON.parse(fs.readFileSync(p,"utf8")); for (const [provider, pc] of Object.entries(c.provider||{})) { for (const [model, mc] of Object.entries(pc.models||{})) console.log(`${provider}/${model}: tool_call=${mc.tool_call===true}`); }'
```

Expected: every tool-using model prints `tool_call=true`.

### Validate OpenCode resolved config

```bash
opencode debug config
```

Expected: config resolves without parse errors.

### Validate model availability

```bash
opencode models openai
opencode models gsykj
```

Expected: configured model IDs appear in the relevant provider list.

### Validate `github-pusher`

```bash
opencode debug agent github-pusher
```

Expected highlights:

- `model.providerID` is `openai`
- `model.modelID` is `Ornith-1.0-35B-4bit`
- `tools.bash` is `true`
- `tools.edit` is `false`
- `tools.write` is `false`
- `tools.webfetch` is `false`

### Validate allowed and denied bash behavior

Allowed command:

```bash
opencode debug agent github-pusher --tool bash --params '{"command":"git status --short"}'
```

Expected: succeeds.

Denied commands:

```bash
opencode debug agent github-pusher --tool bash --params '{"command":"git push --force"}'
opencode debug agent github-pusher --tool bash --params '{"command":"ls"}'
```

Expected: both are denied by permission rules.

## When To Update This Guide

Update this file when:

- New OpenCode providers or models are added.
- Model routing rules change.
- Agent permission patterns change.
- OpenCode changes permission syntax or deprecates current fields.
- `github-pusher` expands or narrows its responsibilities.

Also update `HANDOFF.md` with a short reviewer-facing summary after any such change.
