---
name: plan-visualizer
description: >-
  Turns a Claude Code markdown plan, audit/review report, or investigation
  document into a visual HTML page. Use when asked to "visualize a plan",
  "show me the plan visually", "make an infographic of this plan", "render
  this report", or wants a BEFORE/AFTER architecture view. Supports plan mode
  (BEFORE/AFTER columns + badges + file manifest) and report mode (free-form
  sections with prose, bullets, tables, callouts, Mermaid diagrams). Both
  modes support per-section comment boxes with an "Export comments" button.
metadata:
  {
    "ilia":
      {
        "emoji": "📊",
        "requires": { "bins": ["python3"], "env": [] },
      },
  }
---

# Plan / Report Visualizer

Use this skill to turn a markdown plan, audit, review, or investigation document into a single-page HTML page. The point is to make intent and findings visible at a glance so the user can review (and comment) instead of skimming a 200-line markdown dump.

## When to use

Trigger this any time the user wants a markdown document rendered visually for review. Common phrasings:

**Plan mode (architectural changes / proposals):**
- "visualize this plan"
- "show me the plan as a picture / diagram / infographic"
- "make the plan easier to review"
- "BEFORE/AFTER view of what you'd change"
- "render this plan so I can see it"

**Report mode (audits, reviews, investigations):**
- "make this audit/review/investigation easier to read"
- "render this report visually"
- "I want to leave comments on each section"
- "give me a report I can comment on and export questions back"
- "convert this long markdown into something I can scan"

If the user just approved or rejected a plan without review and is complaining about rubber-stamping, that's also a signal to offer this skill.

## Two modes — pick one (or both)

The script supports two top-level shapes:

1. **Plan mode** — BEFORE/AFTER columns + ADDED/CHANGED/REMOVED badges + file manifest. Best for "here's what I'd change" proposals. Use the `before` / `after` / `file_manifest` fields.
2. **Report mode** — free-form sections, each with a type (`prose`, `bullets`, `table`, `diagram`, `callout`, `cards`). Best for audits, reviews, investigations, post-incident write-ups. Use the `sections` array.

You can combine them — a JSON with both `before`/`after` AND `sections` will render both. But typically one mode dominates per document.

## Comments + export Q&A

If you set `comments_enabled: true`, every rendered section gets a small "💬 Comment" toggle button.

### Comment widget behavior — must match this exactly

- **Always collapsed by default.** When the page loads, every comment textarea is hidden, regardless of whether the user already wrote a comment in a previous session.
- **Click the button to open** the textarea (auto-focuses it for typing).
- **Click the button again to close** the textarea (the value stays — it's just hidden).
- **The button label changes to "💬 Comment (saved)"** when there's a non-empty comment, and gets a `.has-comment` CSS class for the colored border. It reverts to plain "💬 Comment" if the user clears the text.
- **Comments persist in `localStorage`** keyed by `report_id`. They survive page reloads but the widget always starts collapsed.
- The textarea autosaves with a 350ms debounce. A "saved" indicator briefly appears.

This collapse-by-default behavior is intentional — it keeps the page scannable and prevents the report from looking cluttered when the user already left comments. Do not change it without an explicit ask from the user.

### Export bar

A floating "📋 Export comments" button at the bottom-right collects every non-empty comment into a Markdown document. Three actions:

- **Copy to clipboard** — copies the export text. Use this when pasting back into a chat.
- **Download .md** — saves the export as `<report_id>-comments.md`.
- **Clear all** — wipes localStorage for this report and re-collapses every widget.

The export walks sections in DOM order, picks each section's heading, and produces:

```markdown
# Comments — <report title>

_Generated_: 2026-04-28
_Report_: `<report_id>`

## Section heading
<user's comment text>

## Another section
<another comment>
```

Default is `comments_enabled: false` (silent — no comment widgets, no export bar).

## The core flow

Your job is to turn a loose markdown plan into a structured JSON object matching the schema below, then hand it to the bundled Python script. The script does the HTML rendering and opens the file in the browser — don't try to write HTML yourself.

1. **Understand the plan.** Read the plan text (either from the current conversation, from a file the user points at, or from clipboard content the user pastes). If something is missing, pick reasonable defaults rather than refusing — an imperfect visualization is still useful.

2. **Extract structured data into JSON.** Map the plan onto the schema below. Don't force sections that don't exist — omit them or leave their arrays empty. Do not invent content that isn't in the plan.

3. **Write the JSON to a temp file**, e.g. `/tmp/plan-visualizer-input.json`.

4. **Run the generator script** (see "Running the script"). It writes an HTML file and opens it via `file://` in the default browser. Print the resulting `file://` URL back to the user so they have a persistent link.

5. **Tell the user the file location** and offer to iterate if the extraction missed something.

## JSON schema

```json
{
  "title": "Short title of the plan or report",
  "subtitle": "1-2 sentence description. Supports `backtick code` spans.",
  "profile": "STANDARD PROFILE",
  "file_count": 8,
  "step_count": 5,
  "generated": "2026-04-17",

  "comments_enabled": false,
  "report_id": "ezbob-audit-2026-04-28",

  "before": [
    {
      "title": "Component or File Name",
      "status": "CHANGED",
      "details": [
        "Free-form bullet describing the current state",
        "Another bullet. `file/paths` and `code` go in backticks."
      ]
    },
    { "title": "section label", "kind": "label" }
  ],

  "after": [
    {
      "title": "Component or File Name",
      "status": "ADDED",
      "details": ["..."]
    }
  ],

  "file_manifest": [
    { "path": "src/services/auth.ts", "action": "modify", "description": "Add token refresh logic" },
    { "path": "src/services/session.ts", "action": "add", "description": "New session management service" },
    { "path": "src/utils/legacy-auth.ts", "action": "remove", "description": "Replaced by auth.ts" }
  ],

  "diagrams": [
    {
      "title": "Authentication Flow — After",
      "description": "How the new token refresh cycle works.",
      "mermaid": "graph LR\n  A[Client] -->|request| B[Auth Service]\n  B -->|validate| C[Token Store]\n  C -->|expired| D[Refresh]\n  D --> B"
    }
  ],

  "sections": [
    {
      "id": "tldr",
      "title": "TL;DR",
      "type": "prose",
      "body": "1–2 paragraphs of plain text. Supports `code` and **bold**.\n\nUse blank lines for paragraph breaks."
    },
    {
      "id": "findings",
      "title": "Top findings",
      "type": "bullets",
      "items": ["First finding with `code`", "Second finding"]
    },
    {
      "id": "comparison",
      "title": "Claim vs reality",
      "type": "table",
      "columns": ["Claim", "Status", "Notes"],
      "rows": [
        ["Repo X exists", "✅", "On disk"],
        ["Repo Y exists", "❌", "Missing"]
      ]
    },
    {
      "id": "flow",
      "title": "End-to-end flow",
      "type": "diagram",
      "description": "How a PR becomes a deploy.",
      "mermaid": "graph LR\n  A --> B --> C"
    },
    {
      "id": "warning",
      "title": "Single point of failure",
      "type": "callout",
      "variant": "warn",
      "body": "GITOPS_PAT is a manually-rotated classic PAT bound to one machine user."
    },
    {
      "id": "risks-grid",
      "title": "Risk dashboard",
      "type": "cards",
      "cards": [
        { "title": "Risk A", "tone": "high", "body": "..." },
        { "title": "Risk B", "tone": "medium", "body": "..." }
      ]
    }
  ],

  "key_changes":   ["One-line summary of a major change", "..."],

  "tradeoffs": [
    {
      "decision": "Use JWT instead of opaque tokens",
      "pros": ["Stateless verification", "No DB lookup per request"],
      "cons": ["Cannot revoke individual tokens", "Larger payload size"]
    }
  ],

  "key_decisions": ["Design choice and why it was made", "..."],

  "alternatives": [
    {
      "title": "Session-based auth with Redis",
      "description": "Store sessions server-side in Redis with a session cookie.",
      "why_rejected": "Adds Redis as an infrastructure dependency; JWT is sufficient for our scale."
    }
  ],

  "risks": [
    { "description": "What could go wrong", "mitigation": "how we plan to handle it" },
    "Risk without a mitigation (plain string is also valid)"
  ],
  "out_of_scope":  ["Things explicitly NOT done in this plan", "..."]
}
```

### Section types (report mode)

The `sections` array is rendered in order. Each entry is one of:

- **`prose`** — `{ id, title, type: "prose", body: "Markdown-ish text..." }`. Body is escaped, then `\`code\`` and `**bold**` are processed, then blank lines split into paragraphs.
- **`bullets`** — `{ id, title, type: "bullets", items: ["...", "..."] }`. Same inline rendering as prose.
- **`table`** — `{ id, title, type: "table", columns: [...], rows: [[...], [...]] }`. Each row is an array of cells matching `columns` length. Cells render with inline `code` and `**bold**`.
- **`diagram`** — `{ id, title, type: "diagram", description?: "...", mermaid: "..." }`. Same as the existing `diagrams` field but inline within a section.
- **`callout`** — `{ id, title, type: "callout", variant: "info|good|warn|error", body: "..." }`. A tinted box for emphasis.
- **`cards`** — `{ id, title, type: "cards", cards: [{ title, body, tone?: "good|info|warn|high|critical" }] }`. Grid of small cards, useful for risk dashboards or finding tiles.
- **`raw_html`** — `{ id, title, type: "raw_html", html: "..." }`. Escape hatch. Use sparingly.

### Field notes

- **`title` / `subtitle`**: required-ish. Use the plan's goal statement. If the plan has a long summary, condense it.
- **`profile`**: optional short pill in the top-right corner (e.g. `STANDARD PROFILE`, `QUICK PLAN`, `REFACTOR`). Omit for a generic label.
- **`file_count` / `step_count`**: optional. Count files touched and numbered steps in the plan. Omit either if the plan doesn't have that concept.
- **`generated`**: optional ISO date. Defaults to today.
- **`before` / `after`**: arrays of items. Two item kinds:
  - **Card** (default): `{ "title": "...", "status": "ADDED|CHANGED|REMOVED|UNCHANGED", "details": [...] }`. `status` is case-insensitive; if omitted, the card renders without a badge.
  - **Label**: `{ "title": "section marker", "kind": "label" }`. Use these sparingly to group cards (e.g. "plan link protocol", "template source").
  - Keep the `before` and `after` arrays roughly symmetric when possible — label-for-label, card-for-card — so they read side by side.
- **`details`**: short bullet points. Prefer 1 line each. Use backticks for paths, identifiers, commands.
- **`file_manifest`**: array of `{path, action, description}`. `action` is one of `add`, `modify`, or `remove` (case-insensitive). Renders as a compact table with colored badges. This is the file-level "what changes where" view — complementary to the component-level BEFORE/AFTER panels. Include every file the plan touches.
- **`diagrams`**: array of `{title, description?, mermaid}`. `mermaid` is a Mermaid syntax string (flowcharts, sequence diagrams, component diagrams). The browser renders these using Mermaid.js loaded from CDN — the Python script itself still needs no network. If the browser is offline, raw Mermaid text shows as a code block fallback. Use diagrams when the plan involves data flows, state machines, request lifecycles, or component relationships that benefit from a visual. Don't force diagrams for simple plans.
- **`tradeoffs`**: array of `{decision, pros: [...], cons: [...]}`. Distinct from `key_decisions` — decisions say "we chose X because Y", while tradeoffs show the tension: "X gives us A but costs B". Include when the plan makes a non-obvious architectural choice with real downsides.
- **`alternatives`**: array of `{title, description, why_rejected}`. Approaches that were considered (or should have been considered) and explicitly not taken. This surfaces the design space so the reviewer can push back on the chosen path. If the plan doesn't mention alternatives, think about what a senior engineer would ask "why not X?" about — include those.
- **`risks`**: can be either a string or `{description, mitigation}`. Prefer the object form; it renders the mitigation in italics next to the risk.
- **`out_of_scope`**: explicit non-goals. Useful signal; include it if the plan mentions any exclusions.

### If the plan doesn't cleanly split into BEFORE/AFTER

Some plans aren't architectural diffs — they're "add this new feature" plans. In that case:

- Put current-state components (or "(none)") in `before`.
- Put new/changed components in `after`.
- Rely on the `key_changes` section to carry the narrative.

Don't force it. A visualization with only an `after` column plus strong `key_changes` / `key_decisions` / `risks` sections is still a big upgrade over prose.

## Running the script

The bundled script lives at `scripts/generate_visualization.py` inside this skill directory.

```bash
python3 "<skill-dir>/scripts/generate_visualization.py" /tmp/plan-visualizer-input.json
```

Flags:

- `-o <path>` / `--output <path>` — explicit output path. Default is a slug-named file in the OS temp dir.
- `--no-open` — write the HTML but don't open the browser (useful in headless environments).
- Pass `-` as the input argument to read JSON from stdin.

The script prints the final `file://...` URL to stdout on success. Always capture and surface this URL to the user so they can re-open the file later.

### Finding the skill directory

If you don't already know the absolute path to this skill, it's typically under the user's Claude skills directory. A robust one-liner to locate it:

```bash
SKILL_DIR="$HOME/.claude/skills/plan-visualizer"
python3 "$SKILL_DIR/scripts/generate_visualization.py" /tmp/plan-visualizer-input.json
```

If the skill was installed elsewhere (e.g. a project-local `skills/plan-visualizer`), prefer that path.

## Example end-to-end

The user in plan mode has just produced a 150-line plan about packaging an internal agent as a plugin. They say "visualize it so I can review it". You:

1. Read the plan from context.
2. Build a JSON object matching the schema. An annotated example is bundled at `assets/example.json` — use it as a reference for shape and tone (do **not** echo its content into the user's plan).
3. Write the JSON to `/tmp/plan-visualizer-input.json`.
4. Run `python3 ~/.claude/skills/plan-visualizer/scripts/generate_visualization.py /tmp/plan-visualizer-input.json`.
5. Reply with: "Opened the visualization at `file:///tmp/plan-visualizer-<slug>.html`. BEFORE column shows the 4 components touched, AFTER shows what they become. Want me to adjust any of the BEFORE/AFTER items?"

## What not to do

- **Don't write raw HTML yourself.** All styling lives in the script template so output stays consistent. If the visual needs a change, change the template — not the caller.
- **Don't invent content.** If the plan doesn't mention risks, leave `risks` empty rather than making them up. Fabricated risks erode trust in the tool.
- **Don't use `open <path>` or any macOS-specific command.** The script opens the file via Python's `webbrowser` module with a `file://` URL, which is the cross-platform path.
- **Don't try to parse the markdown in the script.** Claude (you) does the extraction; the script only renders. Markdown plans are too loose for reliable programmatic parsing.
- **Don't dump the full plan into a single card.** Break it into meaningful components in BEFORE/AFTER — that's the whole point of the visualization.
