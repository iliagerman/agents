# Buzz architecture and change routing

Official source: [ARCHITECTURE.md](https://github.com/block/buzz/blob/main/ARCHITECTURE.md)

## Mental model

- A Buzz community is the workspace selected by request host/relay URL.
- Relay is single source of truth.
- Humans, agents, workflows, messages, reactions, git activity, and other actions are signed Nostr events.
- Event `kind` is primary protocol dispatch key.
- Clients use WebSocket NIP-01/NIP-42; narrow HTTP surfaces cover generic event bridge, metadata, media, webhooks, git, and probes.
- Postgres stores events and derived state; Redis handles fan-out/presence/typing; S3-compatible storage holds media and git objects.
- In multi-community mode, tenant context is host-derived before auth/data access and must flow through every subsystem.

## Event pipeline

Stored event path, conceptually:

1. auth/scope and pubkey checks;
2. reject AUTH persistence and route ephemeral kinds separately;
3. verify ID/signature;
4. enforce channel membership;
5. insert idempotently;
6. publish/fan out;
7. index/audit/trigger workflows.

Do not alter ordering or move tenant/auth checks later without explicit security analysis and tests.

Ephemeral kinds are not persisted, audited, or historically queryable. Presence has distinct handling. Verify current source before changing these paths.

## Protocol boundaries

- Standard Nostr kinds occupy standard ranges; Buzz custom kinds use project-defined ranges.
- `crates/buzz-core/src/kind.rs` is current source of truth. Never copy a number from memory.
- Channel events use `h` tags for channel scope.
- Parameterized channel metadata/membership events identify channel with `d` tags.
- Global subscriptions must not leak private channel events.
- Search service returns candidates; relay remains responsible for authorization.

External protocol reference: [Nostr NIPs](https://github.com/nostr-protocol/nips).

## Where changes belong

| Need | Primary location | Also inspect |
|---|---|---|
| New event/type/filter | `crates/buzz-core` | relay, SDK, CLI, desktop/mobile constants, tests |
| Relay ingest/routing/API | `crates/buzz-relay` | auth, DB, pubsub, search, audit, workflow |
| Persistence/query/migration | `crates/buzz-db`, `migrations/` | tenant constraints, indexes, replay/conformance |
| Auth/scopes | `crates/buzz-auth` | relay ingress, NIP-42/NIP-98, CLI behavior |
| Search | `crates/buzz-search` + Postgres FTS schema | relay re-authorization |
| Presence/fan-out | `crates/buzz-pubsub` | Redis keys, community prefix, local echo dedup |
| Workflow schema/execution | `crates/buzz-workflow` | relay trigger, CLI, current known limitations |
| Agent-facing action | `crates/buzz-cli` | SDK/relay endpoint or event |
| Agent orchestration | `crates/buzz-acp` | ACP runtime docs, subscriptions, identity/membership |
| Desktop UI/native | `desktop/src`, `desktop/src-tauri` | community reset boundary, E2E bridge |
| Browser client | `web/` | relay-served assets and auth behavior |
| Mobile | `mobile/` | Riverpod/hooks rules, shared kind constants |
| Git hosting | relay git modules, NIP-34 crates | object-storage spec, credentials/signing |
| Deployment | `deploy/compose`, `deploy/charts/buzz` | env schema, probes, migrations, backups |

## Security invariants

- Resolve community from host; reject unknown hosts closed.
- Verify signatures and event IDs before persistence.
- Auth identity must match signing pubkey.
- Check membership before subscription registration and channel writes.
- Scope every tenant-observable DB row/query, Redis key, search result, workflow, media object, git pointer, and audit chain.
- Keep NIP-42 AUTH events and ephemeral events out of storage/audit.
- Preserve SSRF protections for outbound workflow calls.
- Preserve hash-chain canonicalization/single-writer behavior in audit code.
- No `unsafe`; avoid production `unwrap()` / `expect()` per upstream contributor rules.

## Known limitations

Never infer roadmap completion from types or reserved kinds. Check the live [Known Limitations](https://github.com/block/buzz/blob/main/ARCHITECTURE.md#9-known-limitations), issues, and tests. Historically evolving areas include rate limiting, workflow approvals/actions, huddle recording, mobile/push, remote agents, shared compute, and multi-tenant behavior.

Use these terms in reports:

- **works now** — verified in implementation/tests/runtime;
- **partially wired** — some layers exist but end-to-end behavior is incomplete;
- **vision** — documented direction without verified complete implementation.
