---
name: pi-code-review
description: Launch an independent code review from Claude Code by running pi non-interactively with `openai-codex/gpt-5.6-sol`. Use whenever the user asks Claude to have pi, GPT-5.6 Sol, or a second AI reviewer review local code, working-tree changes, staged changes, a commit, or a branch before commit, push, or merge.
compatibility: Requires `pi` on PATH and authentication for `openai-codex/gpt-5.6-sol`.
---

# Pi Code Review

Delegate the review to pi. Run it from the repository root so pi can inspect the project rules, changed files, and surrounding code.

## Run the review

Use this command through Claude Code's Bash tool:

```bash
pi -p --no-session \
  --model openai-codex/gpt-5.6-sol \
  --tools read,bash \
  "Review the code changes in this repository. Determine the requested scope from my request; when no scope was specified, review staged and unstaged changes, or the current branch against its default base branch when the working tree is clean. Read applicable project instructions and inspect changed files in context. Do not modify files. Focus on correctness, security, regressions, performance, maintainability, and missing tests. Report only actionable findings, ordered by severity, with exact file paths and line numbers. For each finding explain the impact and the smallest sound fix. If no findings exist, say so explicitly."
```

`-p` makes pi return one review and exit. `--no-session` avoids creating review session history. `--tools read,bash` removes pi's direct file-editing tools while retaining git inspection; the prompt explicitly forbids modification because shell access itself cannot be made read-only.

If the user names a specific scope, append it to the quoted prompt. Examples:

- `Review commit abc123 only.`
- `Review the current branch against origin/main.`
- `Review staged changes only.`
- `Review src/auth.ts, focusing on authorization.`

Do not substitute Claude's own review for pi's output. Return pi's review to the user, preserving file paths, line numbers, severity, and technical details. If the command fails, report the exact error and stop; do not silently use another model.
