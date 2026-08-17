# Installing, deploying, and operating Buzz

Official docs: [README](https://github.com/block/buzz/blob/main/README.md) · [Compose deployment](https://github.com/block/buzz/blob/main/deploy/compose/README.md) · [Helm chart](https://github.com/block/buzz/blob/main/deploy/charts/buzz/README.md)

## Packaged desktop app

Use the [latest release](https://github.com/block/buzz/releases/latest). Choose artifact matching OS/architecture. Desktop defaults to `ws://localhost:3000`; set `BUZZ_RELAY_URL` before launch or switch relay inside the app.

Do not direct Block employees to the OSS build; upstream README points them to the internal release repository.

## Local source run

```bash
git clone https://github.com/block/buzz.git
cd buzz
. ./bin/activate-hermit
just setup && just build
just dev
```

Default ports:

- relay/app: `3000`
- health: `8080`
- metrics: `9102`
- Postgres: `5432`
- Redis: `6379`
- MinIO: `9000` / console `9001`
- Adminer: `8082`

Verify:

```bash
curl -fsS http://localhost:3000/health
curl -fsS http://localhost:8080/_readiness
just ps
```

Stop while retaining data: `just down`. `just reset` deletes development data; require confirmation and warn when Desktop shares the same Docker stack.

## Docker Compose production

The root `docker-compose.yml` is development-only. Use `deploy/compose/` for single-node/VPS operation.

```bash
cd deploy/compose
cp .env.example .env
$EDITOR .env                # replace every CHANGE_ME
./run.sh config
./run.sh start
./run.sh status
./run.sh logs relay
```

TLS with Caddy:

```bash
BUZZ_COMPOSE_TLS=true ./run.sh start
```

Operator commands:

```bash
./run.sh add-member <npub-or-hex> --role member
./run.sh remove-member <npub-or-hex>
./run.sh list-members
./run.sh backup-hint
./run.sh pull
./run.sh upgrade
```

For multiple member additions, serialize them with a one-second delay; do not parallelize roster writes.

Production requirements:

- Replace every placeholder before startup.
- Pin `BUZZ_IMAGE` to an immutable SHA or release tag; `:main` is pre-release.
- Keep relay key, owner key, git hook HMAC secret, DB/Redis/S3 credentials stable.
- Use `wss://` public `RELAY_URL` behind TLS.
- Closed mode needs `RELAY_OWNER_PUBKEY`, relay membership, and stable signing identity.
- Migrations are opt-in through `BUZZ_AUTO_MIGRATE=true` or explicit `buzz-admin migrate`.

### Device-pairing relay and `/pair` 404s

Mobile identity sharing uses a separate, stateless NIP-AB WebSocket relay. A closed main relay advertises NIP-43 membership. Buzz Desktop interprets NIP-43 without an explicit `pairing_relay_url` as the legacy `<main-relay>/pair` endpoint. If the reverse proxy has no `/pair` route, pairing fails with:

```text
WebSocket connection failed: HTTP error: 404 Not Found
```

Do not route pairing through the authenticated main relay. Run the `buzz-pair-relay` binary included in the Buzz image, expose it only through TLS, and set `BUZZ_PAIRING_RELAY_URL` on the main relay. The pairing relay has no auth or persistence; it verifies signed kind `24134` events and enforces tight connection, frame, event, and lifetime limits. Keep its raw port on loopback or a private container network.

Example Compose service:

```yaml
services:
  pairing-relay:
    image: ${BUZZ_IMAGE:-ghcr.io/block/buzz:main}
    # Compose `command` does not replace the image ENTRYPOINT. Use `entrypoint`
    # or the container starts the main relay and then fails on missing DB config.
    entrypoint: ["/usr/local/bin/buzz-pair-relay"]
    environment:
      BUZZ_PAIR_RELAY_BIND_ADDR: 0.0.0.0:5000
    ports:
      - "127.0.0.1:${BUZZ_PAIR_HTTP_PORT:-8790}:5000"
    restart: unless-stopped
```

For a Tailnet-only deployment, a separate TLS port avoids path-routing ambiguity:

```bash
tailscale serve --bg --https=8445 http://127.0.0.1:8790
```

Then configure and recreate the main relay:

```dotenv
BUZZ_PAIRING_RELAY_URL=wss://buzz-host.example:8445
```

Verify discovery and the actual WebSocket upgrade:

```bash
curl -fsS -H 'Accept: application/nostr+json' https://buzz-host.example/ \
  | jq -r .pairing_relay_url

curl --http1.1 -isS --max-time 3 \
  -H 'Connection: Upgrade' \
  -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Version: 13' \
  -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
  https://buzz-host.example:8445/ | head -1
# HTTP/1.1 101 Switching Protocols
```

A `101` proves the TLS proxy reaches the pairing sidecar. Also confirm the main relay and a signed CLI read still work after recreation. Official implementation: [pairing discovery](https://github.com/block/buzz/blob/main/desktop/src-tauri/src/commands/pairing.rs), [pairing sidecar](https://github.com/block/buzz/tree/main/crates/buzz-pair-relay), and [Helm pairing relay](https://github.com/block/buzz/blob/main/deploy/charts/buzz/README.md#device-pairing-relay).

### Mobile push-notification status

Do not diagnose absent background notifications as an iOS permission or relay outage before checking current product status. Buzz's README currently lists mobile clients as being wired up and push notifications as pending code. The relay-side NIP-PL matcher and standalone APNs gateway exist, but that is not end-to-end mobile support.

The deployment documentation states that delivery still requires the mobile client to complete App Attest enrollment/delegation and place a gateway-issued opaque capability in an encrypted relay lease. Current OSS mobile source has no NIP-PL enrollment/lease path and no iOS `aps-environment` entitlement. Therefore:

- messages can arrive while the mobile app is foregrounded and its WebSocket is connected;
- background/closed-app push notifications are not currently available in the OSS mobile client;
- seeing `push` in the relay's NIP-11 document or `NIP-PL push matcher and delivery worker started` in logs does not prove a phone is registered;
- self-hosting `buzz-push-gateway` alone does not fix this; it also requires Apple APNs/App Attest credentials and matching client implementation;
- Android cannot enable push from system settings because the current app manifest lacks `android.permission.POST_NOTIFICATIONS`, the app has no Firebase Messaging integration, and the gateway is APNs-specific. The NIP-PL draft explicitly defines FCM as a future, non-conforming v1 profile.

Useful checks:

```bash
curl -fsS -H 'Accept: application/nostr+json' https://buzz.example.com/ | jq .push
# Server capability only; not evidence of a registered device.

# Run against the relay PostgreSQL database.
psql "$DATABASE_URL" -Atc 'select count(*) from push_leases'
# Zero means no mobile endpoint lease exists, so no push can be matched.
```

Official evidence: [README implementation status](https://github.com/block/buzz/blob/main/README.md#works-today--being-wired-up--strong-opinions-pending-code), [push gateway deployment, relay integration status](https://github.com/block/buzz/blob/main/docs/push-gateway-deployment.md#relay-integration-status), and [NIP-PL FCM status](https://github.com/block/buzz/blob/main/docs/nips/NIP-PL.md#fcm).

## Railway

Use upstream’s [Railway template](https://railway.com/deploy/buzz-relay-block) and [operator article](https://engineering.block.xyz/blog/run-your-own-buzz-relay). Verify current template variables rather than translating old Compose settings blindly.

## Kubernetes / Helm

Follow the chart README and pin a chart version shown by the registry/current docs:

```bash
helm install buzz oci://ghcr.io/block/buzz/charts/buzz --version <chart-version> \
  --create-namespace --namespace buzz \
  --set quickstart=true \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set minio.enabled=true \
  --set relayUrl=wss://buzz.example.com \
  --set ownerPubkey=<64-char-hex-pubkey>
```

Quickstart is evaluation-only. Production/GitOps must use managed Postgres/Redis/S3 and `secrets.existingSecret`. Do not use chart-generated secrets under ArgoCD/Flux because template rendering can regenerate them.

For `replicaCount > 1`, Redis is mandatory for fan-out. Use correct S3 addressing style (`path` for typical MinIO; `virtual` for AWS-style providers when required).

## Agent harness operation

Official docs: [buzz-acp README](https://github.com/block/buzz/blob/main/crates/buzz-acp/README.md).

Each agent needs a unique keypair, relay membership, and channel membership.

```bash
cargo build --release -p buzz-acp -p buzz-admin -p buzz-cli
export PATH="$PWD/target/release:$PATH"
export BUZZ_PRIVATE_KEY="nsec1..."          # not BUZZ_ACP_PRIVATE_KEY, which does not exist
export BUZZ_RELAY_URL="ws://localhost:3000"
export BUZZ_ACP_AGENT_OWNER="<64-char-hex>" # required by the default owner-only author gate
buzz-acp
```

`BUZZ_ACP_RESPOND_TO` defaults to `owner-only`, gated on `BUZZ_ACP_AGENT_OWNER`. Get that pubkey
wrong or leave it unset and the agent starts cleanly, joins channels, shows presence — and silently
drops every message. Use `allowlist` with `BUZZ_ACP_RESPOND_TO_ALLOWLIST` to admit a bounded set of
people; reserve `anyone` for a closed relay where membership is already the gate.

Use one of the supported ACP adapters and verify current installation instructions in the ACP README. Multiple workers share one public agent identity; per-channel serialization remains enforced. Start with low concurrency and increase only from observed queue pressure.

Owner control messages, when properly authored and mentioned, include `!cancel`, `!rotate`, and `!shutdown`. Confirm current semantics in the ACP README before use.

Anything beyond one agent on your own machine — the other three delivery gates, duplicate replies,
agents invisible in autocomplete, supervision, agent-created agents — is in
[agent-fleet.md](agent-fleet.md).

## Monitoring and troubleshooting

Layered checks:

```bash
# process/container
./run.sh status
./run.sh logs relay

# probes
curl -fsS https://buzz.example.com/health
curl -fsS http://127.0.0.1:8080/_readiness

# relay metadata
curl -fsS https://buzz.example.com/info | jq .

# signed functional check
buzz channels list | jq .
```

Common causes:

- `Address already in use`: inspect relay, health, and metrics ports separately.
- auth failure: wrong/stale `BUZZ_PRIVATE_KEY`, `BUZZ_AUTH_TAG`, owner attestation, or membership.
- empty ACP subscriptions: agent lacks channel membership or author/mention gate blocks events.
- storage startup failure: wrong S3 endpoint, bucket, region, credentials, or addressing style.
- stale behavior after changes: wrong binary/profile or unrestarted relay.
- cross-community confusion: wrong host/relay URL; URL is authoritative workspace selector.

## Backups and upgrades

Before upgrade, back up from one consistent maintenance window:

1. deployment `.env` / Kubernetes Secret material;
2. owner private key and relay identity key;
3. Postgres database;
4. S3/MinIO bucket contents;
5. git state/volume where applicable;
6. Caddy state if using bundled TLS.

Then validate rendered config, pull pinned artifacts, migrate according to deployment policy, restart, check probes, and run a signed read/write smoke test. Key rotation changes identity and can break trust; never treat it as routine restart maintenance.

Release operations are privileged and lane-specific. Read [RELEASING.md](https://github.com/block/buzz/blob/main/RELEASING.md) fully before desktop, relay, mobile, or chart publication.
