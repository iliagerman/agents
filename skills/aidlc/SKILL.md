---
name: aidlc
description: Add, start, install, or update AWS AI-DLC (AI-Driven Development Life Cycle / aidlc-workflows) rules in a software project. Use this whenever the user asks to add AIDLC/AI-DLC to a repo, initialize the AI-DLC workflow, update AIDLC rules, configure aidlc-workflows for Claude Code, Cursor, Codex, Copilot, Cline, Kiro, or Amazon Q, or asks how to begin development "Using AI-DLC".
---

# AWS AI-DLC Project Setup

Use this skill to install or update [awslabs/aidlc-workflows](https://github.com/awslabs/aidlc-workflows) in a project.

AI-DLC is delivered as project-level agent rules. The setup always has two parts:

1. Put the core workflow where the user's coding agent reads project instructions.
2. Put detailed rules in the project so the core workflow can reference them.

## First response checklist

When the user asks to add/start/update AI-DLC:

1. Identify the target project path. If unclear, use the current working directory and say so.
2. Identify the target agent/rule format. If unclear, infer from project files; otherwise ask one short question.
3. For an existing project, inspect current rule files before overwriting them.
4. Install/update the latest AI-DLC release.
5. Report changed files and tell the user how to verify and start the workflow.

## Agent selection

Infer the desired format from the user's wording or existing files:

| Agent | Use when | Core rule target |
| --- | --- | --- |
| Claude Code | user says Claude/Claude Code, or repo has `CLAUDE.md` | `CLAUDE.md` |
| Claude Code directory variant | user asks for `.claude` | `.claude/CLAUDE.md` |
| Cursor | user says Cursor, or repo has `.cursor/` | `.cursor/rules/ai-dlc-workflow.mdc` |
| OpenAI Codex | user says Codex, or repo has `AGENTS.md` | `AGENTS.md` |
| GitHub Copilot | user says Copilot | `.github/copilot-instructions.md` |
| Cline | user says Cline, or repo has `.clinerules/` | `.clinerules/core-workflow.md` |
| Kiro | user says Kiro | `.kiro/steering/aws-aidlc-rules/` |
| Amazon Q Developer | user says Amazon Q/Q Developer | `.amazonq/rules/aws-aidlc-rules/` |

For Cursor and Cline, `AGENTS.md` is also supported by AI-DLC as an alternative, but prefer the native rule directory unless the user asks for the simple `AGENTS.md` option.

## Install/update with the bundled script

Prefer the bundled script for repeatable installs. It downloads the latest GitHub release zip named `ai-dlc-rules-v*.zip`, falls back to the repository zip if needed, and replaces the AI-DLC rule detail directory with the downloaded version.

From this skill directory:

```bash
python3 scripts/aidlc_project.py /path/to/project --agent claude
```

Supported `--agent` values:

```text
claude, claude-dir, cursor, codex, copilot, cline, kiro, amazonq
```

Examples:

```bash
# Claude Code, project-root CLAUDE.md
python3 scripts/aidlc_project.py . --agent claude

# Cursor project rules
python3 scripts/aidlc_project.py ~/work/my-app --agent cursor

# OpenAI Codex AGENTS.md
python3 scripts/aidlc_project.py . --agent codex
```

The script writes `.aidlc-version` with the downloaded release tag and prints changed files.

## Manual installation reference

If the script is not appropriate, do the same thing manually:

1. Download the latest release zip from `https://github.com/awslabs/aidlc-workflows/releases/latest`.
2. Extract it outside the target project.
3. Copy the core workflow and rule details according to the agent table above.

Common native layouts:

```text
# Claude Code
<project>/CLAUDE.md
<project>/.aidlc-rule-details/

# Cursor
<project>/.cursor/rules/ai-dlc-workflow.mdc
<project>/.aidlc-rule-details/

# Codex
<project>/AGENTS.md
<project>/.aidlc-rule-details/

# Copilot
<project>/.github/copilot-instructions.md
<project>/.aidlc-rule-details/
```

For Cursor, wrap the copied `core-workflow.md` in `.mdc` frontmatter:

```md
---
description: "AI-DLC (AI-Driven Development Life Cycle) adaptive workflow for software development"
alwaysApply: true
---

[paste core-workflow.md content here]
```

## Protect existing project instructions

Many projects already have `CLAUDE.md`, `AGENTS.md`, or Copilot instructions. AI-DLC's official install commands overwrite those files, but users may not expect their local instructions to disappear.

Before overwriting an existing non-AIDLC instruction file:

1. Read it.
2. If it contains unrelated project guidance, ask whether to replace it, merge it, or use an alternate location where the agent supports one.
3. If replacing, leave the old content recoverable through git or a timestamped backup.

Do not merge blindly: AI-DLC core workflow is designed as a complete project rule. If you merge, place project-specific notes after the AI-DLC content under a clear heading such as `# Project-specific notes`.

## Updating an existing AI-DLC install

For updates:

1. Detect existing install targets: `.aidlc-rule-details/`, `.aidlc-version`, `CLAUDE.md`, `.cursor/rules/ai-dlc-workflow.mdc`, `AGENTS.md`, etc.
2. Re-run the install script with the same agent format.
3. If `.aidlc-version` changed, mention old and new versions.
4. If the user has custom extensions under `.aidlc-rule-details/extensions/`, preserve them unless they clearly came from the upstream package.

If custom extensions exist, copy them aside before update, run the update, then restore the custom extension directory and report that you preserved it.

## Starting the workflow after setup

Tell the user to open their coding agent in the project and begin with a prompt like:

```text
Using AI-DLC, build [the feature or application].
```

For existing projects, a good first prompt is:

```text
Using AI-DLC, analyze this project and propose the right workflow for [goal].
```

AI-DLC should guide the user through Inception, Construction, and future Operations phases, generating artifacts under `aidlc-docs/`.

## Verification

After installation, verify by checking file layout and asking the agent what AI-DLC workflow is active.

Useful checks:

```bash
find . -maxdepth 3 \( -name 'CLAUDE.md' -o -name 'AGENTS.md' -o -name 'ai-dlc-workflow.mdc' -o -name 'copilot-instructions.md' -o -name '.aidlc-version' \) -print
find .aidlc-rule-details -maxdepth 2 -type f | head
```

Expected high-level workflow: Inception → Construction → Operations.
