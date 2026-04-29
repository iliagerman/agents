# Comment Widget — Shared Behavioral Spec

Both `plan-visualizer` and `git-visualizer` use the same comment widget system. This file is the single source of truth for its behavior. When generating or modifying either skill's renderer, always follow this spec exactly.

## Per-section comment boxes

Every commentable element (plan section, report section, or changed file) gets a collapsible comment textarea. The widget is injected by the Python renderer when comments are enabled.

### Triggering comments

- **`plan-visualizer`**: set `"comments_enabled": true` in the JSON input.
- **`git-visualizer`**: pass `--comments` on the command line.

### HTML structure

```html
<div class="comment-widget" data-section-id="<slug>">
  <button type="button" class="comment-toggle" aria-expanded="false">💬 Comment</button>
  <div class="comment-body" hidden>
    <textarea class="comment-textarea" data-section-id="<slug>"
      placeholder="Type your question or comment…"></textarea>
    <div class="comment-meta">
      <span class="comment-saved-indicator" aria-live="polite"></span>
    </div>
  </div>
</div>
```

The widget attaches to the nearest containing section element, which must have matching `data-section-id` and `data-section-label` attributes so the export can produce clean headings.

## Behavioral rules (must match exactly)

1. **Always collapsed by default.** When the page loads, every `comment-body` starts with `hidden`. Never auto-open, even when a saved comment exists.
2. **Click to open / click again to close.** Clicking the toggle button flips `body.hidden` and updates `aria-expanded`. Opening auto-focuses the textarea.
3. **Button label changes.** When a non-empty comment is saved, the button text becomes `"💬 Comment (saved)"` and gets the `.has-comment` CSS class (colored border). It reverts to `"💬 Comment"` if the user clears the text.
4. **Autosave with 350 ms debounce.** Every keystroke resets a 350 ms timer; on fire, the current value is written to `localStorage`. A brief `"saving…"` → `"saved"` indicator appears and fades.
5. **localStorage persistence, keyed by report ID.**
   - `plan-visualizer`: key is `planviz:<report_id>`
   - `git-visualizer`: key is `gitviz:<report_id>` (slugified title)
   Comments survive page reloads but the widget always starts collapsed.
6. **Widgets are only rendered when comments are enabled.** Without the flag, no widget HTML appears and no JS runs.

## Export format

The floating `📋 Export comments` button (bottom-right) collects all non-empty comments into Markdown:

```markdown
# Comments — <report title>

_Generated_: 2026-04-29
_Report_: `<report_id>`

## Section or file heading
<user's comment text>

## Another section
<another comment>
```

Sections appear in DOM order. Headings come from the `data-section-label` attribute on the element that carries `data-section-id`. This attribute must contain **clean plain text** — no HTML tags, no marker symbols (`→ ◇ ◈ ⇋ ⊘ ⚠ ✕ ⊞`).

### `data-section-label` rules

- For plan-visualizer **named sections** (`sections` array): use the raw `title` string from the JSON (before `render_inline()` processing).
- For plan-visualizer **BEFORE/AFTER columns**: use `"Before"` and `"After"` literally.
- For plan-visualizer **auto-generated sections** (Key changes, Tradeoffs, etc.): `wrap_section_with_comment()` strips HTML tags then strips leading marker chars via `.lstrip("→◇◈⇋⊘⚠✕⊞ ")`.
- For git-visualizer **per-file blocks**: use `fc.path` (the file's path string, e.g. `src/app/auth.ts`).
- For git-visualizer **commits section**: use `"Commits"` literally.

### Export actions

- **Copy to clipboard** — copies the Markdown string.
- **Download .md** — saves as `<report_id>-comments.md`.
- **Clear all** — wipes `localStorage` for this report, clears all textareas, re-collapses all widgets, closes the modal.

## Adding comments to a new visualizer

1. Add a `_COMMENTS_ENABLED` module-level bool, set it in `render_html()` before any rendering calls.
2. Compute `comment_css`, `floating_button_html`, and `comment_script` as **plain Python strings** (not f-strings that go through `TEMPLATE.format()`). This avoids having to double every `{` and `}` inside the CSS/JS.
3. Add `{comment_css}`, `{floating_button}`, and `{comment_script}` slots to the TEMPLATE string.
4. Set `data-comments-enabled` and `data-report-id` on `<body>`.
5. Add `data-section-id` and `data-section-label` to every commentable element.
6. Inject the comment widget HTML inside each commentable element (after its main content).
