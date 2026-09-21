---
name: local-code-review
description: Intensive code review of current changes. Scans for complexity, rule violations, scaling issues, security problems, and code clarity. Use when asked to review code, audit changes, or before pushing.
---

# Code Review

## When to Use This Skill

Use this skill when the user asks you to:

- review code or changes
- audit code quality
- check for security issues
- scan for scaling or performance problems
- prepare changes for a pull request
- this skill is also invoked automatically by the `push-code` skill before committing

## Core Principles

1. **Review only what changed.** Start from git to scope the review to current changes.
2. **Run tooling first.** Linters and type checkers catch mechanical issues faster than manual review.
3. **Severity matters.** Classify every finding as blocker, warning, or suggestion.
4. **Be specific.** Reference file paths and line numbers for every finding.
5. **Do not auto-fix.** Report findings and let the user decide. Exception: when `/simplify` is invoked for complexity issues.

## Step 1 — Scope the Changes

Start every review by identifying what changed.

```bash
# Identify changed files (staged)
git diff --cached --name-only

# Identify changed files (unstaged)
git diff --name-only

# Identify changed files vs main branch
git diff --name-only main...HEAD

# Get the full diff for review context
git diff --cached
git diff
```

Read every changed file in full. The review covers only these files — do not review unchanged code unless it is directly called by the changed code and relevant to the finding.

## Step 2 — Run Lint and Static Analysis

Detect the project type and run all available checks. Report findings but do not auto-fix.

### JavaScript / TypeScript

Check `package.json` for available scripts and run them:

- `npm run lint` or equivalent
- `npx tsc --noEmit`
- `npm run typecheck` if available
- Formatter check mode if available (`npm run format -- --check`)

### Python

Check for `justfile`, `Makefile`, `pyproject.toml`, or `setup.cfg` and run:

- `just lint` or `ruff check .`
- `mypy` if configured
- `just format --check` or `ruff format --check` if available

### Other projects

Look for a `justfile`, `Makefile`, or CI config and run equivalent lint and type-check commands.

Report every lint error and type error. Do not suppress or skip any.

## Step 3 — Complexity Scan

Scan every changed file for complexity issues:

- Functions exceeding 80 lines
- Files exceeding 1,000 lines
- Nesting depth greater than 4 levels inside a function body
- Functions with more than 8 parameters (excluding `self`, `cls`)
- Long if/elif chains with 5 or more branches
- Duplicated logic patterns across the diff

If complexity issues are found, run the `/simplify` skill on the affected files to refactor them. Then re-run lint and type checks to confirm the simplification did not break anything.

## Step 4 — Rules Validation

Check changed code against project coding rules.

### Backend (Python)

- No untyped dicts as return types, parameters, or Pydantic fields — use Pydantic models
- Every router, service, and DAO method must have return type annotations
- No `HTTPException` in service layer — use domain exceptions
- No direct database access outside DAO classes
- Use `fastapi.status.HTTP_*` constants — no raw integers for status codes
- No raw string comparisons — use `StrEnum` members
- No deprecated typing imports (`List`, `Dict`, `Optional`, `Union`) — use built-ins and `X | None`
- No `logging.error()` in except blocks — use `logging.exception()`
- Max 1 level of try-except nesting

### Frontend (React / TypeScript)

- No inline styles (`style={{}}`) — use Tailwind classes
- No `any` type — use `unknown` with type guards
- Props must be defined as named `interface`, not inline
- Every interactive element must have a `data-testid` attribute
- No CSS modules or styled-components — use Tailwind + shadcn
- Use shadcn components from `components/ui/` for standard UI elements
- No `<div onClick>` — use `<button>` for actions
- Icon-only buttons must have `aria-label`
- No `transition-all` — list specific transition properties
- No barrel file re-exports

### Frontend-Specific Skills

If React or Next.js files (`.tsx`, `.jsx`, or Next.js pages/app directory) are in the diff:

- Run `/vercel-react-best-practices` to check for performance anti-patterns: unnecessary re-renders, improper data fetching, bundle bloat, missing memoization, client vs server component misuse.
- Run `/web-design-guidelines` on changed UI files to audit accessibility, UX compliance, and interface best practices.

### General

- Every function must have type annotations on parameters and return values
- No deprecated typing imports
- Imports at module level only (exception: circular import breaks with comment)

## Step 5 — Scaling, Performance, and Architecture

### Performance Issues

- N+1 query patterns — queries inside loops that should be batched
- Missing pagination on list endpoints returning unbounded results
- Unbounded loops or data fetches without limits
- Missing database indexes on columns used in WHERE, JOIN, or ORDER BY
- Large objects copied unnecessarily — pass by reference or use slices
- Synchronous blocking calls in async code paths
- Missing `async`/`await` where I/O is involved

### Bottleneck Identification

- Synchronous blocking inside async functions (e.g., `time.sleep` instead of `asyncio.sleep`)
- Single-threaded hot paths that could benefit from concurrency
- Missing caching for repeated expensive operations (DB queries, API calls, computations)
- Unbounded queue or buffer growth without backpressure
- Heavy computation on the request path that should be offloaded to a background task

### Anti-Pattern Detection

- **Singleton misuse**: global mutable state, hidden coupling between modules, singletons that make testing impossible. Look for module-level instances that hold state.
- **God objects / God classes**: classes with too many responsibilities, too many methods, or too many instance variables. A class doing more than one job.
- **Service locator**: hiding dependencies behind a registry instead of injecting them explicitly. Makes testing and reasoning about dependencies harder.
- **Tight coupling**: UI components importing database models directly, services depending on router-level types, or any layer reaching across boundaries.
- **Anemic domain models**: data classes with no behavior where the logic is scattered across unrelated services or utilities instead of living with the data.
- **Circular dependencies**: module A imports from B, B imports from A. Check import graphs in changed files.
- **Premature optimization**: complex caching, custom data structures, or micro-optimizations that hurt readability without evidence of a performance problem.
- **Missing dependency injection**: services or DAOs instantiated with hardcoded constructors instead of being injected, making testing and swapping implementations difficult.

## Step 6 — Security Scan

Check every changed file for:

- **Hardcoded secrets**: API keys, tokens, passwords, connection strings in source code. Check for patterns like `key = "sk-..."`, `password = "..."`, `token = "..."`.
- **SQL injection**: raw string interpolation in SQL queries. Must use parameterized queries or ORM methods.
- **Command injection**: unsanitized user input passed to `subprocess`, `os.system`, `exec`, or shell commands.
- **XSS vectors**: unescaped user input rendered in HTML or JSX. Check for `dangerouslySetInnerHTML`, template literal injection, or missing sanitization.
- **Missing auth checks**: new endpoints without authentication or authorization decorators/middleware.
- **Sensitive data in logs**: logging passwords, tokens, API keys, personal data, or credentials. Check log statements for sensitive field names.
- **CORS misconfiguration**: overly permissive CORS settings (`allow_origins=["*"]` in production).
- **Insecure deserialization**: `pickle.loads`, `yaml.load` without `SafeLoader`, or `eval` on untrusted input.
- **Path traversal**: file operations using unsanitized user input for file paths.
- **Missing input validation**: endpoints accepting user input without size limits, type checks, or sanitization.

## Step 7 — Code Clarity

Review changed code for readability:

- Unclear or misleading variable and function names
- Dead code or unreachable branches
- Missing error handling at system boundaries (external APIs, file I/O, network calls)
- Commented-out code blocks that should be removed
- Magic numbers or strings that should be named constants
- Inconsistent naming conventions within the diff (mixing camelCase and snake_case in the same language)
- Overly clever one-liners that sacrifice readability
- Missing or misleading function/method documentation for non-obvious logic

## Output Format

Present findings as a structured report:

```
## Code Review Report

### Blockers (must fix before merge)
- [SECURITY] `src/api/auth.py:45` — API key hardcoded in source
- [COMPLEXITY] `src/services/agent.py:120` — function `process_all` is 140 lines, exceeds 80-line limit

### Warnings (should fix)
- [PATTERN] `src/services/user.py:30` — singleton pattern with mutable state, consider dependency injection
- [PERFORMANCE] `src/dao/connector.py:88` — N+1 query inside loop, batch with `IN` clause

### Suggestions (consider)
- [CLARITY] `src/utils/helpers.py:15` — variable `x` could be renamed to `retry_count`
- [STYLE] `client/src/components/Form.tsx:42` — missing `data-testid` on submit button
```

Use the exact severity labels: `Blockers`, `Warnings`, `Suggestions`.

Include the category tag in brackets: `[SECURITY]`, `[COMPLEXITY]`, `[PATTERN]`, `[PERFORMANCE]`, `[LINT]`, `[TYPE]`, `[RULES]`, `[CLARITY]`, `[STYLE]`, `[SCALING]`, `[A11Y]`.

If the review finds no issues, report: "No issues found. Code is clean."

## Practical Checklist

1. Scope changes via git diff
2. Run lint and type checks — report all errors
3. Scan for complexity — invoke `/simplify` if issues found
4. Validate against project coding rules
5. If frontend changes: run `/vercel-react-best-practices` and `/web-design-guidelines`
6. Check for scaling, performance, and architectural anti-patterns
7. Run security scan
8. Review code clarity
9. Present structured report with severity levels
