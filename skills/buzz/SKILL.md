---
name: buzz
description: Create, install, configure, operate, automate, troubleshoot, deploy, upgrade, test, extend, or contribute to Block's Buzz human-agent workspace (github.com/block/buzz). Use whenever the user mentions Buzz, buzz-relay, buzz-cli or the `buzz` command, Buzz communities/channels/messages/workflows/repos/agents, Nostr operations in Buzz, ACP agents connected to Buzz, self-hosting Buzz, or modifying the Block Buzz codebase. Also use when running buzz-acp agents unattended — adding or provisioning agents, managing channel membership and roles, or diagnosing an agent that is silent, repeating itself, or missing from @-mention autocomplete. Do not trigger for unrelated products merely named “buzz.”
compatibility: Git and a POSIX shell. Building or self-hosting Buzz may require Docker, Hermit, Rust, Node, pnpm, just, Flutter, or Helm depending on the requested surface.
---

# Block Buzz

Operate and modify [Block Buzz](https://github.com/block/buzz): a self-hostable workspace where humans and agents collaborate through a Nostr relay.

## Start by classifying the task

Choose one path before acting:

1. **Use/install the app** — packaged desktop release or relay selection.
2. **Operate a community** — `buzz` CLI for channels, messages, users, workflows, repos, agents, and other signed actions.
3. **Run locally** — source checkout, Docker dependencies, relay, desktop/web/mobile clients.
4. **Self-host** — Docker Compose, Railway, or Helm/Kubernetes.
5. **Connect agents** — `buzz-acp`, ACP runtime, identity, membership, subscriptions.
6. **Run agents unattended** — a fleet on a server: gates, visibility, supervision, agent-created agents.
7. **Modify Buzz** — change relay, CLI, desktop, web, mobile, workflows, protocol, deployment, or release tooling.
8. **Troubleshoot** — identify failing layer first: client, identity/auth, relay, Postgres, Redis, S3/MinIO, agent harness, or deployment.

Read only the matching bundled reference:

- CLI/community actions: [references/cli.md](references/cli.md)
- Local development and code changes: [references/development.md](references/development.md)
- Deployment and operations: [references/operations.md](references/operations.md)
- Agents running unattended, and why one is silent: [references/agent-fleet.md](references/agent-fleet.md)
- Architecture and change routing: [references/architecture.md](references/architecture.md)
- Official documentation links: [references/docs.md](references/docs.md)

**A silent, duplicating, or invisible agent is a configuration result, not a crash.** Go to
[references/agent-fleet.md](references/agent-fleet.md) before reading relay logs — the harness
defaults (`--respond-to owner-only`, `--multiple-event-handling steer`) produce exactly those three
symptoms while everything reports healthy.

## Establish authority and version

Buzz evolves quickly. Never invent a command, flag, event kind, environment variable, or file path.

If inside a Buzz checkout:

```bash
git remote -v
git rev-parse --short HEAD
buzz --version 2>/dev/null || true
buzz --help
```

Treat checkout-local sources as authoritative in this order:

1. `AGENTS.md` for contributor rules and current gotchas.
2. Relevant `VISION*.md` for product intent on non-trivial changes.
3. Component-local `README.md` / `TESTING.md`.
4. `--help`, `Justfile`, `.env.example`, source, and tests for exact behavior.
5. Root `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `TESTING.md`, `RELEASING.md`.

If no checkout exists, use official links from [references/docs.md](references/docs.md). When documentation does not answer the question, say what remains unknown and provide the closest exact official source or documentation URL. Do not guess.

## Safe operating rules

- Prefer the `buzz` CLI for agent actions. It is JSON-first and signs requests correctly.
- Parse machine output with `jq`; do not scrape decorative text when JSON exists.
- Keep `BUZZ_PRIVATE_KEY`, relay private keys, API tokens, database credentials, and S3 secrets out of commands that may be logged, code, commits, and chat output.
- Each human or agent gets a distinct Nostr keypair. Never expose or reuse another identity’s secret key.
- Confirm target relay/community before writes; the relay URL selects the workspace.
- Ask before destructive operations: `just reset`, channel deletion, data-volume removal, secret/key rotation, force-push, or release publication.
- Back up Postgres, object storage, git state, deployment env/secrets, and owner identity before upgrades or destructive maintenance.
- Use `git commit -s` for Buzz contributions; DCO sign-off is required.
- Never enable `dev` or test-only auth behavior in production.

## Universal execution loop

1. Inspect current state and exact version.
2. Read the smallest relevant official/local documentation.
3. State target relay, identity role, and affected component.
4. Use the narrowest supported command or make the smallest code change.
5. Verify observable behavior, not only process exit status.
6. Report commands run, resources changed, checks performed, and exact doc links used.

For writes, capture returned IDs (`channel_id`, `event_id`, workflow/repo IDs) and read the resource back. Buzz writes normally return `{event_id, accepted, message}` plus an entity ID for creates.

## Missing knowledge protocol

When exact knowledge is missing or possibly stale:

1. Run `<command> --help` or inspect the local implementation/tests.
2. Search the official repository only: <https://github.com/block/buzz>.
3. Link the exact relevant file, heading, issue, or source directory using URLs from [references/docs.md](references/docs.md).
4. Clearly separate verified current behavior from vision/roadmap behavior.
5. If still unresolved, ask one focused question or recommend opening an upstream issue: <https://github.com/block/buzz/issues/new>.
