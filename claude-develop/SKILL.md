---
name: claude-develop
description: Use for Claude Code development, `/claude-develop`, Fable 5.1 implementation planning, Haiku coding, or detailed implementation plans where Fable 5.1 must inspect, plan, review, validate, and deliver while Haiku edits and tests.
compatibility: Requires authenticated Claude Code with access to Fable 5.1 and Haiku.
---

# Claude Develop

## 1. Role/model contract

The active parent must be Fable 5.1. If it is not Fable 5.1, or its identity cannot be confirmed, stop and ask the user to switch with `/model fable`. Never spawn Fable 5.1 as a hidden planner. Never let Haiku plan.

## 2. Ownership

- **Fable 5.1:** inspect, plan, review, independently validate, and deliver.
- **Haiku:** edit, run approved checks, and summarize.
- Haiku output is evidence only. Haiku must not perform Git operations or edit `.git`.

## 3. Implementation-grade planning standard

Before writing a brief, Fable 5.1 reads applicable repository instructions and real code. Because the child uses safe mode, Fable 5.1 copies every applicable repository instruction into the brief. The brief must name exact paths; copy verified symbols and signatures exactly; order edits; explain data/control flow, edge cases, and errors; state exclusions; list exact approved checks; and include concise code or pseudocode anchored to inspected repository APIs.

Fable 5.1 rejects a tool targeting `.git` and rejects a proposed check containing Git, `.git`, nested `pi` or `claude`, destructive shell actions, or unrelated commands. The approved checks contain only validation needed for the approved change.

Use this template:

```text
Goal
Acceptance criteria
Repository instructions
- every applicable instruction copied verbatim
Repository evidence
- exact file paths read
- existing symbols/signatures copied exactly
Files and ordered edits
1. path + symbol
   Current behavior
   Required change
   Data/control flow
   Edge cases and errors
   Code example or pseudocode anchored to the verified API
Tests
- exact test files/cases
- exact commands and working directory
Constraints and explicit exclusions
Definition of done
Coder restrictions
Return format
```

Illustrative shape only; replace it with inspected project symbols and APIs. Preserve the repository's actual error policy:

```ts
// Existing verified signature:
export function normalizeUsername(value: string): string

// Target body shape; preserve the repository's existing error policy:
export function normalizeUsername(value: string): string {
  return value.trim().toLocaleLowerCase("en-US");
}
```

## 4. Weak-coder readiness gate

Do not invoke Haiku until the brief has no vague steps, invented APIs, unresolved choices, placeholders, or commands that cannot run from its stated directory. “Update the service” is not a step. Stop and inspect more code when this gate fails.

## 5. Canonical Haiku invocation

From the target repository root, set `IMPLEMENTATION_BRIEF` to the approved ready brief. Build `HAIKU_TOOLS` from exact absolute in-scope file paths and exact approved check commands. For example:

```bash
HAIKU_TOOLS=(
  "Read"
  "Glob"
  "Grep"
  "Edit(/absolute/path/src/users.py)"
  "Edit(/absolute/path/tests/test_users.py)"
  "Bash(python3 -m unittest tests/test_users.py)"
)
```

Then run:

```bash
printf '%s\n' "$IMPLEMENTATION_BRIEF" | claude -p \
  --no-session-persistence \
  --safe-mode \
  --model haiku \
  --permission-mode dontAsk \
  --allowedTools "${HAIKU_TOOLS[@]}" \
  --disallowedTools "Bash(git *)" "Edit(**/.git/**)"
```

Claude Code's `Edit(path)` permission covers all file-editing tools, including new files; do not emit `Write(path)` permission rules. Safe mode disables skills, hooks, plugins, MCP, agents, and project customization while preserving authentication, model, tools, and permissions. Do not add `--disable-slash-commands` or broad `Read`/`Edit`/`Write`/`Bash` allowlists. Do not use `--bare`; the child needs authenticated setup.

Haiku can modify only the exact paths listed by `Edit(path)` entries in `HAIKU_TOOLS` and run only exact Fable 5.1-approved checks. It has no general shell. The brief must forbid every Git operation and every `.git` edit, including commit, push, branch/worktree changes, merge, rebase, reset, restore, clean, and checkout/switch.

## 6. Review, independent validation, one repair, optional delivery

Fable 5.1 reads Haiku output, every changed file, and the full diff. Fable 5.1 independently reruns the relevant tests, lint, typecheck, build, or other checks named in the brief. Haiku-reported checks do not replace this validation.

If Haiku caused a failure, give it one focused repair brief with the exact failure and relevant diff. Then repeat file/diff review and independent validation. Fable 5.1 remains delivery owner. Only when explicitly requested and validation passes may Fable 5.1 commit and push.

## 7. Detailed brief template

The brief uses the template in section 3 verbatim as headings. Under **Coder restrictions**, state that Haiku may edit only the exact listed paths and run only exact listed checks; it must not plan, make Git calls, edit `.git`, commit, push, create or switch branches, create worktrees, merge, rebase, reset, restore, clean, or deliver. Under **Return format**, require changed files, implementation summary, checks run with results, and unresolved failures.

## 8. Failure handling and completion report

- If Claude Code, authentication, Fable 5.1, or Haiku is unavailable, stop and report the exact failure. Do not substitute a model or hidden planner.
- If the required exact tool entry cannot be constructed, do not invoke Haiku; revise the inspected scope or brief.
- Preserve partial and pre-existing changes; inspect them before deciding whether the one repair brief applies.
- Report: parent/child models, files changed, Haiku checks, Fable 5.1 independent checks, full-diff review result, repair status, and commit/push result only if requested and completed.
