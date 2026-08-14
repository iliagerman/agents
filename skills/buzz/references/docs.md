# Official Buzz documentation index

Use checkout-local versions when available. These links track upstream `main` and provide a destination whenever bundled knowledge is incomplete or stale.

## Start here

- Repository: <https://github.com/block/buzz>
- README / install / quick start: <https://github.com/block/buzz/blob/main/README.md>
- Agent contributor rules: <https://github.com/block/buzz/blob/main/AGENTS.md>
- Architecture: <https://github.com/block/buzz/blob/main/ARCHITECTURE.md>
- Contributing: <https://github.com/block/buzz/blob/main/CONTRIBUTING.md>
- Testing: <https://github.com/block/buzz/blob/main/TESTING.md>
- Releasing: <https://github.com/block/buzz/blob/main/RELEASING.md>
- Security policy: <https://github.com/block/buzz/blob/main/SECURITY.md>
- Changelog: <https://github.com/block/buzz/blob/main/CHANGELOG.md>
- Releases: <https://github.com/block/buzz/releases/latest>
- Issues: <https://github.com/block/buzz/issues>
- Pull requests: <https://github.com/block/buzz/pulls>

## Product intent

- Core vision: <https://github.com/block/buzz/blob/main/VISION.md>
- Sovereignty/community domains: <https://github.com/block/buzz/blob/main/VISION_SOVEREIGN.md>
- Projects/git forge: <https://github.com/block/buzz/blob/main/VISION_PROJECTS.md>
- Agents: <https://github.com/block/buzz/blob/main/VISION_AGENT.md>
- Agent activity: <https://github.com/block/buzz/blob/main/VISION_ACTIVITY.md>
- Mesh/shared compute: <https://github.com/block/buzz/blob/main/VISION_MESH.md>
- Moderation: <https://github.com/block/buzz/blob/main/VISION_MODERATION.md>
- Remote agents: <https://github.com/block/buzz/blob/main/VISION_REMOTE_AGENTS.md>

Vision is not proof of implementation. Cross-check source/tests.

## CLI, agents, and protocol

- Buzz CLI docs: <https://github.com/block/buzz/blob/main/crates/buzz-cli/README.md>
- Buzz CLI live runbook: <https://github.com/block/buzz/blob/main/crates/buzz-cli/TESTING.md>
- ACP harness: <https://github.com/block/buzz/blob/main/crates/buzz-acp/README.md>
- Built-in agent: <https://github.com/block/buzz/blob/main/crates/buzz-agent/README.md>
- Third-party Nostr clients: <https://github.com/block/buzz/blob/main/NOSTR.md>
- Nostr NIPs: <https://github.com/nostr-protocol/nips>
- Agent Communication Protocol: <https://agentclientprotocol.com/>
- MCP-driven lifecycle hooks: <https://github.com/block/buzz/blob/main/docs/MCP_DRIVEN_HOOKS.md>
- Remote agent design: <https://github.com/block/buzz/blob/main/docs/remote-agents.md>
- Buzz entity links/deep links: <https://github.com/block/buzz/blob/main/docs/buzz-entity-links.md>

## Deployment and operations

- Docker Compose deployment: <https://github.com/block/buzz/blob/main/deploy/compose/README.md>
- Compose environment template: <https://github.com/block/buzz/blob/main/deploy/compose/.env.example>
- Compose operator script: <https://github.com/block/buzz/blob/main/deploy/compose/run.sh>
- Helm chart: <https://github.com/block/buzz/blob/main/deploy/charts/buzz/README.md>
- Railway template: <https://railway.com/deploy/buzz-relay-block>
- Railway/operator article: <https://engineering.block.xyz/blog/run-your-own-buzz-relay>
- Push gateway deployment: <https://github.com/block/buzz/blob/main/docs/push-gateway-deployment.md>
- Linux rendering troubleshooting: <https://github.com/block/buzz/blob/main/docs/linux-rendering-troubleshooting.md>

## Specialized architecture

- Multi-tenant relay spec: <https://github.com/block/buzz/blob/main/docs/multi-tenant-relay.md>
- Multi-tenant conformance: <https://github.com/block/buzz/blob/main/docs/multi-tenant-conformance.md>
- Git on object storage: <https://github.com/block/buzz/blob/main/docs/git-on-object-storage.md>
- Bridge channel-window extension: <https://github.com/block/buzz/blob/main/docs/bridge-channel-window.md>
- Shared compute development: <https://github.com/block/buzz/blob/main/docs/buzz-shared-compute-dev.md>

## Exact source discovery

Use GitHub code search for facts not covered by prose:

- Environment variable: `https://github.com/search?q=repo%3Ablock%2Fbuzz+BUZZ_VARIABLE&type=code`
- Command: `https://github.com/search?q=repo%3Ablock%2Fbuzz+COMMAND&type=code`
- Event kind: `https://github.com/search?q=repo%3Ablock%2Fbuzz+KIND_NAME&type=code`

Prefer local `rg` when a checkout exists:

```bash
rg -n 'BUZZ_[A-Z0-9_]+' .env.example deploy crates desktop web mobile
rg -n 'KIND_[A-Z0-9_]+' crates/buzz-core/src/kind.rs
rg -n 'Subcommand|enum .*Command' crates/buzz-cli/src
find . -iname README.md -o -iname TESTING.md -o -iname AGENTS.md
```

When citing mutable `main`, include the inspected commit SHA. For review, incident, or compliance evidence, convert links to a commit permalink:

```text
https://github.com/block/buzz/blob/<commit-sha>/<path>#Lx-Ly
```
