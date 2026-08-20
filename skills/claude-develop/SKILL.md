---
name: claude-develop
description: Delegate code implementation from pi to Claude Code while pi/GPT-5.6 Sol retains planning, review, and delivery control. Use for coding, refactoring, bug fixes, tests, scripts, APIs, or UI implementation when the user asks Pi, Sol, or GPT-5.6 Sol to plan and have Claude implement, mentions a Sol-to-Claude development workflow, requests Claude Haiku or Sonnet for coding, or invokes `claude-develop`. Claude writes and tests code; pi independently verifies it and alone may commit or push.
compatibility: Requires `claude` on PATH and an authenticated Claude Code setup with access to `sonnet` or `haiku`.
---

# Claude Develop

Use Claude Code as implementation worker. Keep planning, acceptance, review, and Git delivery with pi.

## Ownership

- **Pi/Sol:** inspect repository, read instructions, plan exact changes, choose model, review diff, rerun validation, commit, push, and report.
- **Claude:** edit code and tests, run focused checks, and summarize work.
- Never ask Claude to commit, push, create/switch branches, create worktrees, merge, rebase, reset, or clean files.
- Do not delegate planning. Give Claude a complete implementation brief produced by pi.

## Model selection

Respect an explicit user choice. Otherwise:

- Use `sonnet` by default.
- Use `haiku` only for narrow mechanical work: one-file edits, straightforward test additions, renames, formatting, or a fully specified small change with low debugging risk.
- Escalate to `sonnet` when Haiku's result is incomplete or incorrect. Do not keep retrying Haiku to save cost.

## Workflow

1. Read applicable project instructions and relevant files. Inspect `git status` before delegation.
2. Produce a concise implementation brief containing:
   - goal and acceptance criteria;
   - exact files or components in scope;
   - required behavior and constraints;
   - existing conventions to preserve;
   - tests/checks Claude must run;
   - explicit exclusions;
   - instruction to leave commits and pushes to pi.
3. Run Claude from the target repository root in non-interactive print mode:

```bash
printf '%s\n' "$IMPLEMENTATION_BRIEF" | claude -p \
  --no-session-persistence \
  --model sonnet \
  --permission-mode acceptEdits \
  --allowedTools "Read" "Edit" "Write" "Glob" "Grep" "Bash" \
  --disallowedTools \
    "Bash(git commit *)" \
    "Bash(git push *)" \
    "Bash(git merge *)" \
    "Bash(git rebase *)" \
    "Bash(git reset *)" \
    "Bash(git checkout *)" \
    "Bash(git switch *)" \
    "Bash(git clean *)" \
    "Bash(git worktree *)"
```

Replace `sonnet` with `haiku` only under the selection rule above. Set a long Bash-tool timeout appropriate for implementation work. Do not use `--bare`: Claude needs project instructions and the user's existing authenticated setup.

4. Read Claude's output. Inspect `git status`, the complete diff, and every changed file. Confirm scope and project rules.
5. Independently rerun the relevant tests, lint, type checks, or build from pi. Claude's reported success is evidence, not final verification.
6. If verification fails because of Claude's change, give Claude one focused repair brief containing the exact failure and relevant diff. Reinspect and rerun checks afterward. Pi may make a tiny correction directly when delegation would cost more than the fix.
7. Before a requested commit or push, follow the repository's review and delivery skills. Commit and push only after pi's checks pass. Claude never performs Git delivery.

## Brief template

```text
Implement the approved plan in this repository.

Goal:
[desired outcome]

Acceptance criteria:
- [observable result]

Files/components in scope:
- [path or component]

Implementation plan:
1. [specific change]

Constraints:
- Read and follow all repository instructions.
- Preserve existing conventions and unrelated behavior.
- Add or update tests for changed behavior.
- Run: [focused checks].
- Do not commit, push, create/switch branches, create worktrees, merge, rebase, reset, or clean files.

Return a concise summary of changed files and commands run, including failures.
```

## Failure handling

- Missing `claude` or authentication: stop and report the exact error. Do not silently implement the delegated task with another model.
- Claude exits unsuccessfully: preserve its output, inspect partial changes, and report or issue a focused repair brief based on the concrete failure.
- Pre-existing dirty files: preserve them. Scope Claude's work explicitly and never discard unrelated changes.

## Completion report

Report:

- Claude model used;
- files changed;
- checks Claude ran;
- checks pi independently ran;
- review outcome;
- commit hash and push target, only when requested and completed.
