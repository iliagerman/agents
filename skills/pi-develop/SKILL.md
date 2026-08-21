---
name: pi-develop
description: Use for Pi development, `/skill:pi-develop`, GPT-5.6 Sol implementation planning, GPT-5.6 Terra coding, or detailed implementation plans where Sol must inspect, plan, review, validate, and deliver while Terra edits and tests.
compatibility: Requires authenticated Pi access to `openai-codex/gpt-5.6-sol` and `openai-codex/gpt-5.6-terra`.
---

# Pi Develop

## 1. Preflight and role/model contract

Check `$PI_MODEL`. Accept only `gpt-5.6-sol` or `openai-codex/gpt-5.6-sol`. Otherwise stop and tell the user to switch to `openai-codex/gpt-5.6-sol`. Never spawn Sol as a hidden planner. Never let Terra plan.

## 2. Ownership

- **Sol:** inspect, plan, review, independently validate, and deliver.
- **Terra:** edit, run approved checks, and summarize.
- Terra output is evidence only. Terra must not perform Git operations or edit `.git`.

## 3. Implementation-grade planning standard

Before writing a brief, Sol reads applicable repository instructions and real code. The brief must name exact paths; copy verified symbols and signatures exactly; order edits; explain data/control flow, edge cases, and errors; state exclusions; list exact approved checks; and include concise code or pseudocode anchored to inspected repository APIs.

Do not approve test commands that invoke Git, Pi, Claude, destructive filesystem operations, or `.git` paths. The check list must contain only validation needed for the approved change.

Use this template:

```text
Goal
Acceptance criteria
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
- exact commands and working directories
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

Do not invoke Terra until the brief has no vague steps, invented APIs, unresolved choices, placeholders, commands that cannot run from its stated directory, or a malformed or empty approved-file JSON list. “Update the service” is not a step. Stop and inspect more code when this gate fails.

## 5. Canonical Terra invocation

Resolve `extensions/deny-git.ts` relative to this `SKILL.md`, assign the resulting path to `TERRA_GUARD`, then, from the target repository root, set `IMPLEMENTATION_BRIEF` to the approved ready brief. Export Sol's exact approved checks and exact approved files as JSON:

```bash
export PI_DEVELOP_CHECKS_JSON='["python3 -m unittest tests/test_users.py"]'
export PI_DEVELOP_FILES_JSON='["src/users.py","tests/test_users.py"]'
```

Then run:

```bash
printf '%s\n' "$IMPLEMENTATION_BRIEF" | pi -p \
  --no-session \
  --no-extensions \
  -e "$TERRA_GUARD" \
  --no-skills \
  --no-prompt-templates \
  --offline \
  --approve \
  --model openai-codex/gpt-5.6-terra \
  --tools read,edit,write,grep,find,ls,run_check
```

`--no-extensions` plus explicit `-e` loads only the guard. `--offline` disables startup network work, not the model request. Context files remain enabled. `--no-skills` prevents recursive skill invocation. The fixed model and explicit tools are required.

Terra has no Bash tool. It can only select an index from Sol-approved checks through `run_check`; it cannot author shell text. The guard rejects empty or malformed check lists and approved commands containing Git, Pi, Claude, destructive filesystem commands, or `.git` paths before Terra starts.

The guard also requires a non-empty `PI_DEVELOP_FILES_JSON` string array. It blocks `write` or `edit` calls for every path except the exact Sol-approved resolved paths and blocks `.git` paths.

## 6. Review, independent validation, one repair, optional delivery

Sol reads Terra output, every changed file, and the full diff. Sol independently reruns the relevant tests, lint, typecheck, build, or other checks named in the brief. Terra-reported checks do not replace this validation.

If Terra caused a failure, give it one focused repair brief with the exact failure and relevant diff. Then repeat file/diff review and independent validation. Sol remains delivery owner. Only when explicitly requested and validation passes may Sol commit and push.

## 7. Detailed brief template

The brief uses the template in section 3 verbatim as headings. Under **Coder restrictions**, state that Terra may edit or write only the exact files exported in `PI_DEVELOP_FILES_JSON` and select only the listed approved checks; it must not plan, author shell commands, make Git calls, access or edit `.git`, commit, push, create or switch branches, create worktrees, merge, rebase, reset, restore, clean, or deliver. Under **Return format**, require changed files, implementation summary, checks selected with results, and unresolved failures.

## 8. Failure handling and completion report

- If `PI_DEVELOP_CHECKS_JSON` is malformed, empty, contains a prohibited command, or if `PI_DEVELOP_FILES_JSON` is malformed or empty, do not invoke Terra. Correct the approved list and rerun the child command.
- If Pi authentication, Sol, Terra, or the guard extension is unavailable, stop and report the exact failure. Do not substitute a model or hidden planner.
- Preserve partial and pre-existing changes; inspect them before deciding whether the one repair brief applies.
- Report: parent/child models, files changed, Terra checks, Sol independent checks, full-diff review result, repair status, and commit/push result only if requested and completed.
