---
name: git-visualizer
description: Renders git changes (working tree, staged, a specific commit, a range, or a branch-vs-base diff) as a dark-themed HTML review page so a human can actually scan and review the diff instead of squinting at terminal output. Use this whenever the user asks to "visualize my git changes", "show me the diff", "review my changes before committing / pushing", "render what I'm about to commit", "visualize this commit / branch / PR", or wants a reviewable BEFORE/AFTER view of code changes. Especially good when the diff is large and the user needs a summary of which files changed, a per-file +/- bar, and per-file collapsible diffs with line numbers, all in one page. The page opens automatically in the default browser via `file://` so it works on macOS, Linux, and Windows.
compatibility: Requires Python 3.8+ and `git` on PATH. Uses only the Python stdlib — no pip installs.
---

# Git Visualizer

Use this skill to turn `git diff` output into a single HTML page that's easy for a human to scan and review. The default mode reviews uncommitted working-tree changes, but it also handles staged-only, single commits, arbitrary ranges, and "my branch vs `main`".

Unlike the plan-visualizer, you do NOT need to extract structured data yourself — `git` already produces structured output, and the bundled script parses it. Your job is almost entirely to pick the right command-line invocation for what the user wants to review, then run the script.

## When to use

Trigger this any time the user wants a visual, reviewable diff. Common phrasings:

- "visualize my git changes"
- "show me what I'm about to commit"
- "render the diff / render my changes"
- "I want to review my branch before pushing"
- "visualize this commit / PR / range"
- "make the diff easier to skim"

Also offer it proactively:

- After running any tool that produced a large set of changes — e.g. "I just rewrote 15 files, should I render the diff so you can review?"
- Before `git commit` / `git push` / creating a PR — "want me to render the staged diff first?"

Do **not** use this skill for viewing commit graphs, branch topology, or history navigation. This is a *diff* visualizer, not a git GUI.

## Decide what to visualize

The user's request usually maps to exactly one of these modes:

| User says                                      | Flag to pass                                     |
|------------------------------------------------|--------------------------------------------------|
| "my changes", "what I've been working on"      | *(no flag — default is working tree vs HEAD)*    |
| "what I'm about to commit", "staged changes"   | `--staged`                                       |
| "this commit", "the last commit"               | `--commit HEAD` (or `--commit <sha>`)            |
| "my branch vs main", "what this PR changes"    | `--base main` (or whichever base)                |
| "the changes between A and B"                  | `--range A..B` (or `A...B` for merge-base)       |

When in doubt, ask the user once rather than guessing. The answer is always one of those five modes.

## Annotations — agent-authored explanations on the report

When the user asks for "explanations next to each change", "comments on why this changed", "annotated diff", "review with reasoning", or similar, attach explanations to each file and hunk. **The explanations live only in the rendered HTML report — never write them into the source code as comments.**

### Workflow (do this in order)

1. **Read the diff first.** Run the same `git diff` the visualizer will run (e.g. `git diff HEAD` for working tree, `git show HEAD` for last commit, `git diff main...HEAD` for branch-vs-base) and read every hunk in order. Do not guess — explanations must reflect what the diff actually shows.
2. **Write `annotations.json`** with one entry per changed file. For each file, provide a short `summary` (why this file changed overall) and a positional `hunks` list — one entry per hunk in the order they appear in the diff. Use empty string `""` to skip a hunk you don't want to annotate.
3. **Invoke the visualizer with `--annotations <path>`**, combined with whichever diff-mode flag you'd normally use:

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --annotations annotations.json
python3 "<skill-dir>/scripts/visualize_changes.py" --annotations annotations.json --base main
python3 "<skill-dir>/scripts/visualize_changes.py" --annotations annotations.json --commit HEAD
```

### JSON schema

```json
{
  "files": {
    "<path/in/repo>": {
      "summary": "Why this file changed (purpose, reason).",
      "hunks": [
        "Why the first hunk changed.",
        "",
        {"header": "@@ -42,6 +42,22 @@ optional self-check", "explanation": "Why the third hunk changed."}
      ]
    }
  }
}
```

- `files` is keyed by the file's path as it appears in the diff (post-rename path for renames).
- `summary` is optional — omit it if you only want hunk-level notes.
- `hunks` is positional. Entry `i` annotates the i-th hunk shown in that file's diff. Out-of-range entries are silently dropped; empty strings and `null` skip a hunk.
- Each hunk entry is either a plain string (the explanation) or an object `{"header": "...", "explanation": "..."}`. The optional `header` is a self-check: if it's present and doesn't match the actual hunk's `@@` line, the script logs a warning but still applies the explanation by index.

### Worked example

User says: *"show me my staged changes with an explanation of each change"*. Suppose `git diff --cached` shows two files:

```
diff --git a/src/auth.py b/src/auth.py
@@ -10,4 +10,8 @@ def login(...):
@@ -45,2 +49,3 @@ def logout(...):
diff --git a/src/users.py b/src/users.py
@@ -1,1 +1,2 @@
```

Write `annotations.json`:

```json
{
  "files": {
    "src/auth.py": {
      "summary": "Switched session-based auth to short-lived JWTs to satisfy the new compliance requirement on token storage.",
      "hunks": [
        "Replaced the session-cookie issuance with `create_jwt(user_id, ttl=15m)` so tokens never persist server-side.",
        "Added an explicit `revoke_jwt()` call on logout — sessions used to be invalidated implicitly via cookie expiry."
      ]
    },
    "src/users.py": {
      "summary": "One-line import update — needed because `auth.py` now exports `create_jwt` instead of `start_session`.",
      "hunks": ["Renamed the import."]
    }
  }
}
```

Then run:

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --staged --annotations annotations.json
```

The rendered HTML shows a "Why this file changed" callout under each file's header and a "Why" callout above each annotated hunk's diff table. The source files are untouched.

### Combining with `--comments`

`--annotations` (agent-authored, baked into the page) and `--comments` (human reviewer notes, saved to `localStorage` and exportable) are independent and stack. Pass both to give the reviewer your reasoning AND a place to leave their reply.

## Comments — per-file review notes

Pass `--comments` to enable a collapsible comment textarea on every changed file and on the commits section. Comments persist in `localStorage`, survive page reloads, and can be exported as Markdown via the floating `📋 Export comments` button.

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --comments
python3 "<skill-dir>/scripts/visualize_changes.py" --comments --base main
python3 "<skill-dir>/scripts/visualize_changes.py" --comments --commit HEAD
```

The export produces a Markdown document with `## <file path>` headings so it's clear which comment belongs to which file. For the full behavioral spec (collapse-by-default, autosave debounce, export format, `data-section-label` semantics), read:

```
read: ../common/comments-widget.md
```

## Running the script

The bundled script lives at `scripts/visualize_changes.py` inside this skill directory. Run it from the repo root (or pass `--repo <path>`):

```bash
python3 "<skill-dir>/scripts/visualize_changes.py"               # working tree vs HEAD
python3 "<skill-dir>/scripts/visualize_changes.py" --staged
python3 "<skill-dir>/scripts/visualize_changes.py" --base main
python3 "<skill-dir>/scripts/visualize_changes.py" --commit HEAD
python3 "<skill-dir>/scripts/visualize_changes.py" --range HEAD~3..HEAD
```

Other useful flags:

- `--repo <path>` — run against a repo other than the current working directory.
- `-U <N>` / `--context <N>` — unified-diff context lines (default 3).
- `-o <path>` / `--output <path>` — explicit output HTML path.
- `--no-open` — write the HTML but do not open a browser. Use in headless / CI.
- `--comments` — enable per-file comment widgets with export.
- `--annotations <path>` — attach agent-authored "Why this changed" explanations to each file and hunk in the report (see *Annotations* above for the JSON schema).

The script prints the final `file://...` URL to stdout. Always surface that URL back to the user so they have a persistent link they can re-open or share.

### Finding the skill directory

Typical installation paths, in order of preference:

```bash
# Project-local (when the skill is checked into the repo)
SKILL_DIR="$(git rev-parse --show-toplevel)/skills/git-visualizer"

# User-global (when the user has installed it to their personal skills dir)
SKILL_DIR="$HOME/.claude/skills/git-visualizer"
```

Pick whichever exists.

## What the output looks like

A single dark-themed HTML page containing:

1. **Header** — title (e.g. `Branch `feature/x` vs `main``), a profile pill (`WORKING TREE` / `STAGED` / `COMMIT` / `RANGE` / `BRANCH`), a summary line (`N FILES · +X/−Y LINES`), and the generated date.
2. **Legend** — color key for status badges (Added / Modified / Deleted / Renamed / Copied).
3. **Commits section** — only shown for ranges, single commits, or branch-vs-base; lists commit SHA, date, author, and subject.
4. **Files changed panel** — one row per file with a status badge, the path, a proportional +/- bar (scaled across the review), and `+X / −Y` counts. Each row is an anchor link that jumps to the diff below.
5. **Per-file diffs** — collapsible `<details>` sections (open by default) with a unified diff rendered as a table with `old_lineno` / `new_lineno` gutters and green/red row tinting.

The page is self-contained (no external CSS, JS, fonts, or network requests) so it survives being saved, emailed, or opened on a plane.

## Concrete examples

### User: "render my working tree changes so I can review them before committing"

```bash
python3 "$(git rev-parse --show-toplevel)/skills/git-visualizer/scripts/visualize_changes.py"
```

Respond with the `file://...` URL and, if useful, a one-line summary of what the page shows ("N files changed, mostly in `app/services/` — top-level diff scanner suggests you want to double-check the one deletion.").

### User: "visualize the last commit"

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --commit HEAD
```

### User: "I want to review my branch against main before opening a PR"

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --base main
```

### User: "show the diff for commit abc1234"

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --commit abc1234
```

### User: "show me the changes introduced since I branched from origin/develop"

```bash
python3 "<skill-dir>/scripts/visualize_changes.py" --base origin/develop
```

## Things to avoid

- **Don't hand-roll HTML.** All styling and layout live in the script template so output stays consistent across invocations. If the visual needs a change, edit the `TEMPLATE` constant, not the caller.
- **Don't use `open <path>` or `xdg-open` or `start`.** The script already opens the file via Python's cross-platform `webbrowser` module with a `file://` URL. Avoid OS-specific shell commands.
- **Don't run on a repo you don't know.** Always check `git status` / `git rev-parse --show-toplevel` first if there's any ambiguity about which repo you're in.
- **Don't regenerate a review file over and over with different names.** By default, output goes to the OS temp dir with a slug based on the review title; that's fine for normal use. If the user wants a persistent artifact (to attach to a PR, share with a reviewer), pass `-o <path>` to an explicit location they control.
- **Don't block on large diffs.** If the review includes hundreds of files or tens of thousands of lines, just run it — the HTML handles it. Do not pre-filter or sample.
- **Don't write annotations into the source files.** When the user asks for explanations alongside the diff, put them in `annotations.json` and pass `--annotations`. They render in the report only and never touch the code. Adding explanatory `# ...` / `// ...` comments to the actual files is a separate action that this skill never performs.
