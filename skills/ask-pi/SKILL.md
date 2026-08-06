---
name: ask-pi
description: Explains how to call pi non-interactively from a shell, script, CI job, or cron task using the `openai-codex/gpt-5.6-sol` model. Use this whenever the user wants to pass a question from the CLI, automate pi, run a one-shot unattended prompt, capture pi output in a variable, or wrap pi in bash.
compatibility: Requires `pi` on PATH and an authenticated pi setup that can access `openai-codex/gpt-5.6-sol`.
---

# Ask Pi

Use this skill when the user wants to ask pi a question from the command line without opening the interactive TUI.

The important part is to run pi in **print mode** so it answers once and exits:

```bash
pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max "<question>"
```

## Default behavior

When helping with this workflow:

1. Prefer a **single unattended command** first.
2. Use `-p` / `--print` so pi writes the answer to stdout and exits.
3. Use `--no-session` for automation unless the user explicitly wants session history.
4. Always pass `--model openai-codex/gpt-5.6-sol`. Do NOT use `github-copilot/*` — that provider has no API key configured and the command fails with "No API key found for github-copilot."
5. Always pass `--thinking max` so the review uses maximum reasoning effort.
6. Give the user a copy-paste-ready command, not an interactive workflow.

## Ready-to-use commands

### Ask one question

```bash
pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max "What ports are listening on this machine?"
```

### Pass the question from a shell variable

```bash
QUESTION="Summarize the changes in this repository"
pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max "$QUESTION"
```

### Save the answer into a shell variable

```bash
ANSWER=$(pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max "Write a conventional commit message for the current git diff")
printf '%s\n' "$ANSWER"
```

### Use stdin for larger context

Pi merges piped stdin into the prompt in print mode, which is useful for unattended scripting.

```bash
git diff --stat | pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max "Summarize this diff briefly"
```

### Read from a file and ask a question

```bash
pi -p --no-session --model openai-codex/gpt-5.6-sol --thinking max @README.md "Summarize the main setup steps"
```

## Authentication note

This workflow is unattended only after pi is already authenticated.

Use one of these approaches ahead of time:

- Log in once in pi and choose the OpenAI Codex provider via `/login`
- Use a configured pi environment where the selected provider is already available

If authentication is missing, the unattended command will fail before the model runs.

## How to respond

When using this skill, respond with:

1. The exact command to run
2. A short explanation of why `-p` makes it unattended
3. An optional variant for variables, stdin, or shell scripts if relevant

Prefer short, operational answers. The user is usually trying to automate pi, not learn the whole CLI.
