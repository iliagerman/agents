---
name: cmux
description: Control the cmux terminal/browser multiplexer from the CLI. Use whenever the user asks to open a directory in cmux, create/move/focus windows, workspaces, panes, surfaces (terminal or browser tabs), send keys or text to a pane, drive the embedded browser (navigate, click, fill, snapshot, screenshot), inspect the current cmux topology, set status/progress/notifications, or change cmux/Ghostty settings. Triggers on phrases like "in cmux", "open this in cmux", "new cmux workspace", "cmux split", "cmux browser", "cmux send", or any cmux subcommand. The cmux binary is at /Applications/cmux.app/Contents/Resources/bin/cmux and is already on PATH.
---

# cmux CLI

Use this skill to drive cmux without re-reading `cmux --help` each session. cmux is a macOS terminal+browser multiplexer with a Unix-socket CLI. The binary is `cmux` (on PATH).

## Core mental model

| Concept | What it is |
|---|---|
| **window** | Top-level macOS cmux window. |
| **workspace** | Tab-like group of panes inside a window. |
| **pane** | A split container inside a workspace. |
| **surface** | A single tab inside a pane — either a `terminal` or a `browser`. |
| **panel** | UI element holding a surface (the thing you focus). |

Handles use short refs by default: `window:1`, `workspace:2`, `pane:3`, `surface:4` (`tab:N` is also accepted by `tab-action` / `rename-tab`). UUIDs are accepted as inputs; ask for them in output via `--id-format uuids|both`.

## Environment variables (auto-set inside cmux terminals)

- `CMUX_WORKSPACE_ID` — default `--workspace` for every command.
- `CMUX_SURFACE_ID` — default `--surface` for every command.
- `CMUX_TAB_ID` — default `--tab` for `tab-action`/`rename-tab`.
- `CMUX_SOCKET_PATH` — override the socket (default `~/Library/Application Support/cmux/cmux.sock`).

If you're driving cmux from inside a cmux terminal, these are already set — most commands "just work" without explicit `--workspace`/`--surface`.

## First, orient

```bash
cmux identify --json     # full topology: focused + caller window/workspace/pane/surface
cmux tree --all          # tree of all windows/workspaces/panes/surfaces
cmux list-windows
cmux list-workspaces
cmux list-panes
cmux list-pane-surfaces --pane pane:1
```

Use `cmux identify --json` whenever you need to anchor an action to the caller, or check what's actually focused before sending input.

## Opening a directory

```bash
cmux <path>              # opens a directory in a new workspace (launches cmux if needed)
cmux ~/Work/foo          # → new workspace cwd'd to that path
```

## Windows

```bash
cmux list-windows
cmux current-window
cmux new-window
cmux focus-window --window window:2
cmux close-window --window window:2
```

## Workspaces

```bash
cmux list-workspaces
cmux current-workspace
cmux new-workspace --name "build" --cwd ~/Work/repo --command "just dev"
cmux select-workspace --workspace workspace:4
cmux close-workspace --workspace workspace:4
cmux rename-workspace --workspace workspace:4 "new title"
cmux reorder-workspace --workspace workspace:4 --before workspace:2
cmux move-workspace-to-window --workspace workspace:4 --window window:1
```

`new-workspace` flags worth knowing: `--name`, `--description`, `--cwd`, `--command`, `--layout <json>`, `--window`, `--focus true|false`.

## Panes (splits)

```bash
cmux list-panes
cmux new-split right --panel pane:1        # left|right|up|down
cmux focus-pane --pane pane:2
cmux resize-pane --pane pane:2 -R --amount 10   # -L/-R/-U/-D
cmux swap-pane --pane pane:2 --target-pane pane:3
```

## Surfaces (tabs inside a pane)

```bash
cmux list-pane-surfaces --pane pane:1
cmux new-surface --type terminal --pane pane:1
cmux new-surface --type browser  --pane pane:1 --url https://example.com
cmux close-surface --surface surface:7
cmux move-surface  --surface surface:7 --pane pane:2 --focus true
cmux split-off     --surface surface:7 right          # promote a surface into its own split
cmux reorder-surface --surface surface:7 --before surface:3
cmux rename-tab    --surface surface:7 "API logs"
cmux tab-action    --action close --tab tab:3
```

Surface identity is stable across move/reorder/split-off. Layout commands are focus-neutral by default — pass `--focus true` only when you want the moved/created surface to become selected.

## Sending input to a surface

```bash
cmux send <text>                                  # to current surface
cmux send --surface surface:7 "ls -la\n"
cmux send-key --surface surface:7 Enter
cmux send-key Ctrl+c
cmux send-panel --panel pane:1 "echo hi\n"        # target by panel
```

`send` types literal text (include `\n` for Enter). `send-key` takes a key name (`Enter`, `Escape`, `Ctrl+c`, `Tab`, etc.).

## Reading what's on screen

```bash
cmux read-screen                                  # current surface
cmux read-screen --surface surface:7 --scrollback --lines 200
cmux capture-pane --surface surface:7 --scrollback --lines 500   # tmux-compat alias
```

## Notifications, status, progress

```bash
cmux notify --title "Build done" --body "Tests passed" --surface surface:7
cmux set-status build "running" --icon hammer --color "#22c55e"
cmux clear-status build
cmux set-progress 0.42 --label "indexing"
cmux clear-progress
cmux trigger-flash --surface surface:7            # subtle visual cue
```

## Browser automation (cmux's embedded browser surfaces)

Open and operate browser surfaces with `cmux browser ...`. Snapshot to get fresh element refs (e.g. `e1`, `e2`), then act using those refs.

```bash
cmux --json browser open https://example.com       # → returns surface:N
cmux browser surface:7 get url
cmux browser surface:7 wait --load-state complete --timeout-ms 15000
cmux browser surface:7 snapshot --interactive      # produces e1, e2, ... refs

cmux browser surface:7 fill e1 "jane@example.com"
cmux browser surface:7 type e1 "extra text"
cmux --json browser surface:7 click e3 --snapshot-after
cmux browser surface:7 press Enter --snapshot-after
cmux browser surface:7 select e4 "option-value"

cmux browser surface:7 screenshot --out /tmp/out.png
cmux browser surface:7 get text body
cmux browser surface:7 get html body
cmux browser surface:7 get value e1
cmux browser surface:7 is visible e2

cmux browser surface:7 wait --selector "#ready"   --timeout-ms 10000
cmux browser surface:7 wait --text     "Success"  --timeout-ms 10000
cmux browser surface:7 wait --url-contains "/dashboard" --timeout-ms 15000

cmux browser surface:7 back
cmux browser surface:7 forward
cmux browser surface:7 reload
cmux browser surface:7 goto https://example.com/page2 --snapshot-after

cmux browser surface:7 tab new https://example.com
cmux browser surface:7 tab list
cmux browser surface:7 tab close 2

cmux browser surface:7 cookies get
cmux browser surface:7 storage local get
cmux browser surface:7 state save /tmp/session.json
cmux browser surface:7 state load /tmp/session.json
```

### Stable browser loop

```
get url  →  wait  →  snapshot --interactive  →  act with ref  →  --snapshot-after
```

Re-snapshot after every DOM/navigation change — refs (`e1`, `e2`, …) are only valid for the snapshot they came from. If `snapshot --interactive` returns `js_error`, fall back to `get text body` / `get html body` (WKWebView limit).

### Browser disable/enable

```bash
cmux browser-status
cmux disable-browser
cmux enable-browser
```

## Markdown viewer

```bash
cmux markdown open README.md            # opens in a live-reloading viewer panel
cmux markdown open docs/spec.md --focus true
```

## Right sidebar

```bash
cmux right-sidebar toggle
cmux right-sidebar show
cmux right-sidebar files       # files | find | vault | sessions | feed | dock
cmux right-sidebar mode
```

## Settings (cmux.json + Ghostty)

cmux-owned settings live in `~/.config/cmux/cmux.json`. Terminal rendering (font, theme, cursor, scrollback, `background-opacity`, `background-blur`) belongs in Ghostty config at `~/.config/ghostty/config`.

Before editing `cmux.json`, copy it to a timestamped `.bak` next to it.

```bash
cmux docs settings                # docs URL, schema URL, paths, reload command
cmux settings                     # open settings UI
cmux settings path                # print active cmux.json path
cmux settings cmux-json           # open the JSON in editor
cmux settings shortcuts           # show shortcuts in UI
cmux config doctor                # validate config + check engine
cmux config validate
cmux reload-config                # reloads BOTH cmux.json AND Ghostty config in place
```

Useful curl-able resources (printed by `cmux docs <topic>`):

```bash
curl -fsSL https://raw.githubusercontent.com/manaflow-ai/cmux/main/docs/cli-contract.md
curl -fsSL https://raw.githubusercontent.com/manaflow-ai/cmux/main/skills/cmux/SKILL.md
```

Topics for `cmux docs <topic>`: `settings`, `shortcuts`, `api`, `browser`, `agents`, `dock`.

## Output format

```bash
cmux --json <command>             # JSON output for parsing
cmux --id-format uuids <command>  # use UUIDs instead of refs in output
cmux --id-format both  <command>  # include both
```

Prefer refs in interactive use; switch to UUIDs only when stable handles must survive renumbering.

## Agent integrations

cmux ships hooks for agent CLIs. You generally don't need to touch these, but they exist:

```bash
cmux claude-teams [claude-args...]   # wraps `claude` with cmux hooks
cmux codex-teams  [codex-args...]
cmux omo [opencode-args...]
cmux omx [omx-args...]
cmux omc [omc-args...]
cmux hooks setup       # install hooks for all supported agents
cmux hooks uninstall
cmux hooks <agent> install|uninstall|event [--project ...]
cmux hooks feed --source <agent> --event <event>
```

## SSH / remote / VM

```bash
cmux ssh user@host --name "prod" --port 22 --identity ~/.ssh/id_ed25519
cmux vm new           # alias: cmux cloud
cmux vm ls
cmux vm exec <id> -- <cmd>
cmux vm shell <id>
cmux vm ssh <id>
cmux vm rm <id>
cmux remote-daemon-status --os darwin --arch arm64
```

## tmux-compatibility commands

cmux exposes tmux-style aliases for muscle-memory. The most useful:

```bash
cmux capture-pane [--scrollback] [--lines N]
cmux resize-pane --pane pane:N (-L|-R|-U|-D) [--amount N]
cmux pipe-pane --command "tee /tmp/out.log"
cmux wait-for [-S|--signal] <name> [--timeout <s>]
cmux swap-pane --pane pane:1 --target-pane pane:2
cmux break-pane --pane pane:1
cmux join-pane --target-pane pane:1
cmux next-window | cmux previous-window | cmux last-window
cmux last-pane
cmux find-window [--content] [--select] <query>
cmux clear-history
cmux set-hook <event> <command>
cmux set-buffer <text> ; cmux list-buffers ; cmux paste-buffer
cmux respawn-pane --command "<cmd>"
cmux display-message [-p] "<text>"
```

## Events stream (for long-running automation)

```bash
cmux events --after 0 --reconnect --no-heartbeat
cmux events --name workspace.focused --category workspace --limit 50
cmux events --cursor-file ~/.cache/cmux-cursor
```

## Auth, feedback, version

```bash
cmux auth status ; cmux auth login ; cmux auth logout
cmux login ; cmux logout            # aliases
cmux version
cmux capabilities                   # JSON of supported features
cmux ping                           # smoke-test socket
cmux feedback --email me@x --body "..." --image /tmp/shot.png
```

## Common recipes

### Open a repo in a new workspace and run dev server

```bash
cmux new-workspace --name "agents" --cwd ~/Work/personal_projects/agents \
                   --command "just dev" --focus true
```

### Split current workspace, run tests on the right

```bash
cmux new-split right
cmux send "just test\n"             # CMUX_SURFACE_ID is already set
```

### Browser-driven smoke test inside cmux

```bash
SURFACE=$(cmux --json browser open https://app.local/login | jq -r '.surface_ref')
cmux browser "$SURFACE" wait --load-state complete --timeout-ms 15000
cmux browser "$SURFACE" snapshot --interactive
cmux browser "$SURFACE" fill e1 "user@x"
cmux browser "$SURFACE" fill e2 "pw"
cmux --json browser "$SURFACE" click e3 --snapshot-after
cmux browser "$SURFACE" wait --url-contains "/dashboard" --timeout-ms 15000
cmux browser "$SURFACE" screenshot --out /tmp/dashboard.png
```

### Notify when a long task finishes

```bash
just build && cmux notify --title "build OK" --body "$(date)" --surface "$CMUX_SURFACE_ID"
```

### Read what's in another pane

```bash
cmux read-screen --surface surface:7 --scrollback --lines 200
```

## Notes for agent use

- **Default to refs in output, parse with `--json`** — don't grep human-readable tables.
- **Layout commands are focus-neutral by default.** Only pass `--focus true` when you intentionally want the user pulled to that surface (it's disruptive).
- **Identity is stable across move/reorder/split-off** — capture a `surface:N` once and reuse it through the task.
- **Don't run `cmux send` against a surface whose contents you didn't read first** unless you're sending into a known shell prompt — you can clobber an interactive REPL or editor.
- **`cmux reload-config` is in-place** — no app restart needed; safe to run after editing `cmux.json` or Ghostty config.
- **Trigger-flash is the polite cue.** Prefer it over focusing a surface when you just want the user to notice something.
- **Help is always available:** `cmux help`, `cmux <command> --help`, `cmux docs <topic>`.
