---
name: debugging
description: Structured debugging guidelines for reproducing issues, adding focused temporary instrumentation, and cleaning up afterward. Use when diagnosing bugs, isolating regressions, tracing data flow, or investigating unexpected behavior.
---

# Debugging Guide

## When to Use This Skill

Use this skill when the user asks you to:

- debug a bug, regression, crash, or failing test
- investigate unexpected behavior or incorrect output
- trace request flow, state changes, or data transformations
- add temporary instrumentation to confirm or reject a hypothesis
- isolate the root cause before making a fix

## Core Principles

1. **Debug the root cause, not the symptom.**
2. **Instrument narrowly.** Add the smallest amount of temporary logging needed to test the current hypothesis.
3. **Keep logs readable.** Temporary logs must be useful to both the agent and the user without excess noise.
4. **Prefer file-based debug output over scattered console spam.**
5. **Clean up completely.** Remove temporary logging code and delete session log files when the debugging session is finished.

## Standard Debugging Workflow

1. Reproduce the issue and summarize the expected vs actual behavior.
2. Form a concrete hypothesis about where the failure is happening.
3. Add temporary instrumentation only around the code path relevant to that hypothesis.
4. Write debug output to a timestamped file in `tmp/debug/`.
5. Review the logs, refine the hypothesis, and repeat with tighter instrumentation if needed.
6. Implement the fix once the root cause is confirmed.
7. Remove temporary debug code, search for leftover debug markers, and delete the temporary log file(s).

## Temporary Debug Log Rules

### Log location

- Store debug logs in `tmp/debug/` at the repository root.
- Create the directory if it does not already exist.
- Keep one log file per debugging session unless there is a clear reason to split by subsystem.

### File naming

Use timestamped filenames so the newest session is obvious at a glance.

Recommended format:

- `debug-YYYYMMDD-HHMMSS.log`
- `debug-YYYYMMDD-HHMMSS-short-topic.log`

Examples:

- `debug-20260319-143055.log`
- `debug-20260319-143055-auth-callback.log`

### Required log line prefix

Every temporary debug line must start with the same clear prefix so it is easy to search for and remove later.

Use this prefix:

- `[DEBUG-TEMP]`

Recommended full line format:

```text
[DEBUG-TEMP][2026-03-19T14:30:55.123Z][auth-callback] received state=abc123 valid=true
```

This prefix should also be used for any temporary console output if console logging is temporarily necessary.

### Log content guidelines

Only log information that helps evaluate the current hypothesis. Good candidates include:

- function entry and exit for the suspicious code path
- branch decisions and why they were taken
- important identifiers such as request IDs, tenant IDs, record IDs, or job IDs
- key input and output values
- counts, lengths, timestamps, durations, and state transitions
- caught errors and error metadata

Avoid or minimize:

- unrelated framework noise
- repeated logs inside hot loops unless counting or sampling is necessary
- full object dumps when a few fields are enough
- secrets, API keys, tokens, passwords, or sensitive personal data

If sensitive values are relevant, redact them.

## Instrumentation Guidelines

- Prefer a small temporary helper or wrapper instead of many ad hoc print statements.
- Make the instrumentation easy to delete in one pass.
- If the codebase already has logging utilities, route temporary debugging through them only if you can still guarantee a dedicated file and the `[DEBUG-TEMP]` prefix.
- If the issue is timing-related, include precise timestamps and elapsed durations.
- If the issue is state-related, log before and after snapshots of the specific fields involved.
- If the issue is data-related, log the narrowest useful subset of fields.

## Cleanup Requirements

When the debugging session is over:

1. Remove all temporary log statements, helpers, flags, and instrumentation added only for debugging.
2. Search the repo for `[DEBUG-TEMP]` and delete any remaining temporary debug code.
3. Delete the session log file(s) from `tmp/debug/` unless the user explicitly asks to keep them.
4. If a log file must be kept temporarily for handoff, mention its exact path and why it still exists.

A debugging task is not complete if temporary debug code remains in the codebase.

## Practical Checklist

Before debugging:

- identify the failing behavior
- state the current hypothesis
- choose the smallest instrumentation point

During debugging:

- log only what helps confirm or reject the hypothesis
- keep all temporary log lines prefixed with `[DEBUG-TEMP]`
- write to a timestamped file in `tmp/debug/`

After debugging:

- implement the fix
- remove temporary instrumentation
- delete temporary log files
- verify there are no remaining `[DEBUG-TEMP]` markers

## Example Session Notes

A good temporary debug session usually answers questions like:

- Did the function run?
- Which branch was taken?
- Which identifiers and inputs were present?
- What value changed unexpectedly?
- Where did expected flow diverge from actual flow?

If a log line does not help answer one of those questions, it probably should not be there.
