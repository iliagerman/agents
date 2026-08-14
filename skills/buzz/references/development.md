# Developing and modifying Buzz

Official docs: [AGENTS.md](https://github.com/block/buzz/blob/main/AGENTS.md) · [Contributing](https://github.com/block/buzz/blob/main/CONTRIBUTING.md) · [Testing](https://github.com/block/buzz/blob/main/TESTING.md)

## First-time setup

```bash
git clone https://github.com/block/buzz.git
cd buzz
. ./bin/activate-hermit
just setup
just build
just hooks
```

Hermit pins the toolchain. Without Hermit, current upstream minimums include Rust, Node, pnpm, Docker, and `just`; mobile work also needs Flutter. Read current [CONTRIBUTING.md prerequisites](https://github.com/block/buzz/blob/main/CONTRIBUTING.md#prerequisites).

Daily development:

```bash
. ./bin/activate-hermit
just dev                 # relay + Tauri desktop
# or split:
just relay
just desktop-dev
```

Other surfaces:

```bash
just relay-web
just web
just desktop-standalone
just mobile-dev          # for humans; agents must follow AGENTS.md mobile restrictions
```

## Required planning context

Before non-trivial work:

1. Read checkout-local `AGENTS.md` completely.
2. Read `VISION.md` and relevant `VISION_*.md`.
3. Read relevant component `README.md` / `TESTING.md`.
4. Search open [issues](https://github.com/block/buzz/issues) and [pull requests](https://github.com/block/buzz/pulls).
5. Identify current behavior, desired behavior, affected event kinds, tenant boundary, and tests.

Vision describes intended direction, not necessarily shipped behavior. Label roadmap gaps clearly.

## Component map

- Relay/core/auth/data: `crates/buzz-relay`, `buzz-core`, `buzz-db`, `buzz-auth`, `buzz-pubsub`, `buzz-search`, `buzz-audit`, `buzz-media`.
- Agent surface: `buzz-cli`, `buzz-acp`, `buzz-agent`, `buzz-dev-mcp`, `buzz-persona`, `buzz-workflow`.
- Git: `git-sign-nostr`, `git-credential-nostr`, relay git handlers.
- Desktop: `desktop/` — Tauri 2, React, Vite, Tailwind, Biome.
- Web: `web/`.
- Mobile: `mobile/` — Flutter, Riverpod, hooks.
- Deployment: `deploy/compose`, `deploy/charts/buzz`.
- Protocol migrations: `migrations/` and `crates/buzz-core/src/kind.rs`.

Read [references/architecture.md](architecture.md) before cross-component work.

## Change rules

### Protocol/event behavior

Prefer a signed Nostr event over a new endpoint. Define the kind in `crates/buzz-core/src/kind.rs`, update scope routing and side effects in the relay, add persistence/search behavior where needed, then expose agent-facing operations through `buzz-cli`.

For every new event kind:

1. Check kind collision and sub-range.
2. Define typed payload if content is structured.
3. Register required auth scope.
4. Add relay post-storage side effects.
5. Add DB/search handling if queryable.
6. Add unit and integration tests.
7. Keep desktop/mobile kind constants synchronized where applicable.
8. Document user-facing behavior.

Exact current walkthrough: [CONTRIBUTING.md — How to Add a New Event Kind](https://github.com/block/buzz/blob/main/CONTRIBUTING.md#how-to-add-a-new-event-kind).

### HTTP

Use HTTP only when the operation inherently needs it: generic Nostr bridge, media, webhooks, git smart HTTP, metadata, or health. If still needed, follow [How to Add a New API Endpoint](https://github.com/block/buzz/blob/main/CONTRIBUTING.md#how-to-add-a-new-api-endpoint). Resolve host/community before auth or data lookup.

### Agent CLI

Add agent-facing operations to `crates/buzz-cli`; keep JSON stdout/stderr and stable exit semantics. Update CLI docs and live tests.

### Desktop

Feature code lives under `desktop/src/features/`. Use rem-based named text tokens. Community-scoped module singletons need reset wiring in `resetCommunityState()`. Use the Tauri E2E mock bridge; a plain browser cannot represent the app correctly.

### Mobile

Follow checkout-local rules. Current upstream requires Riverpod/hooks, forbids `StatefulWidget`, limits feature cross-imports, and instructs agents not to run destructive/heavy Flutter commands. Run only allowed format/analyze/test recipes.

## Validation ladder

Use the narrowest meaningful check, then broaden by risk:

```bash
# Rust
cargo test -p <crate>
cargo clippy -p <crate> --all-targets -- -D warnings
just fmt-check

# Desktop
just desktop-check
just desktop-test
just desktop-typecheck
just desktop-e2e-smoke

# Web
just web-check
just web-typecheck
just web-e2e-smoke

# Mobile
just mobile-check
just mobile-test

# Relay/data/auth integration
just test

# Full PR gate
just ci
```

Root `cargo test` does not include the excluded desktop Tauri workspace. Use `just desktop-tauri-test` or its explicit manifest.

For visible UI changes, capture focused screenshots:

```bash
just desktop-screenshot --name change --route /target --click target-testid
```

Use `scripts/post-screenshots.sh` for PR screenshots; do not host them through Buzz media URLs.

## Contribution workflow

- Keep PR focused.
- Add regression tests for fixes and behavior tests for features.
- Use Conventional Commit PR titles.
- Commit with DCO sign-off: `git commit -s`.
- Run `just ci` before PR, plus integration/E2E checks relevant to the touched surface.
- Include before/after screenshots or recording for UI work.
- Never force-push during review unless maintainers request it.
