---
name: pi-code-review
description: Launch an independent, fully unattended code review from Claude Code by running pi with `openai-codex/gpt-5.6-sol` and showing progress while it works. Use whenever the user asks Claude to have pi, GPT-5.6 Sol, or a second AI reviewer review local code, working-tree changes, staged changes, a commit, or a branch before commit, push, or merge.
compatibility: Requires `pi` on PATH and authentication for `openai-codex/gpt-5.6-sol`.
---

# Pi Code Review

Delegate the review to pi. Run the bundled script from the repository root so pi can inspect project rules, changed files, and surrounding code.

## Run the review

Resolve `scripts/review.sh` relative to this `SKILL.md`, then run it through Claude Code's Bash tool. Do not ask for confirmation:

```bash
bash "/absolute/path/to/pi-code-review/scripts/review.sh"
```

Pass a user-requested scope as one quoted argument:

```bash
bash "/absolute/path/to/pi-code-review/scripts/review.sh" \
  "Review the current branch against origin/main."
```

The script is fully unattended. It:

- uses pi print mode and disables session persistence
- selects `openai-codex/gpt-5.6-sol` exactly
- approves project-local context without prompting
- removes pi's direct edit/write tools
- emits a start message and a heartbeat every 15 seconds
- exits with pi's status and prints pi's complete review

Shell access remains available so pi can inspect git. The review prompt forbids file modification.

When no scope is supplied, review staged and unstaged changes. If the working tree is clean, compare the current branch with its default base branch.

Return progress output while the command runs. After completion, return pi's review without substituting Claude's own review. Preserve file paths, line numbers, severity, and technical details. If pi fails, report its exact output and exit status; never retry with another model.

## Fully unattended installation

Run installation outside `$HOME` so npm does not prepend `$HOME/node_modules/.bin`. This machine has a `node@21.6.2` executable there that shadows the active Node 22 binary inside `npx` commands.

```bash
cd /tmp && npx --yes skills add \
  https://github.com/iliagerman/agents/tree/main/skills/pi-code-review \
  --global --agent claude-code --skill pi-code-review --yes
```
