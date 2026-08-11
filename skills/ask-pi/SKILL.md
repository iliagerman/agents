---
name: ask-pi
description: Call pi non-interactively from a shell, script, CI job, or cron task, or launch an independent unattended code review, using `openai-codex/gpt-5.6-sol`. Use whenever the user wants to ask pi or another AI from the CLI, automate pi, run a one-shot prompt, capture pi output, or have pi, GPT-5.6 Sol, or a second AI reviewer inspect local code, changes, commits, or branches.
compatibility: Requires `pi` on PATH and an authenticated pi setup that can access `openai-codex/gpt-5.6-sol`.
---

# Ask Pi

Use this skill when the user wants to ask pi a question from the command line without opening the interactive TUI.

Run pi in print mode with extensions and startup network operations disabled. This prevents configured MCP extensions or update checks from blocking unattended startup. `--offline` does not disable the model request.

```bash
pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol "<question>"
```

## Default behavior

1. Prefer one unattended command.
2. Use `-p` / `--print` so pi writes the answer to stdout and exits.
3. Use `--no-session` unless the user explicitly wants session history.
4. Use `--no-extensions` so configured extensions and MCP children cannot block startup.
5. Use `--offline` to skip startup update checks, package checks, and telemetry.
6. Always pass `--model openai-codex/gpt-5.6-sol`. Do not use `github-copilot/*`; it fails with `No API key found for github-copilot.`
7. Do not set a thinking level for ordinary questions. Delegated code reviews default to `high`; change it only when the user explicitly requests another level.
8. Give the user a copy-paste-ready command, not an interactive workflow.

## Independent code review

Run the bundled script from the repository root. Resolve `scripts/review.sh` relative to this `SKILL.md`, then run it without asking for confirmation:

```bash
bash "/absolute/path/to/ask-pi/scripts/review.sh"
```

Pass a requested scope as one quoted argument:

```bash
bash "/absolute/path/to/ask-pi/scripts/review.sh" \
  "Review the current branch against origin/main."
```

Reviews use `high` thinking by default. If the user explicitly requests another level, set `PI_REVIEW_THINKING` for that invocation:

```bash
PI_REVIEW_THINKING=max bash "/absolute/path/to/ask-pi/scripts/review.sh" \
  "Review the current branch against origin/main."
```

Allowed values: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`.

The script:

- uses print mode without session persistence
- disables extensions and startup network operations
- selects `openai-codex/gpt-5.6-sol` with `--thinking high` by default, or the explicitly requested `PI_REVIEW_THINKING` value
- approves project-local context without prompting
- exposes only `read` and `bash`, removing direct edit/write tools
- prints a start message and a heartbeat every 15 seconds
- kills the process after 900 seconds and exits with status 124
- otherwise exits with pi's status and prints pi's complete review

The review prompt forbids file changes. With no scope, review staged and unstaged changes; if the working tree is clean, compare the current branch with its default base branch.

Stream progress while the command runs. After completion, return pi's review without substituting your own. Preserve file paths, line numbers, severity, and technical details. If pi fails or times out, report its exact output and exit status; do not automatically retry.

## Ready-to-use commands

### Ask one question

```bash
pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol "What ports are listening on this machine?"
```

### Pass the question from a shell variable

```bash
QUESTION="Summarize the changes in this repository"
pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol "$QUESTION"
```

### Save the answer into a shell variable

```bash
ANSWER=$(pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol "Write a conventional commit message for the current git diff")
printf '%s\n' "$ANSWER"
```

### Use stdin for larger context

Pi merges piped stdin into the prompt in print mode.

```bash
git diff --stat | pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol "Summarize this diff briefly"
```

### Read from a file and ask a question

```bash
pi -p --no-session --no-extensions --offline --model openai-codex/gpt-5.6-sol @README.md "Summarize the main setup steps"
```

## Authentication note

This workflow is unattended only after pi is authenticated. Log in once through `/login` and choose the OpenAI Codex provider, or use an environment where that provider is already configured.

If authentication is missing, the unattended command fails before the model runs.

## How to respond

For general CLI questions, return the exact command, briefly explain print mode, and add a variable/stdin variant only when useful.

For delegated reviews, return the script's progress and final review. Keep responses operational and short.
