#!/usr/bin/env python3
"""Generate a visual HTML infographic from a structured plan.

Reads a JSON description of a plan and produces a standalone HTML file showing
BEFORE/AFTER architecture panels, color-coded diffs, key changes, decisions,
risks, and out-of-scope items. Opens the file in the default browser via the
`file://` protocol so it works on macOS, Linux, and Windows.

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
    """Escape text and render `code` spans in monospace."""
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r'<code class="inline">\1</code>', escaped)


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
    return (
        '<section class="section">'
        '<h2 class="section-title"><span class="marker sym-file">⊞</span>File manifest</h2>'
        '<table class="file-manifest">'
        '<thead><tr><th>Action</th><th>Path</th><th>Description</th></tr></thead>'
        f'<tbody>{table_rows}</tbody>'
        '</table>'
        '</section>'
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
        # Mermaid div with a <pre> fallback for offline
        parts.append(
            f'<div class="diagram-block">'
            f'<h3 class="diagram-title">{title}</h3>'
            f'{desc_html}'
            f'<div class="mermaid">{html.escape(mermaid_src)}</div>'
            f'<pre class="mermaid-fallback">{html.escape(mermaid_src)}</pre>'
            f'</div>'
        )
    blocks = "\n".join(parts)
    return (
        '<section class="section">'
        '<h2 class="section-title"><span class="marker sym-diagram">◈</span>Diagrams</h2>'
        f'{blocks}'
        '</section>'
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
    return (
        '<section class="section">'
        '<h2 class="section-title"><span class="marker sym-tradeoff">⇋</span>Tradeoffs</h2>'
        f'{blocks}'
        '</section>'
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
    return (
        '<section class="section">'
        '<h2 class="section-title"><span class="marker sym-alt">⊘</span>Alternatives considered</h2>'
        f'{blocks}'
        '</section>'
    )


def render_html(plan: dict) -> str:
    title = html.escape(plan.get("title", "Plan Visualization"))
    subtitle = render_inline(plan.get("subtitle", ""))
    profile = html.escape(plan.get("profile") or "PLAN")
    file_count = plan.get("file_count")
    step_count = plan.get("step_count")
    generated = html.escape(plan.get("generated") or date.today().isoformat())

    summary_parts = []
    if file_count is not None:
        label = "FILE" if file_count == 1 else "FILES"
        summary_parts.append(f"{file_count} {label}")
    if step_count is not None:
        label = "STEP" if step_count == 1 else "STEPS"
        summary_parts.append(f"{step_count} {label}")
    summary_line = html.escape(" · ".join(summary_parts)) if summary_parts else ""

    before_html = render_column(plan.get("before", []))
    after_html = render_column(plan.get("after", []))

    file_manifest_html = render_file_manifest(plan.get("file_manifest", []))
    diagrams_html = render_diagrams(plan.get("diagrams", []))

    key_changes_html = render_bullet_list(
        plan.get("key_changes", []), "→", "sym-arrow"
    )
    tradeoffs_html = render_tradeoffs(plan.get("tradeoffs", []))
    key_decisions_html = render_bullet_list(
        plan.get("key_decisions", []), "◇", "sym-diamond"
    )
    alternatives_html = render_alternatives(plan.get("alternatives", []))
    risks_html = render_bullet_list(plan.get("risks", []), "⚠", "sym-warn")
    out_of_scope_html = render_bullet_list(
        plan.get("out_of_scope", []), "✕", "sym-x"
    )

    return TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        profile=profile,
        summary_line=summary_line,
        generated=generated,
        before=before_html,
        after=after_html,
        file_manifest=file_manifest_html,
        diagrams=diagrams_html,
        key_changes=key_changes_html,
        tradeoffs=tradeoffs_html,
        key_decisions=key_decisions_html,
        alternatives=alternatives_html,
        risks=risks_html,
        out_of_scope=out_of_scope_html,
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
    --border: #222b39;
    --border-strong: #2f3a4c;
    --text: #e6ebf2;
    --muted: #8893a5;
    --dim: #5b6778;
    --added: #3fb950;
    --added-bg: rgba(63,185,80,0.14);
    --changed: #f5b041;
    --changed-bg: rgba(245,176,65,0.14);
    --removed: #f47272;
    --removed-bg: rgba(244,114,114,0.14);
    --unchanged: #8893a5;
    --unchanged-bg: rgba(136,147,165,0.14);
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  html, body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.5;
    margin: 0;
    padding: 0;
  }}
  .page {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 32px 48px;
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
    font-size: 20px;
    font-weight: 600;
    letter-spacing: -0.01em;
  }}
  .top-left .subtitle {{
    color: var(--muted);
    font-size: 13px;
    max-width: 780px;
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
  .summary-line {{
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .gen-line {{
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}
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
  .legend .legend-label {{
    color: var(--dim);
  }}
  .legend .chip {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }}
  .chip .dot {{
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
  }}
  .dot.added {{ background: var(--added); }}
  .dot.changed {{ background: var(--changed); }}
  .dot.removed {{ background: var(--removed); }}
  .dot.unchanged {{ background: var(--unchanged); }}

  .columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 28px;
  }}
  .column {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px 18px 8px;
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
  .badge-added    {{ color: var(--added);    background: var(--added-bg);    border-color: rgba(63,185,80,0.35); }}
  .badge-changed  {{ color: var(--changed);  background: var(--changed-bg);  border-color: rgba(245,176,65,0.35); }}
  .badge-removed  {{ color: var(--removed);  background: var(--removed-bg);  border-color: rgba(244,114,114,0.35); }}
  .badge-unchanged{{ color: var(--unchanged);background: var(--unchanged-bg);border-color: rgba(136,147,165,0.35); }}

  .card-details {{
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 12.5px;
    color: #c3cbd8;
  }}
  .card-details li {{
    padding: 2px 0 2px 14px;
    position: relative;
  }}
  .card-details li::before {{
    content: "·";
    color: var(--dim);
    position: absolute;
    left: 4px;
    font-weight: 700;
  }}
  code.inline {{
    font-family: var(--mono);
    font-size: 11.5px;
    color: #c5e0ff;
    background: rgba(110,168,254,0.08);
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid rgba(110,168,254,0.15);
  }}

  .section {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    margin-top: 16px;
  }}
  .section-title {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 12px;
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .section-title .marker {{
    font-size: 14px;
    line-height: 1;
  }}
  .bullet-row {{
    display: flex;
    gap: 10px;
    padding: 4px 0;
    font-size: 13px;
    color: #d0d7e3;
  }}
  .bullet-symbol {{
    flex-shrink: 0;
    width: 16px;
    text-align: center;
    font-weight: 700;
  }}
  .sym-arrow {{ color: var(--added); }}
  .sym-diamond {{ color: #6ea8fe; }}
  .sym-warn {{ color: var(--changed); }}
  .sym-x {{ color: var(--removed); }}
  .bullet-text {{
    flex: 1;
  }}
  .mitigation {{
    color: var(--muted);
    font-style: italic;
  }}
  .empty-row {{
    color: var(--dim);
    font-size: 12px;
    padding: 4px 0;
  }}

  /* File manifest table */
  .file-manifest {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .file-manifest th {{
    text-align: left;
    color: var(--dim);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
  }}
  .file-manifest td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  .file-manifest tr:last-child td {{
    border-bottom: none;
  }}
  .fm-desc {{
    color: var(--muted);
    font-size: 12.5px;
  }}
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
  .diagram-title {{
    font-size: 13px;
    font-weight: 600;
    margin: 0 0 6px;
    color: var(--text);
  }}
  .diagram-desc {{
    font-size: 12.5px;
    color: var(--muted);
    margin: 0 0 12px;
  }}
  .mermaid {{
    text-align: center;
    background: transparent;
  }}
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
  .tradeoff-decision {{
    font-weight: 600;
    font-size: 13px;
    margin-bottom: 10px;
    color: var(--text);
  }}
  .tradeoff-columns {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}
  .tradeoff-col-head {{
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-weight: 600;
  }}
  .pro-head {{ color: var(--added); }}
  .con-head {{ color: var(--removed); }}
  .tradeoff-list {{
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 12.5px;
  }}
  .tradeoff-list li {{
    padding: 2px 0 2px 14px;
    position: relative;
    color: #c3cbd8;
  }}
  .tradeoff-list li::before {{
    content: "·";
    color: var(--dim);
    position: absolute;
    left: 4px;
    font-weight: 700;
  }}
  .pro-item {{ color: rgba(63,185,80,0.85); }}
  .con-item {{ color: rgba(244,114,114,0.85); }}

  /* Alternatives */
  .sym-alt {{ color: var(--muted); }}
  .alt-card {{
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .alt-title {{
    font-weight: 600;
    font-size: 13px;
    color: var(--text);
    margin-bottom: 4px;
  }}
  .alt-desc {{
    font-size: 12.5px;
    color: #c3cbd8;
    margin-bottom: 6px;
  }}
  .alt-rejected {{
    font-size: 12px;
    color: var(--muted);
    font-style: italic;
  }}
  .alt-rejected-label {{
    color: var(--removed);
    font-style: normal;
    font-weight: 600;
  }}

  @media (max-width: 820px) {{
    .columns {{ grid-template-columns: 1fr; }}
    .top {{ flex-direction: column; align-items: flex-start; }}
    .top-right {{ align-items: flex-start; text-align: left; }}
  }}
</style>
</head>
<body>
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

    <div class="columns">
      <section class="column">
        <div class="column-head">Before</div>
        {before}
      </section>
      <section class="column">
        <div class="column-head">After</div>
        {after}
      </section>
    </div>

    {file_manifest}

    {diagrams}

    <section class="section">
      <h2 class="section-title"><span class="marker sym-arrow">→</span>Key changes</h2>
      {key_changes}
    </section>

    {tradeoffs}

    <section class="section">
      <h2 class="section-title"><span class="marker sym-diamond">◇</span>Key decisions</h2>
      {key_decisions}
    </section>

    {alternatives}

    <section class="section">
      <h2 class="section-title"><span class="marker sym-warn">⚠</span>Risks</h2>
      {risks}
    </section>

    <section class="section">
      <h2 class="section-title"><span class="marker sym-x">✕</span>Out of scope</h2>
      {out_of_scope}
    </section>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
      var mermaidBlocks = document.querySelectorAll('.mermaid');
      if (mermaidBlocks.length === 0) return;
      try {{
        mermaid.initialize({{
          startOnLoad: true,
          theme: 'dark',
          themeVariables: {{
            primaryColor: '#182030',
            primaryTextColor: '#e6ebf2',
            primaryBorderColor: '#2f3a4c',
            lineColor: '#5b6778',
            secondaryColor: '#131922',
            tertiaryColor: '#0b0f14',
            fontFamily: '-apple-system, BlinkMacSystemFont, Inter, Segoe UI, Roboto, sans-serif',
            fontSize: '13px'
          }}
        }});
      }} catch (e) {{
        // Mermaid failed to load (offline?) — show fallback code blocks
        mermaidBlocks.forEach(function(el) {{
          el.style.display = 'none';
          var fallback = el.nextElementSibling;
          if (fallback && fallback.classList.contains('mermaid-fallback')) {{
            fallback.style.display = 'block';
          }}
        }});
      }}
    }});
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
        help='Path to plan JSON file, or "-" to read JSON from stdin.',
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to write the HTML file. Default: system temp dir with a slug from the plan title.",
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
        print(f"error: could not load plan JSON: {exc}", file=sys.stderr)
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
