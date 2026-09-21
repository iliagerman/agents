---
name: aidlc
description: Install, initialize, update, or migrate AWS AI-DLC Workflows 2.x in a software project. Use whenever the user mentions AI-DLC/AIDLC, aidlc-workflows v2, a greenfield AI-DLC setup, upgrading or migrating an existing AI-DLC project, starting development "Using AI-DLC", or configuring Claude Code, Codex CLI, Kiro, opencode, or GitHub Copilot for AI-DLC. Also use when setup must preserve existing Claude provider, Bedrock, region, model, effort, hooks, permissions, or agent configuration.
compatibility: Requires network access and Python 3. AI-DLC Workflows 2.x requires bun in target projects.
metadata:
  upstream: awslabs/aidlc-workflows
  upstream-branch: v2
---

# AWS AI-DLC Workflows 2.x

Install and update the GA v2 implementation from the authoritative upstream `v2` branch.

## Upstream facts

- Source: `https://github.com/awslabs/aidlc-workflows/tree/v2`.
- GitHub's `latest` release can still point to v1. Never use the Releases API to select v2.
- Read the framework version from upstream `core/tools/aidlc-version.ts`; never hardcode it.
- V2 requires `bun` and uses a new engine, hooks, agents, skills, workspace, and artifact model.
- Upstream has no first-class resumable v1-to-v2 state migration. Issue `#636` tracks that work.

## Supported harnesses

| `--agent` | Harness | Invocation |
|---|---|---|
| `claude` | Claude Code | `/aidlc` |
| `codex` | OpenAI Codex CLI >= 0.145.0 | `$aidlc` |
| `kiro` | Kiro CLI >= 2.6 | `/aidlc` |
| `kiro-ide` | Kiro IDE | `/aidlc` |
| `opencode` | opencode >= 1.17 | `/aidlc` |
| `copilot` | GitHub Copilot CLI/VS Code | `/aidlc` |

V2 has no native pi, Cursor, Cline, or Amazon Q harness. Pi can run this setup skill, but that does not make v2 hooks native to pi.

## First-response checklist

1. Resolve the target project path.
2. Infer the harness from existing files or ask one short question.
3. Inspect existing AI-DLC, harness settings, `AGENTS.md`, `CLAUDE.md`, and `.gitignore`.
4. Check git status. Preserve or stash uncommitted work before migration or a major update.
5. Classify AI-DLC state as fresh, v2 update, or v1 migration.
6. Distinguish software state separately: a project can be AI-DLC-fresh but application-brownfield.
7. Run the installer only after config conflicts are understood.
8. Inspect the diff and run the harness doctor command in a fresh session.

## Detect current state

```bash
find . -maxdepth 3 \
  \( -name '.aidlc-version' -o -name '.aidlc-rule-details' -o -name 'aidlc-docs' \
     -o -name '.aidlc' -o -name '.claude' -o -name '.codex' -o -name '.kiro' \
     -o -name '.opencode' -o -name '.github' -o -name 'AGENTS.md' \
     -o -name 'CLAUDE.md' \) -print
```

Classify:

- **V1:** `.aidlc-rule-details/`, `.aidlc/aidlc-rules/VERSION`, old core workflow text, or `.aidlc-version` below 2.
- **V2:** harness engine plus `aidlc/spaces/default/memory/`, usually with `.aidlc-version` beginning `2.`.
- **Fresh AI-DLC:** neither layout exists.

Then classify the application:

- **Greenfield application:** no existing application code or deployed workload.
- **Brownfield application:** existing application code, infrastructure, or live behavior must be preserved.

Do not call an existing codebase greenfield merely because AI-DLC is not installed.

## Claude runtime configuration safety

AI-DLC setup must not silently change how Claude connects or which model it uses.

The bundled installer intentionally does **not** import these upstream project defaults:

- `CLAUDE_CODE_USE_BEDROCK`
- `AWS_REGION`
- `ANTHROPIC_DEFAULT_*_MODEL`
- project-level `model`
- project-level `effortLevel`

It preserves existing project `.claude/settings.json` values and does not touch user-global `~/.claude/settings.json`, shell environment variables, provider/base URL, credentials, or local settings. It merges only AI-DLC mechanics such as hooks, announcement, permissions, and status line.

After Claude installation or update, verify:

```bash
python3 -m json.tool .claude/settings.json >/dev/null
grep -nE 'CLAUDE_CODE_USE_BEDROCK|ANTHROPIC_DEFAULT_.*MODEL|AWS_REGION|"model"|effortLevel' \
  .claude/settings.json || true
```

Existing user-authored matches are allowed; the installer must not add them. Restart Claude Code after settings change.

## Fresh or greenfield installation

Use this path when AI-DLC is not installed. Do not pass `--migrate-v1`.

1. Confirm the intended harness.
2. Inspect existing harness configuration even in a greenfield application repository.
3. Confirm `bun` is available on the non-interactive shell path.
4. Run:

```bash
python3 scripts/aidlc_project.py /path/to/project --agent <harness>
```

5. Inspect `git diff` and untracked files.
6. For Claude, verify runtime/provider/model settings were preserved.
7. Start a fresh harness session and run doctor.
8. Start the first intent with a clear goal and explicit scope when useful.

Examples:

```text
/aidlc Build the first production feature
/aidlc --scope enterprise "Design and build the regulated service"
/aidlc compose "Create a design-only workflow for the shared application layer"
```

For an application-greenfield project, AI-DLC should establish requirements and architecture before code. For an application-brownfield project with a fresh AI-DLC install, tell the first intent to inspect the existing project and preserve current behavior.

## V2 update

For an existing v2 install, run the same command without `--migrate-v1`:

```bash
python3 scripts/aidlc_project.py /path/to/project --agent <harness>
```

The script overlays managed harness files, preserves the existing `aidlc/` workspace and user-authored memory by copying only missing workspace-shell files, merges marked `AGENTS.md` and `.gitignore` blocks, and writes the actual upstream version to `.aidlc-version`.

After update:

- inspect the full diff because upstream overlays can change many framework files;
- verify project-specific memory and knowledge remain intact;
- verify Claude runtime settings remain unchanged;
- run doctor in a fresh session.

## V1-to-v2 migration

### Migration boundary

An existing source project can adopt v2, but v1 workflow state and `aidlc-docs/` cannot become a resumable v2 intent. Never map v1 stage completion to v2 approvals, receipts, or audit state.

### Safe migration

1. Commit, stash, or otherwise preserve current work.
2. Finish or stop any active v1 workflow.
3. Read custom v1 extensions and project rules; identify only approved guidance worth porting.
4. Run:

```bash
python3 scripts/aidlc_project.py /path/to/project --agent <harness> --migrate-v1
```

5. The script creates a timestamped sibling backup. It supports both common v1 layouts:
   - `.aidlc-rule-details/`
   - `.aidlc/aidlc-rules/`
6. The active v1 rule package is removed. `aidlc-docs/` remains in place as historical evidence.
7. Inspect the migration diff and backup before committing.
8. Port approved organization/team/project guidance into `aidlc/spaces/default/memory/` or space knowledge. Do not bulk-copy old workflow instructions.
9. Run doctor in a fresh session.
10. Start a new v2 intent. Treat selected v1 artifacts as untrusted background context that newer approved decisions can override.

Never delete `aidlc-docs/` automatically.

## Project config conflicts

- Preserve unrelated `AGENTS.md` and `CLAUDE.md` guidance.
- Claude: preserve provider, model, effort, environment, credentials, user hooks, and existing permissions; merge AI-DLC hooks only.
- Codex: preserve `.codex/config.toml`; review `.codex/config.aidlc.toml.example` manually.
- Kiro: existing settings win, including the user's preferred default agent.
- opencode: preserve existing wildcard permissions; add only AI-DLC-specific permission paths.
- Copilot: merge only AI-DLC-prefixed `.github` files and the marked `AGENTS.md` block.
- Secrets belong in user/local settings or environment variables, never committed project configuration.

## Prerequisites

All v2 harnesses require `bun`:

```bash
command -v bun
```

If missing:

```bash
curl -fsSL https://bun.sh/install | bash
```

For zsh, make the bun path available from `~/.zshenv`, not only `~/.zshrc`.

## Verification

Start a fresh harness session after files change.

Claude Code:

```text
/aidlc --doctor
/aidlc --version
```

Direct diagnostic when Claude is not open:

```bash
bun .claude/tools/aidlc-utility.ts doctor
```

Codex CLI:

```bash
bun .codex/tools/aidlc-utility.ts doctor
```

Kiro CLI/IDE:

```bash
bun .kiro/tools/aidlc-utility.ts doctor
```

opencode or Copilot:

```bash
bun .aidlc/tools/aidlc-utility.ts doctor
```

## Report

Report:

- installed upstream version;
- selected harness;
- fresh install, v2 update, or v1 migration;
- changed and merged files;
- backup path for v1 migration;
- preserved historical documents and custom memory;
- Claude provider/model preservation result;
- unresolved manual config merges;
- doctor result;
- exact next command.
