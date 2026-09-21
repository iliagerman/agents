#!/usr/bin/env python3
"""Generate a visual HTML page from a structured plan or report JSON.

Two modes:
  - Plan mode  — BEFORE/AFTER columns + ADDED/CHANGED/REMOVED badges + file
                 manifest. Best for "here's what I'd change" proposals.
  - Report mode — free-form sections (prose / bullets / table / diagram /
                 callout / cards) for audits, reviews, investigations.
Both modes can render with per-section comment boxes (`comments_enabled: true`)
and a floating "Export comments" button that produces Markdown-formatted Q&A
the user can paste back to the assistant.

Output is a single self-contained HTML file. Mermaid is loaded from CDN with
a code-block fallback if offline. The file is opened via the `file://`
protocol so it works on macOS, Linux, and Windows.

Usage:
    python3 generate_visualization.py plan.json
    python3 generate_visualization.py - < plan.json
    python3 generate_visualization.py plan.json -o /tmp/my-plan.html --no-open
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
import webbrowser
from datetime import date
from pathlib import Path


STATUS_CLASSES = {
    "ADDED": "badge-added",
    "CHANGED": "badge-changed",
    "REMOVED": "badge-removed",
    "UNCHANGED": "badge-unchanged",
}


def render_inline(text: str) -> str:
    """Escape text and render `code` spans + **bold** in monospace/strong."""
    escaped = html.escape(text)
    # Code spans first (greedy non-backtick).
    escaped = re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', escaped)
    # Bold (**...**).
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def render_prose_body(text: str) -> str:
    """Split blank-line-separated paragraphs and render inline markup per paragraph."""
    if not text:
        return ""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "\n".join(
        f'<p class="prose-p">{render_inline(p.strip())}</p>'
        for p in paragraphs
        if p.strip()
    )


def render_column_item(item: dict) -> str:
    kind = item.get("kind", "card")
    if kind == "label":
        return f'<div class="col-label">{render_inline(item.get("title", ""))}</div>'

    title = render_inline(item.get("title", ""))
    status = (item.get("status") or "").upper()
    badge_class = STATUS_CLASSES.get(status, "badge-unchanged")
    badge_html = (
        f'<span class="badge {badge_class}">{html.escape(status)}</span>'
        if status
        else ""
    )

    details = item.get("details") or []
    details_html = ""
    if details:
        items_html = "".join(
            f'<li>{render_inline(detail)}</li>' for detail in details
        )
        details_html = f'<ul class="card-details">{items_html}</ul>'

    return (
        '<div class="card">'
        f'  <div class="card-head"><span class="card-title">{title}</span>{badge_html}</div>'
        f'  {details_html}'
        '</div>'
    )


def render_column(items: list[dict]) -> str:
    return "\n".join(render_column_item(item) for item in items)


def render_bullet_list(entries: list, symbol: str, symbol_class: str) -> str:
    if not entries:
        return '<div class="empty-row">—</div>'
    parts = []
    for entry in entries:
        if isinstance(entry, dict):
            desc = entry.get("description", "")
            mitigation = entry.get("mitigation")
            body = render_inline(desc)
            if mitigation:
                body += (
                    f' <span class="mitigation">— mitigation: '
                    f'{render_inline(mitigation)}</span>'
                )
        else:
            body = render_inline(str(entry))
        parts.append(
            f'<div class="bullet-row">'
            f'  <span class="bullet-symbol {symbol_class}">{symbol}</span>'
            f'  <span class="bullet-text">{body}</span>'
            f'</div>'
        )
    return "\n".join(parts)


FILE_ACTION_CLASSES = {
    "ADD": "badge-added",
    "MODIFY": "badge-changed",
    "REMOVE": "badge-removed",
}


def render_file_manifest(entries: list[dict]) -> str:
    if not entries:
        return ""
    rows = []
    for entry in entries:
        path = html.escape(entry.get("path", ""))
        action = (entry.get("action") or "modify").upper()
        badge_class = FILE_ACTION_CLASSES.get(action, "badge-changed")
        desc = render_inline(entry.get("description", ""))
        rows.append(
            f'<tr>'
            f'<td><span class="badge {badge_class}">{html.escape(action)}</span></td>'
            f'<td><code class="inline">{path}</code></td>'
            f'<td class="fm-desc">{desc}</td>'
            f'</tr>'
        )
    table_rows = "\n".join(rows)
    return wrap_section_with_comment(
        section_id="file-manifest",
        title='<span class="marker sym-file">⊞</span>File manifest',
        body=(
            '<table class="file-manifest">'
            '<thead><tr><th>Action</th><th>Path</th><th>Description</th></tr></thead>'
            f'<tbody>{table_rows}</tbody>'
            '</table>'
        ),
    )


def render_diagrams(entries: list[dict]) -> str:
    if not entries:
        return ""
    parts = []
    for entry in entries:
        title = html.escape(entry.get("title", "Diagram"))
        desc = render_inline(entry.get("description", ""))
        mermaid_src = entry.get("mermaid", "")
        desc_html = f'<p class="diagram-desc">{desc}</p>' if desc else ""
        parts.append(
            f'<div class="diagram-block">'
            f'<h3 class="diagram-title">{title}</h3>'
            f'{desc_html}'
            f'<div class="mermaid">{html.escape(mermaid_src)}</div>'
            f'<pre class="mermaid-fallback">{html.escape(mermaid_src)}</pre>'
            f'</div>'
        )
    blocks = "\n".join(parts)
    return wrap_section_with_comment(
        section_id="diagrams",
        title='<span class="marker sym-diagram">◈</span>Diagrams',
        body=blocks,
    )


def render_tradeoffs(entries: list[dict]) -> str:
    if not entries:
        return ""
    parts = []
    for entry in entries:
        decision = render_inline(entry.get("decision", ""))
        pros = entry.get("pros") or []
        cons = entry.get("cons") or []
        pros_items = "".join(f'<li class="pro-item">{render_inline(p)}</li>' for p in pros)
        cons_items = "".join(f'<li class="con-item">{render_inline(c)}</li>' for c in cons)
        parts.append(
            f'<div class="tradeoff-card">'
            f'<div class="tradeoff-decision">{decision}</div>'
            f'<div class="tradeoff-columns">'
            f'<div class="tradeoff-col"><div class="tradeoff-col-head pro-head">Pros</div><ul class="tradeoff-list">{pros_items}</ul></div>'
            f'<div class="tradeoff-col"><div class="tradeoff-col-head con-head">Cons</div><ul class="tradeoff-list">{cons_items}</ul></div>'
            f'</div></div>'
        )
    blocks = "\n".join(parts)
    return wrap_section_with_comment(
        section_id="tradeoffs",
        title='<span class="marker sym-tradeoff">⇋</span>Tradeoffs',
        body=blocks,
    )


def render_alternatives(entries: list[dict]) -> str:
    if not entries:
        return ""
    parts = []
    for entry in entries:
        title = render_inline(entry.get("title", ""))
        desc = render_inline(entry.get("description", ""))
        why_rejected = render_inline(entry.get("why_rejected", ""))
        rejected_html = (
            f'<div class="alt-rejected"><span class="alt-rejected-label">Why not:</span> {why_rejected}</div>'
            if why_rejected else ""
        )
        parts.append(
            f'<div class="alt-card">'
            f'<div class="alt-title">{title}</div>'
            f'<div class="alt-desc">{desc}</div>'
            f'{rejected_html}'
            f'</div>'
        )
    blocks = "\n".join(parts)
    return wrap_section_with_comment(
        section_id="alternatives",
        title='<span class="marker sym-alt">⊘</span>Alternatives considered',
        body=blocks,
    )


# ---------- Free-form report sections ----------

CARD_TONE_CLASSES = {
    "good": "tone-good",
    "info": "tone-info",
    "warn": "tone-warn",
    "high": "tone-high",
    "critical": "tone-critical",
    "medium": "tone-warn",
    "low": "tone-info",
}

CALLOUT_VARIANT_CLASSES = {
    "info": "callout-info",
    "good": "callout-good",
    "warn": "callout-warn",
    "error": "callout-error",
}


def render_section_body(section: dict) -> str:
    """Render the inner body of a free-form section based on `type`."""
    stype = (section.get("type") or "prose").lower()

    if stype == "prose":
        return f'<div class="section-prose">{render_prose_body(section.get("body", ""))}</div>'

    if stype == "bullets":
        items = section.get("items", [])
        if not items:
            return '<div class="empty-row">—</div>'
        parts = []
        for item in items:
            if isinstance(item, dict):
                # Allow {title, body} for richer bullets
                t = render_inline(item.get("title", ""))
                b = render_inline(item.get("body", ""))
                inner = f'<strong>{t}</strong> — {b}' if t and b else (t or b)
            else:
                inner = render_inline(str(item))
            parts.append(
                f'<div class="bullet-row">'
                f'<span class="bullet-symbol sym-arrow">→</span>'
                f'<span class="bullet-text">{inner}</span>'
                f'</div>'
            )
        return "\n".join(parts)

    if stype == "table":
        cols = section.get("columns", [])
        rows = section.get("rows", [])
        thead = "".join(f"<th>{render_inline(str(c))}</th>" for c in cols)
        tbody_rows = []
        for r in rows:
            if isinstance(r, dict):
                # Allow {cells: [...]} or column-keyed dict
                if "cells" in r:
                    cells = r["cells"]
                else:
                    cells = [r.get(str(c), "") for c in cols]
            else:
                cells = r
            tds = "".join(f"<td>{render_inline(str(c))}</td>" for c in cells)
            tbody_rows.append(f"<tr>{tds}</tr>")
        return (
            '<table class="report-table">'
            f'<thead><tr>{thead}</tr></thead>'
            f'<tbody>{"".join(tbody_rows)}</tbody>'
            '</table>'
        )

    if stype == "diagram":
        title = html.escape(section.get("subtitle", "") or "")
        desc = render_inline(section.get("description", ""))
        mermaid_src = section.get("mermaid", "")
        desc_html = f'<p class="diagram-desc">{desc}</p>' if desc else ""
        sub_html = f'<h3 class="diagram-title">{title}</h3>' if title else ""
        return (
            f'<div class="diagram-block">'
            f'{sub_html}'
            f'{desc_html}'
            f'<div class="mermaid">{html.escape(mermaid_src)}</div>'
            f'<pre class="mermaid-fallback">{html.escape(mermaid_src)}</pre>'
            f'</div>'
        )

    if stype == "callout":
        variant = (section.get("variant") or "info").lower()
        klass = CALLOUT_VARIANT_CLASSES.get(variant, "callout-info")
        body = render_prose_body(section.get("body", ""))
        return f'<div class="callout {klass}">{body}</div>'

    if stype == "cards":
        cards = section.get("cards", [])
        if not cards:
            return '<div class="empty-row">—</div>'
        parts = []
        for c in cards:
            t = render_inline(c.get("title", ""))
            b = render_inline(c.get("body", ""))
            tone = (c.get("tone") or "info").lower()
            tone_class = CARD_TONE_CLASSES.get(tone, "tone-info")
            tone_label = html.escape(tone.upper())
            parts.append(
                f'<div class="report-card {tone_class}">'
                f'<div class="report-card-head"><span class="report-card-title">{t}</span>'
                f'<span class="tone-badge">{tone_label}</span></div>'
                f'<div class="report-card-body">{b}</div>'
                f'</div>'
            )
        return f'<div class="report-cards-grid">{"".join(parts)}</div>'

    if stype == "raw_html":
        # Escape hatch — use sparingly
        return section.get("html", "")

    return f'<div class="empty-row">unsupported section type: {html.escape(stype)}</div>'


def render_sections(sections: list[dict]) -> str:
    if not sections:
        return ""
    parts = []
    for s in sections:
        sid = s.get("id") or ""
        raw_title = s.get("title", "")
        title = render_inline(raw_title)
        body = render_section_body(s)
        parts.append(
            wrap_section_with_comment(
                section_id=sid,
                title=title,
                body=body,
                label=raw_title,
            )
        )
    return "\n".join(parts)


# ---------- Comment widget plumbing ----------

# A module-level toggle so wrap_section_with_comment knows whether to emit
# the comment widget or omit it. Set in render_html() before any rendering.
_COMMENTS_ENABLED = False


def wrap_section_with_comment(section_id: str, title: str, body: str, label: str = "") -> str:
    """Wrap a section's content in <section>, with an optional comment widget."""
    sid = re.sub(r"[^a-zA-Z0-9_-]+", "-", section_id).strip("-") or "section"
    title_html = title  # caller has already rendered HTML for marker + text
    clean_label = label
    if not clean_label:
        clean_label = re.sub(r"<[^>]+>", "", title).strip()
        clean_label = clean_label.lstrip("→◇◈⇋⊘⚠✕⊞ ").strip()
    comment_html = ""
    if _COMMENTS_ENABLED:
        comment_html = (
            f'<div class="comment-widget" data-section-id="{sid}">'
            f'<button type="button" class="comment-toggle" aria-expanded="false">💬 Comment</button>'
            f'<div class="comment-body" hidden>'
            f'<textarea class="comment-textarea" data-section-id="{sid}" '
            f'placeholder="Type your question or comment for this section…"></textarea>'
            f'<div class="comment-meta"><span class="comment-saved-indicator" aria-live="polite"></span></div>'
            f'</div>'
            f'</div>'
        )
    return (
        f'<section class="section" id="sec-{sid}" data-section-id="{sid}"'
        f' data-section-label="{html.escape(clean_label)}">'
        f'<h2 class="section-title">{title_html}'
        f'<a class="section-anchor" href="#sec-{sid}" title="permalink">¶</a>'
        f'</h2>'
        f'{body}'
        f'{comment_html}'
        f'</section>'
    )


# ---------- Top-level render ----------

def render_html(plan: dict) -> str:
    global _COMMENTS_ENABLED
    _COMMENTS_ENABLED = bool(plan.get("comments_enabled", False))

    title = html.escape(plan.get("title", "Plan Visualization"))
    subtitle = render_inline(plan.get("subtitle", ""))
    profile = html.escape(plan.get("profile") or "PLAN")
    theme = (plan.get("theme") or "dark").lower()
    if theme not in ("dark", "light"):
        theme = "dark"
    file_count = plan.get("file_count")
    step_count = plan.get("step_count")
    generated = html.escape(plan.get("generated") or date.today().isoformat())
    report_id = html.escape(plan.get("report_id") or slugify(plan.get("title") or "report"))

    summary_parts = []
    if file_count is not None:
        label = "FILE" if file_count == 1 else "FILES"
        summary_parts.append(f"{file_count} {label}")
    if step_count is not None:
        label = "STEP" if step_count == 1 else "STEPS"
        summary_parts.append(f"{step_count} {label}")
    summary_line = html.escape(" · ".join(summary_parts)) if summary_parts else ""

    # Plan-mode columns
    before_items = plan.get("before", [])
    after_items = plan.get("after", [])
    columns_html = ""
    if before_items or after_items:
        before_html = render_column(before_items)
        after_html = render_column(after_items)
        columns_html = (
            '<div class="columns">'
            f'<section class="column" id="sec-before" data-section-id="before" data-section-label="Before">'
            f'<div class="column-head">Before</div>{before_html}'
        )
        if _COMMENTS_ENABLED:
            columns_html += render_inline_comment_widget("before")
        columns_html += (
            f'</section>'
            f'<section class="column" id="sec-after" data-section-id="after" data-section-label="After">'
            f'<div class="column-head">After</div>{after_html}'
        )
        if _COMMENTS_ENABLED:
            columns_html += render_inline_comment_widget("after")
        columns_html += '</section></div>'

    file_manifest_html = render_file_manifest(plan.get("file_manifest", []))
    diagrams_html = render_diagrams(plan.get("diagrams", []))

    # Free-form sections (report mode)
    sections_html = render_sections(plan.get("sections", []))

    # Plan-mode standard sections — only render if non-empty (avoid noisy empty boxes for reports)
    key_changes_html = ""
    if plan.get("key_changes"):
        key_changes_html = wrap_section_with_comment(
            section_id="key-changes",
            title='<span class="marker sym-arrow">→</span>Key changes',
            body=render_bullet_list(plan["key_changes"], "→", "sym-arrow"),
        )

    tradeoffs_html = render_tradeoffs(plan.get("tradeoffs", []))

    key_decisions_html = ""
    if plan.get("key_decisions"):
        key_decisions_html = wrap_section_with_comment(
            section_id="key-decisions",
            title='<span class="marker sym-diamond">◇</span>Key decisions',
            body=render_bullet_list(plan["key_decisions"], "◇", "sym-diamond"),
        )

    alternatives_html = render_alternatives(plan.get("alternatives", []))

    risks_html = ""
    if plan.get("risks"):
        risks_html = wrap_section_with_comment(
            section_id="risks",
            title='<span class="marker sym-warn">⚠</span>Risks',
            body=render_bullet_list(plan["risks"], "⚠", "sym-warn"),
        )

    out_of_scope_html = ""
    if plan.get("out_of_scope"):
        out_of_scope_html = wrap_section_with_comment(
            section_id="out-of-scope",
            title='<span class="marker sym-x">✕</span>Out of scope',
            body=render_bullet_list(plan["out_of_scope"], "✕", "sym-x"),
        )

    # Floating export button only if comments enabled
    floating_button_html = ""
    if _COMMENTS_ENABLED:
        floating_button_html = (
            '<div id="export-bar">'
            '<button type="button" id="export-btn">📋 Export comments</button>'
            '<span id="export-count" class="export-count">0 comments</span>'
            '</div>'
            # Modal overlay
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

    return TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        profile=profile,
        summary_line=summary_line,
        generated=generated,
        report_id=report_id,
        comments_enabled_js=("true" if _COMMENTS_ENABLED else "false"),
        theme=theme,
        mermaid_theme=("default" if theme == "light" else "dark"),
        columns=columns_html,
        file_manifest=file_manifest_html,
        diagrams=diagrams_html,
        sections=sections_html,
        key_changes=key_changes_html,
        tradeoffs=tradeoffs_html,
        key_decisions=key_decisions_html,
        alternatives=alternatives_html,
        risks=risks_html,
        out_of_scope=out_of_scope_html,
        floating_button=floating_button_html,
    )


def render_inline_comment_widget(section_id: str) -> str:
    sid = re.sub(r"[^a-zA-Z0-9_-]+", "-", section_id).strip("-") or "section"
    return (
        f'<div class="comment-widget" data-section-id="{sid}">'
        f'<button type="button" class="comment-toggle" aria-expanded="false">💬 Comment</button>'
        f'<div class="comment-body" hidden>'
        f'<textarea class="comment-textarea" data-section-id="{sid}" '
        f'placeholder="Type your question or comment for this section…"></textarea>'
        f'<div class="comment-meta"><span class="comment-saved-indicator" aria-live="polite"></span></div>'
        f'</div>'
        f'</div>'
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  /* Dark palette (default) */
  body.theme-dark {{
    --bg: #0b0f14;
    --panel: #131922;
    --panel-alt: #182030;
    --border: #222b39;
    --border-strong: #2f3a4c;
    --text: #e6ebf2;
    --text-soft: #d0d7e3;
    --text-soft-2: #c3cbd8;
    --strong: #f4f7fb;
    --muted: #8893a5;
    --dim: #5b6778;
    --code-text: #c5e0ff;
    --code-bg: rgba(110,168,254,0.08);
    --code-border: rgba(110,168,254,0.15);
    --added: #3fb950;
    --added-bg: rgba(63,185,80,0.14);
    --added-border: rgba(63,185,80,0.35);
    --changed: #f5b041;
    --changed-bg: rgba(245,176,65,0.14);
    --changed-border: rgba(245,176,65,0.35);
    --removed: #f47272;
    --removed-bg: rgba(244,114,114,0.14);
    --removed-border: rgba(244,114,114,0.35);
    --unchanged: #8893a5;
    --unchanged-bg: rgba(136,147,165,0.14);
    --unchanged-border: rgba(136,147,165,0.35);
    --info: #6ea8fe;
    --info-bg: rgba(110,168,254,0.10);
    --info-border: rgba(110,168,254,0.35);
    --high: #ff7a59;
    --high-bg: rgba(255,122,89,0.10);
    --high-border: rgba(255,122,89,0.40);
    --critical: #ff4d4d;
    --critical-bg: rgba(255,77,77,0.12);
    --critical-border: rgba(255,77,77,0.45);
    --pro-text: rgba(63,185,80,0.85);
    --con-text: rgba(244,114,114,0.85);
  }}
  /* Light palette — clean, elegant, easy to read */
  body.theme-light {{
    --bg: #ffffff;
    --panel: #fbfcfd;
    --panel-alt: #f3f5f8;
    --border: #e4e7ec;
    --border-strong: #cdd2d9;
    --text: #1c2230;
    --text-soft: #2f3744;
    --text-soft-2: #4a5364;
    --strong: #0d1320;
    --muted: #586173;
    --dim: #8590a3;
    --code-text: #0a4ea6;
    --code-bg: rgba(9,105,218,0.06);
    --code-border: rgba(9,105,218,0.18);
    --added: #1a7f37;
    --added-bg: rgba(26,127,55,0.08);
    --added-border: rgba(26,127,55,0.30);
    --changed: #9a6700;
    --changed-bg: rgba(154,103,0,0.08);
    --changed-border: rgba(154,103,0,0.30);
    --removed: #cf222e;
    --removed-bg: rgba(207,34,46,0.08);
    --removed-border: rgba(207,34,46,0.30);
    --unchanged: #6e7686;
    --unchanged-bg: rgba(110,118,134,0.08);
    --unchanged-border: rgba(110,118,134,0.30);
    --info: #0969da;
    --info-bg: rgba(9,105,218,0.06);
    --info-border: rgba(9,105,218,0.25);
    --high: #bc4c00;
    --high-bg: rgba(188,76,0,0.06);
    --high-border: rgba(188,76,0,0.30);
    --critical: #a40e26;
    --critical-bg: rgba(164,14,38,0.06);
    --critical-border: rgba(164,14,38,0.30);
    --pro-text: #1a7f37;
    --con-text: #cf222e;
  }}
  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.55;
    margin: 0;
    padding: 0;
  }}
  .page {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 32px 96px;
  }}
  .top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border);
  }}
  .top-left h1 {{
    margin: 0 0 8px;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  .top-left .subtitle {{
    color: var(--muted);
    font-size: 13.5px;
    max-width: 820px;
  }}
  .top-right {{
    text-align: right;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 6px;
    min-width: 180px;
  }}
  .profile-pill {{
    border: 1px solid var(--border-strong);
    background: var(--panel);
    color: var(--muted);
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .summary-line, .gen-line {{
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .gen-line {{ color: var(--dim); }}

  .legend {{
    display: flex;
    align-items: center;
    gap: 20px;
    margin: 18px 0 22px;
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .legend .legend-label {{ color: var(--dim); }}
  .legend .chip {{ display: inline-flex; align-items: center; gap: 8px; }}
  .chip .dot {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
  .dot.added {{ background: var(--added); }}
  .dot.changed {{ background: var(--changed); }}
  .dot.removed {{ background: var(--removed); }}
  .dot.unchanged {{ background: var(--unchanged); }}

  .columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }}
  .column {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 18px 12px;
    position: relative;
  }}
  .column-head {{
    font-size: 11px;
    letter-spacing: 0.14em;
    color: var(--muted);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 14px;
  }}
  .col-label {{
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 14px 0 8px;
    padding-left: 2px;
  }}
  .card {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    margin-bottom: 12px;
  }}
  .card-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }}
  .card-title {{
    font-weight: 600;
    font-size: 13px;
    color: var(--text);
  }}
  .badge {{
    font-family: var(--mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 2px 7px;
    border-radius: 3px;
    border: 1px solid transparent;
    flex-shrink: 0;
  }}
  .badge-added    {{ color: var(--added);    background: var(--added-bg);    border-color: var(--added-border); }}
  .badge-changed  {{ color: var(--changed);  background: var(--changed-bg);  border-color: var(--changed-border); }}
  .badge-removed  {{ color: var(--removed);  background: var(--removed-bg);  border-color: var(--removed-border); }}
  .badge-unchanged{{ color: var(--unchanged);background: var(--unchanged-bg);border-color: var(--unchanged-border); }}

  .card-details {{
    list-style: none; padding: 0; margin: 0;
    font-size: 12.5px; color: var(--text-soft-2);
  }}
  .card-details li {{ padding: 2px 0 2px 14px; position: relative; }}
  .card-details li::before {{ content: "·"; color: var(--dim); position: absolute; left: 4px; font-weight: 700; }}
  code.inline {{
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--code-text);
    background: var(--code-bg);
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid var(--code-border);
  }}
  strong {{ color: var(--strong); font-weight: 600; }}

  .section {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 22px;
    margin-top: 18px;
    position: relative;
  }}
  .section-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 14px;
    font-size: 13.5px;
    letter-spacing: 0.04em;
    color: var(--text);
    font-weight: 600;
  }}
  .section-title .marker {{ font-size: 16px; line-height: 1; }}
  .section-anchor {{
    color: var(--dim);
    text-decoration: none;
    margin-left: 6px;
    opacity: 0;
    transition: opacity 120ms;
    font-weight: 400;
  }}
  .section:hover .section-anchor {{ opacity: 1; }}

  .section-prose .prose-p {{
    margin: 0 0 12px;
    color: var(--text-soft);
    font-size: 13.5px;
  }}
  .section-prose .prose-p:last-child {{ margin-bottom: 0; }}

  .bullet-row {{ display: flex; gap: 10px; padding: 4px 0; font-size: 13px; color: var(--text-soft); }}
  .bullet-symbol {{ flex-shrink: 0; width: 16px; text-align: center; font-weight: 700; }}
  .sym-arrow   {{ color: var(--added); }}
  .sym-diamond {{ color: #6ea8fe; }}
  .sym-warn    {{ color: var(--changed); }}
  .sym-x       {{ color: var(--removed); }}
  .bullet-text {{ flex: 1; }}
  .mitigation  {{ color: var(--muted); font-style: italic; }}
  .empty-row   {{ color: var(--dim); font-size: 12px; padding: 4px 0; }}

  /* File manifest + report tables */
  .file-manifest, .report-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .file-manifest th, .report-table th {{
    text-align: left;
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
  }}
  .file-manifest td, .report-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  .file-manifest tr:last-child td,
  .report-table tr:last-child td {{ border-bottom: none; }}
  .fm-desc {{ color: var(--muted); font-size: 12.5px; }}
  .sym-file {{ color: #6ea8fe; }}

  /* Diagrams */
  .sym-diagram {{ color: #a78bfa; }}
  .diagram-block {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 16px;
    margin-bottom: 12px;
  }}
  .diagram-title {{ font-size: 13px; font-weight: 600; margin: 0 0 6px; color: var(--text); }}
  .diagram-desc  {{ font-size: 12.5px; color: var(--muted); margin: 0 0 12px; }}
  .mermaid {{ text-align: center; background: transparent; }}
  .mermaid-fallback {{
    display: none;
    font-family: var(--mono);
    font-size: 11.5px;
    color: var(--muted);
    background: rgba(110,168,254,0.05);
    padding: 12px;
    border-radius: 4px;
    border: 1px solid var(--border);
    white-space: pre-wrap;
    overflow-x: auto;
  }}

  /* Tradeoffs */
  .sym-tradeoff {{ color: #f5b041; }}
  .tradeoff-card {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .tradeoff-decision {{ font-weight: 600; font-size: 13px; margin-bottom: 10px; color: var(--text); }}
  .tradeoff-columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .tradeoff-col-head {{ font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px; font-weight: 600; }}
  .pro-head {{ color: var(--added); }}
  .con-head {{ color: var(--removed); }}
  .tradeoff-list {{ list-style: none; padding: 0; margin: 0; font-size: 12.5px; }}
  .tradeoff-list li {{ padding: 2px 0 2px 14px; position: relative; color: var(--text-soft-2); }}
  .tradeoff-list li::before {{ content: "·"; color: var(--dim); position: absolute; left: 4px; font-weight: 700; }}
  .pro-item {{ color: var(--pro-text); }}
  .con-item {{ color: var(--con-text); }}

  /* Alternatives */
  .sym-alt {{ color: var(--muted); }}
  .alt-card {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .alt-title {{ font-weight: 600; font-size: 13px; color: var(--text); margin-bottom: 4px; }}
  .alt-desc  {{ font-size: 12.5px; color: var(--text-soft-2); margin-bottom: 6px; }}
  .alt-rejected {{ font-size: 12px; color: var(--muted); font-style: italic; }}
  .alt-rejected-label {{ color: var(--removed); font-style: normal; font-weight: 600; }}

  /* Callouts */
  .callout {{
    border-left: 3px solid;
    padding: 12px 16px;
    border-radius: 4px;
    margin: 4px 0;
  }}
  .callout-info  {{ border-color: var(--info);     background: var(--info-bg); }}
  .callout-good  {{ border-color: var(--added);    background: var(--added-bg); }}
  .callout-warn  {{ border-color: var(--changed);  background: var(--changed-bg); }}
  .callout-error {{ border-color: var(--removed);  background: var(--removed-bg); }}
  .callout .prose-p:last-child {{ margin-bottom: 0; }}

  /* Cards grid (report mode) */
  .report-cards-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
  }}
  .report-card {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    border-left-width: 3px;
  }}
  .report-card-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }}
  .report-card-title {{ font-weight: 600; font-size: 13px; color: var(--text); }}
  .report-card-body  {{ font-size: 12.5px; color: var(--text-soft-2); }}
  .tone-badge {{
    font-family: var(--mono);
    font-size: 9.5px;
    letter-spacing: 0.08em;
    padding: 1px 6px;
    border-radius: 3px;
    border: 1px solid transparent;
  }}
  .tone-good     {{ border-left-color: var(--added);  }}
  .tone-good     .tone-badge {{ color: var(--added);    background: var(--added-bg);    border-color: var(--added-border); }}
  .tone-info     {{ border-left-color: var(--info);    }}
  .tone-info     .tone-badge {{ color: var(--info);     background: var(--info-bg);     border-color: var(--info-border); }}
  .tone-warn     {{ border-left-color: var(--changed); }}
  .tone-warn     .tone-badge {{ color: var(--changed);  background: var(--changed-bg);  border-color: var(--changed-border); }}
  .tone-high     {{ border-left-color: var(--high);    }}
  .tone-high     .tone-badge {{ color: var(--high);     background: var(--high-bg);     border-color: var(--high-border); }}
  .tone-critical {{ border-left-color: var(--critical);}}
  .tone-critical .tone-badge {{ color: var(--critical); background: var(--critical-bg); border-color: var(--critical-border);  }}

  /* Comment widget */
  .comment-widget {{
    margin-top: 16px;
    border-top: 1px dashed var(--border);
    padding-top: 12px;
  }}
  .comment-toggle {{
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
  }}
  .comment-toggle:hover {{ color: var(--text); border-color: var(--info); }}
  .comment-toggle.has-comment {{ color: var(--info); border-color: var(--info); }}
  .comment-body {{ margin-top: 10px; }}
  .comment-textarea {{
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
  }}
  .comment-textarea:focus {{ outline: none; border-color: var(--info); }}
  .comment-meta {{
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
    min-height: 16px;
  }}
  .comment-saved-indicator {{
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.04em;
  }}

  /* Floating export bar */
  #export-bar {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 100;
  }}
  #export-btn {{
    background: var(--info);
    color: #0a0d12;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    transition: transform 120ms, box-shadow 120ms;
  }}
  #export-btn:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.5);
  }}
  #export-btn:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }}
  .export-count {{
    background: var(--panel);
    border: 1px solid var(--border-strong);
    color: var(--muted);
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 11.5px;
    letter-spacing: 0.04em;
  }}

  /* Modal — note `display: flex` only when NOT hidden, otherwise the
     `hidden` attribute cannot hide the overlay. Without the `:not([hidden])`
     selector, this rule wins over the UA `[hidden] {{ display: none }}` rule
     (specificity 0,1,0 vs 0,0,1) and the modal stays open on load. */
  .export-modal:not([hidden]) {{
    display: flex;
  }}
  .export-modal {{
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    align-items: center;
    justify-content: center;
    z-index: 200;
  }}
  .export-modal-inner {{
    width: min(720px, 90vw);
    max-height: 80vh;
    background: var(--panel);
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .export-modal-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .export-modal-title {{ font-size: 14px; font-weight: 600; color: var(--text); }}
  .export-modal-close {{
    background: transparent;
    color: var(--muted);
    border: none;
    font-size: 20px;
    cursor: pointer;
    line-height: 1;
  }}
  .export-modal-close:hover {{ color: var(--text); }}
  #export-modal-text {{
    width: 100%;
    flex: 1;
    min-height: 280px;
    box-sizing: border-box;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 12px;
    font-family: var(--mono);
    font-size: 12px;
    line-height: 1.55;
    resize: vertical;
  }}
  .export-modal-actions {{
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    flex-wrap: wrap;
  }}
  .export-action-btn {{
    background: var(--panel-alt);
    color: var(--text);
    border: 1px solid var(--border-strong);
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12.5px;
    cursor: pointer;
    transition: border-color 120ms, color 120ms;
  }}
  .export-action-btn:hover {{ border-color: var(--info); color: var(--info); }}
  .export-clear:hover {{ border-color: var(--removed); color: var(--removed); }}

  @media (max-width: 820px) {{
    .columns {{ grid-template-columns: 1fr; }}
    .top {{ flex-direction: column; align-items: flex-start; }}
    .top-right {{ align-items: flex-start; text-align: left; }}
    #export-bar {{ bottom: 12px; right: 12px; }}
  }}
</style>
</head>
<body class="theme-{theme}" data-comments-enabled="{comments_enabled_js}" data-report-id="{report_id}">
  <div class="page">
    <header class="top">
      <div class="top-left">
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
      </div>
      <div class="top-right">
        <span class="profile-pill">{profile}</span>
        <span class="summary-line">{summary_line}</span>
        <span class="gen-line">Generated {generated}</span>
      </div>
    </header>

    <div class="legend">
      <span class="legend-label">Change key:</span>
      <span class="chip"><span class="dot added"></span>Added</span>
      <span class="chip"><span class="dot changed"></span>Changed</span>
      <span class="chip"><span class="dot removed"></span>Removed</span>
      <span class="chip"><span class="dot unchanged"></span>Unchanged</span>
    </div>

    {columns}

    {file_manifest}

    {diagrams}

    {sections}

    {key_changes}

    {tradeoffs}

    {key_decisions}

    {alternatives}

    {risks}

    {out_of_scope}
  </div>

  {floating_button}

  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    (function() {{
      // ---- Mermaid init ----
      var mermaidBlocks = document.querySelectorAll('.mermaid');
      var isLight = document.body.classList.contains('theme-light');
      var mermaidVars = isLight ? {{
        primaryColor: '#f3f5f8',
        primaryTextColor: '#1c2230',
        primaryBorderColor: '#cdd2d9',
        lineColor: '#586173',
        secondaryColor: '#fbfcfd',
        tertiaryColor: '#ffffff',
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, Segoe UI, Roboto, sans-serif',
        fontSize: '13px'
      }} : {{
        primaryColor: '#182030',
        primaryTextColor: '#e6ebf2',
        primaryBorderColor: '#2f3a4c',
        lineColor: '#5b6778',
        secondaryColor: '#131922',
        tertiaryColor: '#0b0f14',
        fontFamily: '-apple-system, BlinkMacSystemFont, Inter, Segoe UI, Roboto, sans-serif',
        fontSize: '13px'
      }};
      if (mermaidBlocks.length > 0 && typeof mermaid !== 'undefined') {{
        try {{
          mermaid.initialize({{
            startOnLoad: true,
            theme: '{mermaid_theme}',
            themeVariables: mermaidVars
          }});
        }} catch (e) {{
          mermaidBlocks.forEach(function(el) {{
            el.style.display = 'none';
            var fb = el.nextElementSibling;
            if (fb && fb.classList.contains('mermaid-fallback')) fb.style.display = 'block';
          }});
        }}
      }} else if (mermaidBlocks.length > 0) {{
        mermaidBlocks.forEach(function(el) {{
          el.style.display = 'none';
          var fb = el.nextElementSibling;
          if (fb && fb.classList.contains('mermaid-fallback')) fb.style.display = 'block';
        }});
      }}

      // ---- Comments ----
      var enabled = document.body.getAttribute('data-comments-enabled') === 'true';
      if (!enabled) return;
      var reportId = document.body.getAttribute('data-report-id') || 'report';
      var storageKey = 'planviz:' + reportId;

      function loadComments() {{
        try {{ return JSON.parse(localStorage.getItem(storageKey) || '{{}}'); }}
        catch (e) {{ return {{}}; }}
      }}
      function saveComments(map) {{
        try {{ localStorage.setItem(storageKey, JSON.stringify(map)); }}
        catch (e) {{}}
      }}
      function updateExportCount() {{
        var map = loadComments();
        var n = Object.keys(map).filter(function(k) {{ return (map[k] || '').trim().length > 0; }}).length;
        var el = document.getElementById('export-count');
        var btn = document.getElementById('export-btn');
        if (el) el.textContent = n + (n === 1 ? ' comment' : ' comments');
        if (btn) btn.disabled = (n === 0);
      }}

      // Hydrate textareas + wire up events
      // Comment widgets are ALWAYS collapsed by default, even when a saved
      // comment exists. The button gets a `has-comment` class as a visual
      // indicator, and the textarea is hydrated so the value is there when
      // the user re-opens it. Toggling is purely on click.
      var data = loadComments();
      var widgets = document.querySelectorAll('.comment-widget');
      widgets.forEach(function(w) {{
        var sid = w.getAttribute('data-section-id');
        var btn = w.querySelector('.comment-toggle');
        var body = w.querySelector('.comment-body');
        var ta = w.querySelector('.comment-textarea');
        var indicator = w.querySelector('.comment-saved-indicator');

        // Hydrate value + indicator class, but DO NOT auto-open.
        if (data[sid]) {{
          ta.value = data[sid];
          btn.classList.add('has-comment');
          btn.textContent = '💬 Comment (saved)';
        }}
        // Always start collapsed.
        body.hidden = true;
        btn.setAttribute('aria-expanded', 'false');

        btn.addEventListener('click', function(e) {{
          e.preventDefault();
          var isHidden = body.hidden;
          if (isHidden) {{
            body.hidden = false;
            btn.setAttribute('aria-expanded', 'true');
            ta.focus();
          }} else {{
            body.hidden = true;
            btn.setAttribute('aria-expanded', 'false');
          }}
        }});

        var saveTimer = null;
        ta.addEventListener('input', function() {{
          if (saveTimer) clearTimeout(saveTimer);
          if (indicator) indicator.textContent = 'saving…';
          saveTimer = setTimeout(function() {{
            var map = loadComments();
            var v = ta.value.trim();
            if (v) {{
              map[sid] = ta.value;
              btn.classList.add('has-comment');
              btn.textContent = '💬 Comment (saved)';
            }} else {{
              delete map[sid];
              btn.classList.remove('has-comment');
              btn.textContent = '💬 Comment';
            }}
            saveComments(map);
            if (indicator) {{
              indicator.textContent = 'saved';
              setTimeout(function() {{ if (indicator.textContent === 'saved') indicator.textContent = ''; }}, 1200);
            }}
            updateExportCount();
          }}, 350);
        }});
      }});

      updateExportCount();

      // ---- Export modal ----
      var exportBtn = document.getElementById('export-btn');
      var modal = document.getElementById('export-modal');
      var modalText = document.getElementById('export-modal-text');
      var closeBtn = document.getElementById('export-modal-close');
      var copyBtn = document.getElementById('export-copy-btn');
      var dlBtn = document.getElementById('export-download-btn');
      var clearBtn = document.getElementById('export-clear-btn');

      function buildExport() {{
        var map = loadComments();
        var lines = [];
        var title = document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : 'Report';
        var dateStr = new Date().toISOString().slice(0, 10);
        lines.push('# Comments — ' + title);
        lines.push('');
        lines.push('_Generated_: ' + dateStr);
        lines.push('_Report_: `' + reportId + '`');
        lines.push('');

        // Walk sections in DOM order so the export matches the report layout
        var seen = {{}};
        var sections = document.querySelectorAll('[data-section-id]');
        var any = false;
        sections.forEach(function(sec) {{
          var sid = sec.getAttribute('data-section-id');
          if (!sid || seen[sid]) return;
          seen[sid] = true;
          var c = (map[sid] || '').trim();
          if (!c) return;

          // Prefer the clean data-section-label attribute, fall back to DOM text
          var heading = sec.getAttribute('data-section-label') || '';
          if (!heading) {{
            var hEl = sec.querySelector('.section-title, h1, h2, h3, .column-head');
            if (hEl) heading = hEl.textContent.replace(/¶$/, '').trim();
          }}
          if (!heading) heading = sid;

          any = true;
          lines.push('## ' + heading);
          lines.push('');
          lines.push(c);
          lines.push('');
        }});

        if (!any) {{
          lines.push('_(no comments yet)_');
        }}
        return lines.join('\\n');
      }}

      if (exportBtn) {{
        exportBtn.addEventListener('click', function() {{
          modalText.value = buildExport();
          modal.hidden = false;
          modalText.focus();
          modalText.select();
        }});
      }}
      if (closeBtn) closeBtn.addEventListener('click', function() {{ modal.hidden = true; }});
      if (modal) modal.addEventListener('click', function(e) {{ if (e.target === modal) modal.hidden = true; }});

      if (copyBtn) {{
        copyBtn.addEventListener('click', function() {{
          var txt = modalText.value;
          if (navigator.clipboard) {{
            navigator.clipboard.writeText(txt).then(function() {{
              copyBtn.textContent = '✓ Copied';
              setTimeout(function() {{ copyBtn.textContent = '📋 Copy to clipboard'; }}, 1400);
            }});
          }} else {{
            modalText.select(); document.execCommand('copy');
            copyBtn.textContent = '✓ Copied';
            setTimeout(function() {{ copyBtn.textContent = '📋 Copy to clipboard'; }}, 1400);
          }}
        }});
      }}

      if (dlBtn) {{
        dlBtn.addEventListener('click', function() {{
          var blob = new Blob([modalText.value], {{ type: 'text/markdown' }});
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = reportId + '-comments.md';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }});
      }}

      if (clearBtn) {{
        clearBtn.addEventListener('click', function() {{
          if (!confirm('Clear all comments? This cannot be undone.')) return;
          localStorage.removeItem(storageKey);
          document.querySelectorAll('.comment-textarea').forEach(function(ta) {{ ta.value = ''; }});
          document.querySelectorAll('.comment-toggle').forEach(function(b) {{
            b.classList.remove('has-comment');
            b.textContent = '💬 Comment';
          }});
          // Re-collapse all widgets
          document.querySelectorAll('.comment-body').forEach(function(b) {{ b.hidden = true; }});
          document.querySelectorAll('.comment-toggle').forEach(function(b) {{ b.setAttribute('aria-expanded', 'false'); }});
          modal.hidden = true;
          updateExportCount();
        }});
      }}
    }})();
  </script>
</body>
</html>
"""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "plan"


def load_plan(source: str) -> dict:
    if source == "-":
        return json.load(sys.stdin)
    path = Path(source).expanduser()
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        help='Path to plan/report JSON file, or "-" to read JSON from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to write the HTML file. Default: system temp dir with a slug from the title.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the HTML in a browser; just write it and print the path.",
    )
    args = parser.parse_args()

    try:
        plan = load_plan(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not load JSON: {exc}", file=sys.stderr)
        return 1

    html_content = render_html(plan)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        slug = slugify(plan.get("title", "plan"))
        output_path = Path(tempfile.gettempdir()) / f"plan-visualizer-{slug}.html"

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
