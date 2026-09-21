#!/usr/bin/env python3
"""Render git changes as a reviewable HTML page and open it in the browser.

Collects file statuses, per-file +/- counts, commit metadata, and the full
unified diff from `git`, parses the diff into per-file hunks with line numbers,
and produces a standalone dark-themed HTML page with a sticky left file panel
for navigation and a side-by-side diff view for modified files. Opens the page
via the `file://` protocol using Python's `webbrowser` module so it works on
macOS, Linux, and Windows.

Examples:
    # Uncommitted working-tree changes (staged + unstaged) vs HEAD
    visualize_changes.py

    # Only staged changes (what a plain `git commit` would record)
    visualize_changes.py --staged

    # Current branch vs an upstream base (uses the merge-base via `A...B`)
    visualize_changes.py --base main

    # A single commit's diff
    visualize_changes.py --commit HEAD
    visualize_changes.py --commit abc1234

    # An explicit range
    visualize_changes.py --range HEAD~3..HEAD
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


STATUS_META = {
    "A": ("ADDED", "badge-added", "A"),
    "M": ("MODIFIED", "badge-changed", "M"),
    "D": ("DELETED", "badge-removed", "D"),
    "R": ("RENAMED", "badge-renamed", "R"),
    "C": ("COPIED", "badge-copied", "C"),
    "T": ("TYPE CHANGE", "badge-changed", "T"),
    "U": ("UNMERGED", "badge-removed", "U"),
    "?": ("UNTRACKED", "badge-unchanged", "?"),
}

_COMMENTS_ENABLED = False


@dataclass
class DiffLine:
    kind: str  # "context" | "add" | "del" | "meta"
    old_lineno: int | None
    new_lineno: int | None
    text: str


@dataclass
class Hunk:
    header: str
    lines: list[DiffLine] = field(default_factory=list)
    explanation: str | None = None  # agent-authored "why this changed" note


@dataclass
class FileChange:
    status: str  # one-letter status (A/M/D/R/C/T/U)
    path: str
    old_path: str | None = None
    added: int = 0
    deleted: int = 0
    binary: bool = False
    hunks: list[Hunk] = field(default_factory=list)
    explanation: str | None = None  # agent-authored "why this file changed" note

    @property
    def anchor(self) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", self.path).strip("-").lower()
        return f"file-{slug}" or "file"


@dataclass
class Commit:
    sha: str
    short_sha: str
    author: str
    date: str
    subject: str


@dataclass
class Review:
    title: str
    subtitle: str
    profile: str  # short label for the top-right pill
    total_files: int
    total_added: int
    total_deleted: int
    files: list[FileChange]
    commits: list[Commit]


def git(*args: str, repo: str = ".") -> str:
    """Run a git subcommand and return its stdout (as text)."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"git {' '.join(args)} failed ({result.returncode}): {stderr}"
        )
    return result.stdout


def resolve_diff_args(cli: argparse.Namespace) -> tuple[str, str, list[str], list[str]]:
    """Translate CLI options into (title, subtitle, diff_args, log_args)."""
    if cli.staged:
        return (
            "Staged Changes",
            "Index vs HEAD — the set of changes a plain `git commit` would record.",
            ["--cached"],
            [],
        )
    if cli.commit:
        subject = git("log", "-1", "--format=%s", cli.commit, repo=cli.repo).strip()
        short = git("log", "-1", "--format=%h", cli.commit, repo=cli.repo).strip()
        return (
            f"Commit {short}: {subject}",
            f"Diff introduced by commit `{cli.commit}`.",
            [f"{cli.commit}^!"],  # `X^!` is shorthand for X^..X (single-commit diff)
            ["-1", cli.commit],
        )
    if cli.range:
        spec = cli.range
        return (
            f"Range {spec}",
            f"Diff for range `{spec}`.",
            [spec],
            [spec],
        )
    if cli.base:
        base = cli.base
        current = git("rev-parse", "--abbrev-ref", "HEAD", repo=cli.repo).strip()
        return (
            f"Branch `{current}` vs `{base}`",
            f"Changes on `{current}` relative to their common ancestor with `{base}`.",
            [f"{base}...HEAD"],
            [f"{base}..HEAD"],
        )

    return (
        "Working Tree Changes",
        "All uncommitted changes (staged and unstaged) relative to `HEAD`.",
        ["HEAD"],
        [],
    )


_NAME_STATUS_RE = re.compile(r"^([A-Z])(\d+)?\t(.+)$")


def parse_name_status(text: str) -> list[FileChange]:
    files: list[FileChange] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        code = parts[0]
        status_char = code[0]
        if status_char in ("R", "C") and len(parts) >= 3:
            files.append(
                FileChange(status=status_char, path=parts[2], old_path=parts[1])
            )
        else:
            files.append(FileChange(status=status_char, path=parts[1]))
    return files


def merge_numstat(files: list[FileChange], numstat: str) -> None:
    by_path: dict[str, FileChange] = {}
    for fc in files:
        by_path[fc.path] = fc
        if fc.old_path:
            by_path[fc.old_path] = fc
    for line in numstat.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s = parts[0], parts[1]
        for candidate in parts[2:]:
            if "=>" in candidate:
                left, right = candidate.split("=>", 1)
                candidate = (left + right).replace("{", "").replace("}", "")
                candidate = re.sub(r"\s+", "", candidate)
            fc = by_path.get(candidate) or by_path.get(candidate.strip())
            if fc:
                if added_s == "-" or deleted_s == "-":
                    fc.binary = True
                else:
                    fc.added = int(added_s)
                    fc.deleted = int(deleted_s)
                break


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def parse_diff_into_files(diff_text: str, files: list[FileChange]) -> None:
    by_path: dict[str, FileChange] = {f.path: f for f in files}
    for f in files:
        if f.old_path:
            by_path[f.old_path] = f

    current: FileChange | None = None
    current_hunk: Hunk | None = None
    old_lineno = 0
    new_lineno = 0

    def attach_hunk() -> None:
        nonlocal current_hunk
        if current is not None and current_hunk is not None:
            current.hunks.append(current_hunk)
            current_hunk = None

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            attach_hunk()
            match = re.match(r"^diff --git a/(.+?) b/(.+)$", raw)
            new_path = match.group(2) if match else None
            current = by_path.get(new_path) if new_path else None
            continue
        if current is None:
            continue
        if raw.startswith(("index ", "new file mode", "deleted file mode",
                           "old mode", "new mode", "similarity index",
                           "dissimilarity index", "rename from", "rename to",
                           "copy from", "copy to", "--- ", "+++ ", "Binary files")):
            if raw.startswith("Binary files"):
                current.binary = True
            continue
        m = _HUNK_RE.match(raw)
        if m:
            attach_hunk()
            old_lineno = int(m.group(1))
            new_lineno = int(m.group(3))
            current_hunk = Hunk(header=raw)
            continue
        if current_hunk is None:
            continue
        if raw.startswith("+"):
            current_hunk.lines.append(DiffLine("add", None, new_lineno, raw[1:]))
            new_lineno += 1
        elif raw.startswith("-"):
            current_hunk.lines.append(DiffLine("del", old_lineno, None, raw[1:]))
            old_lineno += 1
        elif raw.startswith(" "):
            current_hunk.lines.append(DiffLine("context", old_lineno, new_lineno, raw[1:]))
            old_lineno += 1
            new_lineno += 1
        elif raw.startswith("\\"):  # "\ No newline at end of file"
            current_hunk.lines.append(DiffLine("meta", None, None, raw))
    attach_hunk()


def load_annotations(path: str | None, files: list[FileChange]) -> None:
    """Attach agent-authored explanations from a JSON file to files and hunks.

    Schema:
        {
          "files": {
            "<path/in/repo>": {
              "summary": "<why this file changed>",
              "hunks": [
                "<explanation>",
                {"header": "@@ -a,b +c,d @@", "explanation": "<...>"}
              ]
            }
          }
        }

    `hunks` is a positional list. Each entry may be a string (the explanation
    itself) or an object with `explanation` plus an optional `header` for
    self-verification — when `header` is present and does not match the actual
    hunk's header, a warning is printed but the explanation is still applied
    by index. Empty strings and `null` entries skip the hunk.
    """
    if not path:
        return
    annotations_path = Path(path).expanduser().resolve()
    if not annotations_path.is_file():
        raise RuntimeError(f"Annotations file not found: {annotations_path}")
    try:
        data = json.loads(annotations_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in annotations: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Annotations JSON must be an object at the top level")

    file_anns = data.get("files") or {}
    if not isinstance(file_anns, dict):
        raise RuntimeError("'files' in annotations JSON must be an object keyed by path")

    by_path: dict[str, FileChange] = {f.path: f for f in files}
    for f in files:
        if f.old_path:
            by_path[f.old_path] = f

    for path_key, payload in file_anns.items():
        fc = by_path.get(path_key)
        if not fc:
            print(
                f"warning: annotations reference unknown file {path_key!r}",
                file=sys.stderr,
            )
            continue
        if not isinstance(payload, dict):
            continue
        summary = payload.get("summary") or payload.get("explanation")
        if isinstance(summary, str) and summary.strip():
            fc.explanation = summary

        hunks_payload = payload.get("hunks")
        if not isinstance(hunks_payload, list):
            continue
        for idx, item in enumerate(hunks_payload):
            if idx >= len(fc.hunks):
                break
            text: str | None = None
            expected_header: str | None = None
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                raw_text = item.get("explanation")
                if isinstance(raw_text, str):
                    text = raw_text
                raw_header = item.get("header")
                if isinstance(raw_header, str):
                    expected_header = raw_header
            if not text or not text.strip():
                continue
            if expected_header and expected_header.strip() != fc.hunks[idx].header.strip():
                print(
                    f"warning: hunk header mismatch in {path_key} index {idx}: "
                    f"expected {expected_header!r}, got {fc.hunks[idx].header!r}",
                    file=sys.stderr,
                )
            fc.hunks[idx].explanation = text


def collect_commits(log_args: list[str], repo: str) -> list[Commit]:
    if not log_args:
        return []
    fmt = "%H%x1f%h%x1f%an%x1f%ad%x1f%s%x1e"
    out = git("log", f"--format={fmt}", "--date=short", *log_args, repo=repo)
    commits: list[Commit] = []
    for entry in out.split("\x1e"):
        entry = entry.strip("\n").strip()
        if not entry:
            continue
        parts = entry.split("\x1f")
        if len(parts) < 5:
            continue
        sha, short, author, when, subject = parts[:5]
        commits.append(
            Commit(sha=sha, short_sha=short, author=author, date=when, subject=subject)
        )
    return commits


def build_review(cli: argparse.Namespace) -> Review:
    title, subtitle, diff_args, log_args = resolve_diff_args(cli)

    name_status = git("diff", "--name-status", "--find-renames", *diff_args, repo=cli.repo)
    numstat = git("diff", "--numstat", "--find-renames", *diff_args, repo=cli.repo)
    diff_text = git("diff", "--find-renames", f"-U{cli.context}", *diff_args, repo=cli.repo)

    files = parse_name_status(name_status)
    merge_numstat(files, numstat)
    parse_diff_into_files(diff_text, files)

    load_annotations(getattr(cli, "annotations", None), files)

    total_added = sum(f.added for f in files)
    total_deleted = sum(f.deleted for f in files)

    commits = collect_commits(log_args, cli.repo)

    profile = "WORKING TREE"
    if cli.staged:
        profile = "STAGED"
    elif cli.commit:
        profile = "COMMIT"
    elif cli.range:
        profile = "RANGE"
    elif cli.base:
        profile = "BRANCH"

    return Review(
        title=title,
        subtitle=subtitle,
        profile=profile,
        total_files=len(files),
        total_added=total_added,
        total_deleted=total_deleted,
        files=files,
        commits=commits,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    return html.escape(text)


def render_inline(text: str) -> str:
    """Escape text and allow `backtick` spans as inline monospace."""
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', escaped)


def render_annotation_body(text: str) -> str:
    """Escape annotation prose, preserve paragraphs and line breaks, render `code`."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    rendered: list[str] = []
    for para in paragraphs:
        if not para.strip():
            continue
        escaped = html.escape(para)
        with_code = re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', escaped)
        with_breaks = with_code.replace("\n", "<br>")
        rendered.append(f"<p>{with_breaks}</p>")
    return "".join(rendered)


def render_annotation(text: str, kind: str) -> str:
    """Render an agent-authored explanation block (file-level or hunk-level)."""
    label = "Why this file changed" if kind == "file" else "Why"
    return (
        f'<div class="annotation annotation-{kind}">'
        f'  <span class="annotation-icon" aria-hidden="true">💡</span>'
        f'  <div class="annotation-content">'
        f'    <span class="annotation-label">{label}</span>'
        f'    <div class="annotation-body">{render_annotation_body(text)}</div>'
        f'  </div>'
        f'</div>'
    )


def pair_lines(lines: list[DiffLine]) -> list[tuple[DiffLine | None, DiffLine | None]]:
    """Pair deletions with subsequent additions so they render side-by-side.

    Context lines render in both columns (same content), preserving the flow.
    A run of N deletions followed by M additions pairs up to min(N, M) rows;
    any extras land in single-sided rows. Pure-add files (all additions) yield
    (None, add) rows; pure-delete files yield (del, None) rows.
    """
    result: list[tuple[DiffLine | None, DiffLine | None]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.kind == "context":
            result.append((line, line))
            i += 1
            continue
        if line.kind == "meta":
            result.append((line, line))
            i += 1
            continue
        if line.kind == "del":
            dels: list[DiffLine] = []
            while i < n and lines[i].kind == "del":
                dels.append(lines[i])
                i += 1
            adds: list[DiffLine] = []
            while i < n and lines[i].kind == "add":
                adds.append(lines[i])
                i += 1
            for j in range(max(len(dels), len(adds))):
                left = dels[j] if j < len(dels) else None
                right = adds[j] if j < len(adds) else None
                result.append((left, right))
            continue
        # Run of additions with no preceding deletion (new content).
        if line.kind == "add":
            while i < n and lines[i].kind == "add":
                result.append((None, lines[i]))
                i += 1
            continue
        i += 1
    return result


def render_side_by_side_row(
    left: DiffLine | None, right: DiffLine | None
) -> str:
    def cell(line: DiffLine | None, side: str) -> tuple[str, str]:
        # Returns (gutter_html, code_html) for one side.
        if line is None:
            return (
                '<td class="gutter gutter-empty"></td>',
                '<td class="diff-code diff-empty"></td>',
            )
        if line.kind == "meta":
            return (
                '<td class="gutter gutter-empty"></td>',
                f'<td class="diff-code diff-meta">{_esc(line.text)}</td>',
            )
        lineno = (
            line.old_lineno if side == "old" else line.new_lineno
        )
        lineno_text = "" if lineno is None else str(lineno)
        prefix = {"add": "+", "del": "-", "context": " "}.get(line.kind, " ")
        cls = f"diff-code diff-{line.kind}"
        return (
            f'<td class="gutter gutter-{side}">{lineno_text}</td>',
            f'<td class="{cls}"><span class="prefix">{prefix}</span>{_esc(line.text)}</td>',
        )

    left_gutter, left_code = cell(left, "old")
    right_gutter, right_code = cell(right, "new")
    return f'<tr class="diff-row">{left_gutter}{left_code}{right_gutter}{right_code}</tr>'


def render_hunk_side_by_side(hunk: Hunk) -> str:
    rows = [render_side_by_side_row(left, right) for left, right in pair_lines(hunk.lines)]
    annotation_html = (
        render_annotation(hunk.explanation, kind="hunk") if hunk.explanation else ""
    )
    return (
        f'{annotation_html}'
        f'<div class="hunk-header"><code>{_esc(hunk.header)}</code></div>'
        '<table class="diff-table side-by-side">'
        '  <colgroup>'
        '    <col class="col-gutter"><col class="col-code">'
        '    <col class="col-gutter"><col class="col-code">'
        '  </colgroup>'
        f'  <tbody>{"".join(rows)}</tbody>'
        '</table>'
    )


def render_sidebar_item(fc: FileChange) -> str:
    label, badge_cls, letter = STATUS_META.get(fc.status, ("CHANGED", "badge-changed", "?"))
    stats = (
        '<span class="nav-stats binary">bin</span>'
        if fc.binary
        else (
            f'<span class="nav-stats">'
            f'<span class="add-count">+{fc.added}</span>'
            f'<span class="del-count">−{fc.deleted}</span>'
            f'</span>'
        )
    )
    # Split path into directory and basename so basename can stand out when
    # the row is narrow.
    parts = fc.path.rsplit("/", 1)
    if len(parts) == 2:
        dirname, basename = parts
        path_html = (
            f'<span class="nav-dir">{_esc(dirname)}/</span>'
            f'<span class="nav-base">{_esc(basename)}</span>'
        )
    else:
        path_html = f'<span class="nav-base">{_esc(fc.path)}</span>'

    return (
        f'<a class="nav-item" href="#{fc.anchor}" title="{_esc(fc.path)}">'
        f'  <span class="nav-badge {badge_cls}">{_esc(letter)}</span>'
        f'  <span class="nav-path">{path_html}</span>'
        f'  {stats}'
        f'</a>'
    )


def render_sidebar(review: Review) -> str:
    if not review.files:
        body = '<div class="empty-row">No changes.</div>'
    else:
        body = "".join(render_sidebar_item(f) for f in review.files)
    return (
        '<div class="sidebar-sticky">'
        f'  <div class="nav-head">'
        f'    <span class="nav-head-label">Files changed</span>'
        f'    <span class="nav-head-count">{review.total_files}</span>'
        f'  </div>'
        f'  <div class="nav-totals">'
        f'    <span class="add-count">+{review.total_added}</span>'
        f'    <span class="del-count">−{review.total_deleted}</span>'
        f'  </div>'
        f'  <nav class="nav-list">{body}</nav>'
        '</div>'
    )


def render_file_detail(fc: FileChange) -> str:
    label, badge_cls, _ = STATUS_META.get(fc.status, ("CHANGED", "badge-changed", "?"))
    header_path = _esc(fc.path)
    rename_html = ""
    if fc.old_path and fc.old_path != fc.path:
        rename_html = f'<span class="rename-from">{_esc(fc.old_path)} →</span> '

    if fc.binary:
        body = '<div class="binary-note">Binary file — diff not shown.</div>'
    elif not fc.hunks:
        body = '<div class="binary-note">No textual changes (possibly mode-only or pure rename).</div>'
    else:
        body = "".join(render_hunk_side_by_side(h) for h in fc.hunks)

    file_annotation_html = (
        render_annotation(fc.explanation, kind="file") if fc.explanation else ""
    )

    stats_html = (
        '<span class="stat-nums binary">binary</span>'
        if fc.binary
        else (
            f'<span class="stat-nums">'
            f'<span class="add-count">+{fc.added}</span>'
            f'<span class="del-count">−{fc.deleted}</span>'
            f'</span>'
        )
    )

    comment_widget = ""
    if _COMMENTS_ENABLED:
        sid = fc.anchor
        comment_widget = (
            f'<div class="comment-widget" data-section-id="{sid}">'
            f'<button type="button" class="comment-toggle" aria-expanded="false">💬 Comment</button>'
            f'<div class="comment-body" hidden>'
            f'<textarea class="comment-textarea" data-section-id="{sid}" '
            f'placeholder="Type your question or comment for this file…"></textarea>'
            f'<div class="comment-meta"><span class="comment-saved-indicator" aria-live="polite"></span></div>'
            f'</div>'
            f'</div>'
        )

    return (
        f'<details class="file-detail" id="{fc.anchor}"'
        f' data-section-id="{fc.anchor}" data-section-label="{_esc(fc.path)}" open>'
        f'  <summary class="file-summary-head">'
        f'    <span class="badge {badge_cls}">{_esc(label)}</span>'
        f'    <span class="file-path">{rename_html}<code>{header_path}</code></span>'
        f'    {stats_html}'
        f'  </summary>'
        f'  {file_annotation_html}'
        f'  <div class="file-body">{body}</div>'
        f'  {comment_widget}'
        f'</details>'
    )


def render_commits(commits: list[Commit]) -> str:
    if not commits:
        return ""
    rows = "".join(
        f'<tr>'
        f'  <td class="commit-sha"><code>{_esc(c.short_sha)}</code></td>'
        f'  <td class="commit-date">{_esc(c.date)}</td>'
        f'  <td class="commit-author">{_esc(c.author)}</td>'
        f'  <td class="commit-subject">{_esc(c.subject)}</td>'
        f'</tr>'
        for c in commits
    )
    commit_comment_widget = ""
    if _COMMENTS_ENABLED:
        commit_comment_widget = (
            '<div class="comment-widget" data-section-id="commits">'
            '<button type="button" class="comment-toggle" aria-expanded="false">💬 Comment</button>'
            '<div class="comment-body" hidden>'
            '<textarea class="comment-textarea" data-section-id="commits" '
            'placeholder="Type your question or comment for commits…"></textarea>'
            '<div class="comment-meta"><span class="comment-saved-indicator" aria-live="polite"></span></div>'
            '</div>'
            '</div>'
        )
    return (
        '<section class="section" data-section-id="commits" data-section-label="Commits">'
        '  <h2 class="section-title"><span class="marker sym-diamond">◇</span>Commits</h2>'
        f'  <table class="commits-table">{rows}</table>'
        f'  {commit_comment_widget}'
        '</section>'
    )


def render_html(review: Review, comments_enabled: bool = False) -> str:
    global _COMMENTS_ENABLED
    _COMMENTS_ENABLED = comments_enabled

    detail_blocks = "\n".join(render_file_detail(f) for f in review.files)
    if not review.files:
        detail_blocks = '<div class="empty-row">No changes to display.</div>'

    stats_line = (
        f"{review.total_files} FILE" + ("" if review.total_files == 1 else "S")
        + f" · +{review.total_added} / −{review.total_deleted} LINES"
    )

    report_id = slugify(review.title)

    annotation_css = """
  /* Annotation blocks — agent-authored explanations for files and hunks. */
  .annotation {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(245, 176, 65, 0.06);
    border-left: 3px solid var(--changed);
    font-family: var(--sans);
    font-size: 13px;
    line-height: 1.55;
    color: var(--text);
  }
  .annotation-icon {
    flex-shrink: 0;
    font-size: 14px;
    color: var(--changed);
    line-height: 1.4;
  }
  .annotation-content { flex: 1; min-width: 0; }
  .annotation-label {
    display: block;
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--changed);
    margin-bottom: 4px;
  }
  .annotation-body p { margin: 0 0 8px; }
  .annotation-body p:last-child { margin-bottom: 0; }
  .annotation-body code.inline {
    background: rgba(245, 176, 65, 0.12);
    border-color: rgba(245, 176, 65, 0.3);
    color: #f5d28a;
  }
  .annotation-file { border-bottom: 1px solid var(--border); }
  .annotation-hunk {
    border-top: 1px solid var(--border);
    padding: 10px 16px;
    font-size: 12.5px;
  }
  .annotation-hunk + .hunk-header { border-top: none; }
"""

    # Build comment-related blocks as plain Python strings so CSS/JS braces
    # don't need to be doubled when interpolated into TEMPLATE.format().
    comment_css = ""
    floating_button_html = ""
    comment_script = ""
    if _COMMENTS_ENABLED:
        comment_css = """
  /* Comment widget */
  .comment-widget {
    margin-top: 12px;
    border-top: 1px dashed var(--border);
    padding: 12px 16px 12px;
  }
  .comment-toggle {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11.5px;
    letter-spacing: 0.04em;
    cursor: pointer;
    font-family: var(--sans);
    transition: border-color 120ms, color 120ms, background 120ms;
  }
  .comment-toggle:hover { color: var(--text); border-color: var(--renamed); }
  .comment-toggle.has-comment { color: var(--renamed); border-color: var(--renamed); }
  .comment-body { margin-top: 10px; }
  .comment-textarea {
    width: 100%;
    min-height: 80px;
    box-sizing: border-box;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    padding: 10px 12px;
    color: var(--text);
    font-family: var(--sans);
    font-size: 13px;
    line-height: 1.5;
    resize: vertical;
  }
  .comment-textarea:focus { outline: none; border-color: var(--renamed); }
  .comment-meta {
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
    min-height: 16px;
  }
  .comment-saved-indicator {
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.04em;
  }
  #export-bar {
    position: fixed;
    bottom: 20px;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 100;
  }
  #export-btn {
    background: var(--renamed);
    color: #0a0d12;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    transition: transform 120ms, box-shadow 120ms;
  }
  #export-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(0,0,0,0.5); }
  #export-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
  .export-count {
    background: var(--panel);
    border: 1px solid var(--border-strong);
    color: var(--muted);
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 11.5px;
    letter-spacing: 0.04em;
  }
  .export-modal:not([hidden]) { display: flex; }
  .export-modal {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    align-items: center;
    justify-content: center;
    z-index: 200;
  }
  .export-modal-inner {
    width: min(720px, 90vw);
    max-height: 80vh;
    background: var(--panel);
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .export-modal-head { display: flex; justify-content: space-between; align-items: center; }
  .export-modal-title { font-size: 14px; font-weight: 600; color: var(--text); }
  .export-modal-close {
    background: transparent; color: var(--muted); border: none;
    font-size: 20px; cursor: pointer; line-height: 1;
  }
  .export-modal-close:hover { color: var(--text); }
  #export-modal-text {
    width: 100%; flex: 1; min-height: 280px; box-sizing: border-box;
    background: var(--bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 4px;
    padding: 12px; font-family: var(--mono); font-size: 12px;
    line-height: 1.55; resize: vertical;
  }
  .export-modal-actions {
    display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap;
  }
  .export-action-btn {
    background: var(--panel-alt); color: var(--text);
    border: 1px solid var(--border-strong); border-radius: 4px;
    padding: 6px 12px; font-size: 12.5px; cursor: pointer;
    transition: border-color 120ms, color 120ms;
  }
  .export-action-btn:hover { border-color: var(--renamed); color: var(--renamed); }
  .export-clear:hover { border-color: var(--removed); color: var(--removed); }"""

        floating_button_html = (
            '<div id="export-bar">'
            '<button type="button" id="export-btn">📋 Export comments</button>'
            '<span id="export-count" class="export-count">0 comments</span>'
            '</div>'
            '<div id="export-modal" class="export-modal" hidden>'
            '<div class="export-modal-inner">'
            '<div class="export-modal-head">'
            '<span class="export-modal-title">Comments &amp; questions</span>'
            '<button type="button" class="export-modal-close" id="export-modal-close">×</button>'
            '</div>'
            '<textarea id="export-modal-text" readonly></textarea>'
            '<div class="export-modal-actions">'
            '<button type="button" id="export-copy-btn" class="export-action-btn">📋 Copy to clipboard</button>'
            '<button type="button" id="export-download-btn" class="export-action-btn">💾 Download .md</button>'
            '<button type="button" id="export-clear-btn" class="export-action-btn export-clear">🗑 Clear all</button>'
            '</div>'
            '</div>'
            '</div>'
        )

        comment_script = """
  <script>
    (function() {
      var enabled = document.body.getAttribute('data-comments-enabled') === 'true';
      if (!enabled) return;
      var reportId = document.body.getAttribute('data-report-id') || 'review';
      var storageKey = 'gitviz:' + reportId;

      function loadComments() {
        try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); }
        catch (e) { return {}; }
      }
      function saveComments(map) {
        try { localStorage.setItem(storageKey, JSON.stringify(map)); }
        catch (e) {}
      }
      function updateExportCount() {
        var map = loadComments();
        var n = Object.keys(map).filter(function(k) { return (map[k] || '').trim().length > 0; }).length;
        var el = document.getElementById('export-count');
        var btn = document.getElementById('export-btn');
        if (el) el.textContent = n + (n === 1 ? ' comment' : ' comments');
        if (btn) btn.disabled = (n === 0);
      }

      var data = loadComments();
      var widgets = document.querySelectorAll('.comment-widget');
      widgets.forEach(function(w) {
        var sid = w.getAttribute('data-section-id');
        var btn = w.querySelector('.comment-toggle');
        var body = w.querySelector('.comment-body');
        var ta = w.querySelector('.comment-textarea');
        var indicator = w.querySelector('.comment-saved-indicator');

        if (data[sid]) {
          ta.value = data[sid];
          btn.classList.add('has-comment');
          btn.textContent = '💬 Comment (saved)';
        }
        body.hidden = true;
        btn.setAttribute('aria-expanded', 'false');

        btn.addEventListener('click', function(e) {
          e.preventDefault();
          var isHidden = body.hidden;
          if (isHidden) {
            body.hidden = false;
            btn.setAttribute('aria-expanded', 'true');
            ta.focus();
          } else {
            body.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
          }
        });

        var saveTimer = null;
        ta.addEventListener('input', function() {
          if (saveTimer) clearTimeout(saveTimer);
          if (indicator) indicator.textContent = 'saving…';
          saveTimer = setTimeout(function() {
            var map = loadComments();
            var v = ta.value.trim();
            if (v) {
              map[sid] = ta.value;
              btn.classList.add('has-comment');
              btn.textContent = '💬 Comment (saved)';
            } else {
              delete map[sid];
              btn.classList.remove('has-comment');
              btn.textContent = '💬 Comment';
            }
            saveComments(map);
            if (indicator) {
              indicator.textContent = 'saved';
              setTimeout(function() { if (indicator.textContent === 'saved') indicator.textContent = ''; }, 1200);
            }
            updateExportCount();
          }, 350);
        });
      });

      updateExportCount();

      var exportBtn = document.getElementById('export-btn');
      var modal = document.getElementById('export-modal');
      var modalText = document.getElementById('export-modal-text');
      var closeBtn = document.getElementById('export-modal-close');
      var copyBtn = document.getElementById('export-copy-btn');
      var dlBtn = document.getElementById('export-download-btn');
      var clearBtn = document.getElementById('export-clear-btn');

      function buildExport() {
        var map = loadComments();
        var lines = [];
        var title = document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : 'Review';
        var dateStr = new Date().toISOString().slice(0, 10);
        lines.push('# Comments — ' + title);
        lines.push('');
        lines.push('_Generated_: ' + dateStr);
        lines.push('_Report_: `' + reportId + '`');
        lines.push('');

        var seen = {};
        var sections = document.querySelectorAll('[data-section-id]');
        var any = false;
        sections.forEach(function(sec) {
          var sid = sec.getAttribute('data-section-id');
          if (!sid || seen[sid]) return;
          seen[sid] = true;
          var c = (map[sid] || '').trim();
          if (!c) return;

          var heading = sec.getAttribute('data-section-label') || '';
          if (!heading) {
            var hEl = sec.querySelector('.section-title, h1, h2, h3');
            if (hEl) heading = hEl.textContent.replace(/¶$/, '').trim();
          }
          if (!heading) heading = sid;

          any = true;
          lines.push('## ' + heading);
          lines.push('');
          lines.push(c);
          lines.push('');
        });

        if (!any) { lines.push('_(no comments yet)_'); }
        return lines.join('\\n');
      }

      if (exportBtn) {
        exportBtn.addEventListener('click', function() {
          modalText.value = buildExport();
          modal.hidden = false;
          modalText.focus();
          modalText.select();
        });
      }
      if (closeBtn) closeBtn.addEventListener('click', function() { modal.hidden = true; });
      if (modal) modal.addEventListener('click', function(e) { if (e.target === modal) modal.hidden = true; });

      if (copyBtn) {
        copyBtn.addEventListener('click', function() {
          var txt = modalText.value;
          if (navigator.clipboard) {
            navigator.clipboard.writeText(txt).then(function() {
              copyBtn.textContent = '✓ Copied';
              setTimeout(function() { copyBtn.textContent = '📋 Copy to clipboard'; }, 1400);
            });
          } else {
            modalText.select(); document.execCommand('copy');
            copyBtn.textContent = '✓ Copied';
            setTimeout(function() { copyBtn.textContent = '📋 Copy to clipboard'; }, 1400);
          }
        });
      }

      if (dlBtn) {
        dlBtn.addEventListener('click', function() {
          var blob = new Blob([modalText.value], { type: 'text/markdown' });
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = reportId + '-comments.md';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        });
      }

      if (clearBtn) {
        clearBtn.addEventListener('click', function() {
          if (!confirm('Clear all comments? This cannot be undone.')) return;
          localStorage.removeItem(storageKey);
          document.querySelectorAll('.comment-textarea').forEach(function(ta) { ta.value = ''; });
          document.querySelectorAll('.comment-toggle').forEach(function(b) {
            b.classList.remove('has-comment');
            b.textContent = '💬 Comment';
          });
          document.querySelectorAll('.comment-body').forEach(function(b) { b.hidden = true; });
          document.querySelectorAll('.comment-toggle').forEach(function(b) { b.setAttribute('aria-expanded', 'false'); });
          modal.hidden = true;
          updateExportCount();
        });
      }
    })();
  </script>"""

    return TEMPLATE.format(
        title=_esc(review.title),
        subtitle=render_inline(review.subtitle),
        profile=_esc(review.profile),
        stats_line=_esc(stats_line),
        generated=_esc(date.today().isoformat()),
        sidebar=render_sidebar(review),
        detail_blocks=detail_blocks,
        commits_section=render_commits(review.commits),
        comments_enabled_js="true" if _COMMENTS_ENABLED else "false",
        report_id=report_id,
        annotation_css=annotation_css,
        comment_css=comment_css,
        floating_button=floating_button_html,
        comment_script=comment_script,
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #0b0f14;
    --panel: #131922;
    --panel-alt: #182030;
    --panel-hover: #1d2637;
    --border: #222b39;
    --border-strong: #2f3a4c;
    --text: #e6ebf2;
    --muted: #8893a5;
    --dim: #5b6778;
    --added: #3fb950;
    --added-bg: rgba(63,185,80,0.14);
    --added-bg-soft: rgba(63,185,80,0.11);
    --added-bg-empty: rgba(63,185,80,0.04);
    --changed: #f5b041;
    --changed-bg: rgba(245,176,65,0.14);
    --removed: #f47272;
    --removed-bg: rgba(244,114,114,0.14);
    --removed-bg-soft: rgba(244,114,114,0.11);
    --removed-bg-empty: rgba(244,114,114,0.04);
    --renamed: #6ea8fe;
    --renamed-bg: rgba(110,168,254,0.14);
    --copied: #a371f7;
    --copied-bg: rgba(163,113,247,0.14);
    --unchanged: #8893a5;
    --unchanged-bg: rgba(136,147,165,0.14);
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --sidebar-w: 300px;
    --gap: 20px;
    --pad: 28px;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.5;
    margin: 0;
    padding: 0;
    scroll-behavior: smooth;
  }}
  .page {{ max-width: 1400px; margin: 0 auto; padding: var(--pad); }}

  /* Header */
  .top {{
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 24px; padding-bottom: 20px; border-bottom: 1px solid var(--border);
  }}
  .top-left h1 {{ margin: 0 0 8px; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }}
  .top-left .subtitle {{ color: var(--muted); font-size: 13px; max-width: 820px; }}
  .top-right {{
    text-align: right; display: flex; flex-direction: column; align-items: flex-end;
    gap: 6px; min-width: 220px;
  }}
  .profile-pill {{
    border: 1px solid var(--border-strong); background: var(--panel);
    color: var(--muted); padding: 4px 10px; border-radius: 999px;
    font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
  }}
  .stats-line {{ color: var(--muted); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; }}
  .gen-line   {{ color: var(--dim);   font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }}

  /* Legend */
  .legend {{
    display: flex; align-items: center; gap: 20px; margin: 18px 0 22px;
    color: var(--muted); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
    flex-wrap: wrap;
  }}
  .legend .legend-label {{ color: var(--dim); }}
  .legend .chip {{ display: inline-flex; align-items: center; gap: 8px; }}
  .chip .dot {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
  .dot.added    {{ background: var(--added); }}
  .dot.changed  {{ background: var(--changed); }}
  .dot.removed  {{ background: var(--removed); }}
  .dot.renamed  {{ background: var(--renamed); }}
  .dot.copied   {{ background: var(--copied); }}

  /* Two-column layout: sticky sidebar + scrollable main.
     Do NOT set align-items: start here. Grid cells must stretch to match
     the main column's height so the sidebar cell is tall enough for its
     position:sticky child to remain pinned as the page scrolls. */
  .layout {{
    display: grid;
    grid-template-columns: var(--sidebar-w) minmax(0, 1fr);
    gap: var(--gap);
  }}
  .sidebar {{ min-width: 0; }}
  .sidebar-sticky {{
    position: sticky;
    top: var(--pad);
    max-height: calc(100vh - var(--pad) * 2);
    overflow-y: auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
  }}
  .nav-head {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 14px; border-bottom: 1px solid var(--border);
    position: sticky; top: 0;
    background: var(--panel);
  }}
  .nav-head-label {{
    font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted);
  }}
  .nav-head-count {{
    font-family: var(--mono); font-size: 11px; color: var(--dim);
    background: var(--panel-alt); padding: 2px 7px; border-radius: 999px;
  }}
  .nav-totals {{
    display: flex; gap: 10px; padding: 8px 14px;
    font-family: var(--mono); font-size: 12px;
    border-bottom: 1px solid var(--border);
  }}
  .nav-list {{ padding: 4px 0; }}
  .nav-item {{
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px 6px 14px;
    color: var(--text); text-decoration: none;
    border-left: 2px solid transparent;
    font-size: 12.5px;
  }}
  .nav-item:hover {{ background: var(--panel-hover); border-left-color: var(--border-strong); }}
  .nav-item:target, .nav-item:focus {{
    background: var(--panel-hover); border-left-color: var(--renamed); outline: none;
  }}
  .nav-badge {{
    font-family: var(--mono); font-size: 10px; font-weight: 600;
    width: 18px; height: 18px; line-height: 18px; text-align: center;
    border-radius: 3px; border: 1px solid transparent; flex-shrink: 0;
  }}
  .nav-path {{
    flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0; line-height: 1.25;
    overflow: hidden;
  }}
  .nav-dir {{
    font-family: var(--mono); font-size: 10.5px; color: var(--dim);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    direction: rtl; text-align: left;
  }}
  .nav-base {{
    font-family: var(--mono); font-size: 12px; color: #c5e0ff;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .nav-stats {{
    font-family: var(--mono); font-size: 10.5px; flex-shrink: 0;
    display: flex; gap: 5px;
  }}
  .nav-stats.binary {{ color: var(--dim); font-style: italic; }}

  /* Badges */
  .badge {{
    font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em;
    padding: 2px 7px; border-radius: 3px; border: 1px solid transparent;
    flex-shrink: 0; text-align: center; min-width: 66px; display: inline-block;
  }}
  .badge-added, .nav-badge.badge-added       {{ color: var(--added);    background: var(--added-bg);    border-color: rgba(63,185,80,0.35); }}
  .badge-changed, .nav-badge.badge-changed   {{ color: var(--changed);  background: var(--changed-bg);  border-color: rgba(245,176,65,0.35); }}
  .badge-removed, .nav-badge.badge-removed   {{ color: var(--removed);  background: var(--removed-bg);  border-color: rgba(244,114,114,0.35); }}
  .badge-renamed, .nav-badge.badge-renamed   {{ color: var(--renamed);  background: var(--renamed-bg);  border-color: rgba(110,168,254,0.35); }}
  .badge-copied,  .nav-badge.badge-copied    {{ color: var(--copied);   background: var(--copied-bg);   border-color: rgba(163,113,247,0.35); }}
  .badge-unchanged,.nav-badge.badge-unchanged{{ color: var(--unchanged);background: var(--unchanged-bg);border-color: rgba(136,147,165,0.35); }}
  .add-count {{ color: var(--added); }}
  .del-count {{ color: var(--removed); }}

  /* Per-file diff blocks in the main column */
  .main {{ min-width: 0; }}
  .file-detail {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
    margin-bottom: 16px; overflow: hidden;
    scroll-margin-top: var(--pad);
  }}
  .file-summary-head {{
    display: flex; align-items: center; gap: 12px; padding: 12px 16px;
    cursor: pointer; border-bottom: 1px solid var(--border);
    list-style: none;
    position: sticky; top: 0; z-index: 2;
    background: var(--panel);
  }}
  .file-summary-head::-webkit-details-marker {{ display: none; }}
  .file-summary-head::before {{
    content: "▾"; color: var(--dim); font-size: 10px; width: 10px;
    transition: transform 0.15s;
  }}
  .file-detail:not([open]) .file-summary-head::before {{ transform: rotate(-90deg); }}
  .file-path {{ flex: 1; min-width: 0; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .file-path code {{
    font-family: var(--mono); color: #c5e0ff; font-size: 12.5px;
    background: none; padding: 0; border: none;
  }}
  .rename-from {{ color: var(--dim); font-family: var(--mono); font-size: 12px; }}
  .stat-nums {{
    font-family: var(--mono); font-size: 11px; color: var(--muted);
    display: inline-flex; gap: 8px;
  }}
  .stat-nums.binary {{ font-style: italic; color: var(--dim); }}
  .file-body {{ padding: 0; }}
  .hunk-header {{
    padding: 6px 16px; background: var(--panel-alt); color: var(--muted);
    font-size: 11px; border-bottom: 1px solid var(--border); border-top: 1px solid var(--border);
  }}
  .hunk-header code {{
    font-family: var(--mono); background: none; border: none; color: inherit; padding: 0;
  }}

  /* Diff table — side-by-side layout */
  .diff-table {{
    width: 100%; border-collapse: collapse;
    font-family: var(--mono); font-size: 12px;
    table-layout: fixed;
  }}
  .diff-table col.col-gutter {{ width: 46px; }}
  .diff-table col.col-code {{ width: auto; }}
  .diff-table .gutter {{
    text-align: right; padding: 0 8px; color: var(--dim);
    user-select: none;
    background: var(--panel-alt);
    font-variant-numeric: tabular-nums;
    border-right: 1px solid var(--border);
  }}
  .diff-table .gutter-new {{ border-left: 1px solid var(--border); }}
  .diff-table .diff-code {{
    padding: 1px 10px; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;
    color: var(--text);
    vertical-align: top;
  }}
  .diff-table .prefix {{
    color: var(--dim); margin-right: 4px; display: inline-block; width: 6px;
  }}
  .diff-add {{ background: var(--added-bg-soft); }}
  .diff-add .prefix {{ color: var(--added); }}
  .diff-del {{ background: var(--removed-bg-soft); }}
  .diff-del .prefix {{ color: var(--removed); }}
  .diff-empty {{ background: repeating-linear-gradient(
    45deg,
    rgba(255,255,255,0.01) 0 6px,
    transparent 6px 12px
  ); }}
  .gutter-empty {{ background: var(--panel-alt); }}
  .diff-meta {{ color: var(--muted); font-style: italic; padding: 2px 12px; }}
  .binary-note {{ padding: 16px; color: var(--muted); font-style: italic; }}
  .empty-row {{ color: var(--dim); padding: 16px; text-align: center; }}

  /* Commits section */
  .section {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px 20px; margin-bottom: 16px;
  }}
  .section-title {{
    display: flex; align-items: center; gap: 10px; margin: 0 0 12px;
    font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted);
  }}
  .section-title .marker {{ font-size: 14px; line-height: 1; color: var(--renamed); }}
  .commits-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .commits-table td {{ padding: 4px 8px; border-bottom: 1px solid rgba(34,43,57,0.6); vertical-align: top; }}
  .commits-table tr:last-child td {{ border-bottom: none; }}
  .commit-sha code {{ font-family: var(--mono); color: var(--renamed); background: none; border: none; padding: 0; }}
  .commit-date {{ color: var(--dim); font-family: var(--mono); font-size: 12px; white-space: nowrap; }}
  .commit-author {{ color: var(--muted); white-space: nowrap; }}
  .commit-subject {{ color: var(--text); }}

  code.inline {{
    font-family: var(--mono); font-size: 11.5px; color: #c5e0ff;
    background: rgba(110,168,254,0.08); padding: 1px 5px; border-radius: 3px;
    border: 1px solid rgba(110,168,254,0.15);
  }}

  /* Responsive: stack on narrow viewports */
  @media (max-width: 900px) {{
    :root {{ --pad: 16px; --sidebar-w: 100%; }}
    .layout {{ grid-template-columns: 1fr; }}
    .sidebar-sticky {{ position: static; max-height: none; }}
    .top {{ flex-direction: column; align-items: flex-start; }}
    .top-right {{ align-items: flex-start; text-align: left; min-width: 0; }}
    .diff-table col.col-gutter {{ width: 36px; }}
  }}
{annotation_css}
{comment_css}
</style>
</head>
<body data-comments-enabled="{comments_enabled_js}" data-report-id="{report_id}">
  <div class="page">
    <header class="top">
      <div class="top-left">
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
      </div>
      <div class="top-right">
        <span class="profile-pill">{profile}</span>
        <span class="stats-line">{stats_line}</span>
        <span class="gen-line">Generated {generated}</span>
      </div>
    </header>

    <div class="legend">
      <span class="legend-label">Status:</span>
      <span class="chip"><span class="dot added"></span>Added</span>
      <span class="chip"><span class="dot changed"></span>Modified</span>
      <span class="chip"><span class="dot removed"></span>Deleted</span>
      <span class="chip"><span class="dot renamed"></span>Renamed</span>
      <span class="chip"><span class="dot copied"></span>Copied</span>
    </div>

    <div class="layout">
      <aside class="sidebar">
        {sidebar}
      </aside>
      <main class="main">
        {commits_section}
        <section class="file-details">
          {detail_blocks}
        </section>
      </main>
    </div>
  </div>

  {floating_button}

{comment_script}
</body>
</html>
"""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "review"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true", help="Review only staged changes (index vs HEAD).")
    mode.add_argument("--base", metavar="REF", help="Review current branch vs this base (uses merge-base).")
    mode.add_argument("--commit", metavar="REF", help="Review a single commit's diff.")
    mode.add_argument("--range", metavar="A..B", help="Review an explicit revision range.")
    parser.add_argument("--repo", default=".", help="Repository root (default: cwd).")
    parser.add_argument("-U", "--context", type=int, default=3, help="Unified-diff context lines (default: 3).")
    parser.add_argument("-o", "--output", help="Output HTML path (default: slug-named file in OS temp dir).")
    parser.add_argument("--no-open", action="store_true", help="Write the file but do not open the browser.")
    parser.add_argument("--comments", action="store_true", help="Enable per-file comment widgets with export.")
    parser.add_argument(
        "--annotations",
        metavar="PATH",
        help=(
            "Path to a JSON file with agent-authored explanations. "
            "Schema: {\"files\": {\"<path>\": {\"summary\": \"...\", \"hunks\": [\"...\"]}}}. "
            "Renders 'Why this changed' callouts above each file and hunk in the report."
        ),
    )
    args = parser.parse_args()

    try:
        review = build_review(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    html_content = render_html(review, comments_enabled=args.comments)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        slug = slugify(review.title)
        output_path = Path(tempfile.gettempdir()) / f"git-visualizer-{slug}.html"

    output_path.write_text(html_content, encoding="utf-8")
    file_url = f"file://{output_path}"

    if not args.no_open:
        try:
            webbrowser.open(file_url)
        except Exception as exc:
            print(f"warning: could not open browser automatically: {exc}", file=sys.stderr)

    print(file_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
