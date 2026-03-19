---
name: push-code
description: Workflow for preparing code to commit and push safely. Use when the user asks to commit, push, ship, finalize, or submit code changes. Requires running relevant tests, linting, TypeScript checks, and other validation before committing.
---

# Push Code

## When to Use This Skill

Use this skill when the user asks you to:

- commit code
- push changes
- finalize a task for git
- prepare a branch for review
- submit code after making changes
- make a clean, meaningful commit

## Core Rules

1. **Do not commit broken code.** All relevant validation must pass before creating a commit.
2. **Fix issues before committing.** If tests, linting, type checks, builds, or other validations fail, fix them first.
3. **Run the full relevant validation set unless it was already run after the latest changes.**
4. **Use a meaningful commit message.** The message must describe the actual change, not a vague action like `updates` or `fix stuff`.
5. **Review what is being committed.** Check the diff and avoid committing unrelated changes.

## Required Validation Workflow

Before committing, identify and run the relevant checks for the project.

### JavaScript / TypeScript projects

Prefer package scripts when they exist. Check `package.json` and run the relevant scripts such as:

- `npm test`
- `npm run lint`
- `npm run typecheck`
- `npm run build`

If no dedicated typecheck script exists but the project uses TypeScript, run TypeScript directly:

- `npx tsc --noEmit`

If the repo uses another package manager, use the equivalent commands for that package manager.

### What “and everything” means

Run all validations that are relevant to the modified codebase, including when available:

- unit tests
- integration tests
- linting
- formatting checks
- static type checks
- build or compile checks
- framework-specific verification commands

Examples:

- monorepo affected checks for changed packages
- Next.js build validation
- test suites for the touched app or package
- backend and frontend validation if both were changed

## When You May Skip Re-Running a Check

A check may be skipped only if all of the following are true:

1. It already ran successfully in the current session.
2. It ran after the latest relevant code changes.
3. No files affecting that check changed since it ran.
4. You are confident the previous result is still valid.

If any of these conditions is not clearly true, run the check again.

When in doubt, rerun it.

## Failure Handling

If any validation fails:

1. Read the failure carefully.
2. Fix the underlying issue, not just the symptom.
3. Re-run the failed check.
4. Re-run any other checks that may be affected by the fix.
5. Only proceed to commit after everything relevant passes.

Do not create a commit while known validation failures remain.

## Commit Workflow

Before committing:

1. Review changed files.
2. Confirm the changes match the user’s request.
3. Exclude unrelated edits.
4. Ensure generated noise, temporary debug code, and local-only artifacts are not included.
5. Verify the working tree is ready.

Then:

1. Stage only the intended files.
2. Write a meaningful commit message.
3. Commit only after validations pass.

## Commit Message Guidelines

A meaningful commit message should:

- summarize the real change
- mention the feature, fix, or refactor performed
- be specific enough to understand later from git history alone

Good examples:

- `Add debugging skill with temporary log cleanup guidance`
- `Enforce pre-commit validation in push-code skill`
- `Fix tenant metering retry handling in billing service`

Bad examples:

- `update`
- `changes`
- `fix stuff`
- `wip`

## Push Workflow

If the user asks to push the code:

1. Make sure the commit is complete and correct.
2. Confirm the correct branch is being used.
3. Push only after successful validation and commit.
4. If there is any doubt about branch safety or unintended changes, review before pushing.

## Practical Checklist

Before commit:

- inspect git diff
- run all relevant validations
- fix every failing issue
- rerun checks as needed
- confirm no temporary or unrelated files are staged

Commit:

- stage the correct files
- write a specific commit message
- create the commit only after checks pass

Before push:

- verify the branch
- confirm the commit is the intended one
- push only after validation is green

## Default Decision Rule

If you are about to commit and are unsure whether enough validation has run, the answer is no: run the missing checks first.
