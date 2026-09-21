---
name: homeserver-deployment
description: Deploy a containerized service to the user's homeserver, accessible via Tailscale at a `<service>.homeserver` domain through Nginx Proxy Manager (NPM). Use when the user asks to "deploy to my homeserver", "expose this as <name>.homeserver", "set up homeserver deployment", or wants a new app routed through the existing NPM + Tailscale stack.
---

# Homeserver Deployment

This skill captures the exact pattern the user uses to deploy small services to
their personal homeserver. Every deployment looks the same:

1. **Build a self-contained Docker image locally** (any architecture — the
   script auto-detects the homeserver's arch and builds the right platform).
2. **Save it as `tar.gz` and `scp` it to the homeserver** via the SSH alias
   `homeserver`.
3. **Load the image on the homeserver and start a `docker compose` stack**
   that attaches the service container to the **external `system_default`**
   docker network — that is the network **Nginx Proxy Manager (NPM)** owns.
4. **Route `<service>.homeserver` through NPM** to `<container>:<port>`. The
   homeserver is reachable from the user's devices over **Tailscale**, so
   `<service>.homeserver` resolves only on the tailnet.

Persistent data lives on a **named docker volume** on the homeserver. Compose
files never bind-mount paths from the local repo for storage — that would
disappear on redeploy.

## When to use

Trigger this skill when the user says any of:

- "Deploy [this app] to my homeserver"
- "Set up a homeserver deployment for X"
- "Make it accessible at `<something>.homeserver`"
- "Add a `just deploy-homeserver` recipe"
- "Route this through NPM on the homeserver"

If the user asks to deploy to "AWS", "EC2", "Render", "Vercel", anywhere
public, or anything implying a real DNS name — **do not use this skill**.
The `.homeserver` TLD only resolves on the tailnet.

## Prerequisites the user has already set up

Assume the user already has, and do not re-explain:

- **Tailscale** installed on their laptop and the homeserver, with the
  homeserver reachable on the tailnet.
- **SSH config alias** `homeserver` in `~/.ssh/config` pointing at the
  homeserver's tailnet IP with key-based auth.
- **Docker** + **docker compose** v2 on the homeserver.
- **Nginx Proxy Manager** running on the homeserver, owning the docker
  network **`system_default`**. New service containers attach to that
  network to be reachable by NPM.
- **MagicDNS / split-DNS for `.homeserver`** — the user's devices resolve
  `<name>.homeserver` to the homeserver's tailnet IP, which is what NPM
  terminates.

Verify the SSH alias works before starting:

```bash
ssh homeserver "echo ok"
```

If that fails, stop and ask the user to fix `~/.ssh/config`. Do not invent
hostnames or IPs.

## What you create

For a project that does not have a homeserver deployment yet, generate
these files (paths shown relative to the project root):

```
Dockerfile.<service>                       # self-contained image for the service
.dockerignore                              # excludes caches/DBs/secrets from the build context
docker-compose.homeserver.yml              # one-service compose, attaches to system_default
deployments/homeserver/env.homeserver      # env vars for the service container
deployments/homeserver/info.yml            # metadata: SSH alias, domain, container name, port
scripts/deploy-homeserver.sh               # the deploy script (executable)
```

And add to the project's `justfile`:

```just
# Deploy <project> to the homeserver via the `homeserver` SSH alias.
deploy-homeserver *args:
    @bash scripts/deploy-homeserver.sh {{ args }}
```

Use the templates in `templates/` as the starting point — they encode every
default the user has settled on (network name, NPM hint, healthcheck
shape, `~/<service>` remote dir, etc.). Substitute the placeholders for the
specific project you are deploying.

### Placeholders to replace in templates

| Placeholder         | Meaning                                              | Example                                |
|---------------------|------------------------------------------------------|----------------------------------------|
| `__SERVICE__`       | short kebab-case service name; also the image prefix | `ro-collector`, `ia-backend`           |
| `__SERVICE_DIR__`   | remote deploy dir under `$HOME` on the homeserver    | `runtime-observer`, `internal-assistant` |
| `__DOMAIN__`        | tailnet domain NPM proxies to the container          | `metrics.homeserver`, `mordecai.homeserver` |
| `__CONTAINER__`     | the docker container name (NPM forward hostname)     | `ro-collector`                         |
| `__PORT__`          | the port the service listens on inside the container | `4319`, `9020`                          |
| `__IMAGE__`         | the docker image tag (typically `__CONTAINER__:latest`) | `ro-collector:latest`              |
| `__VOLUME__`        | named volume for persistent data, or empty           | `collector_data`                       |

## Workflow

Follow these phases in order. Confirm with the user at the checkpoints.

### Phase 1 — Gather details

Ask the user, only what you can't derive:

1. **Service name** (kebab-case). Used for the container, image, and remote
   dir. Default to the project's package name if obvious.
2. **Public domain** under `.homeserver`. Default to `<service>.homeserver`.
3. **Listen port** inside the container.
4. **Persistent data?** SQLite / disk cache / uploads → name a docker volume
   and the mount path. If purely stateless, no volume.
5. **Database?** If the service needs Postgres/Redis/etc., decide whether to
   add it as a second compose service on a private `__SERVICE__-network` or
   reuse an existing one on the homeserver. Most small apps don't need this.

**CHECKPOINT** — repeat back the chosen values before generating files.

### Phase 2 — Build the image

The image **must be self-contained** — no `pip install` at container start,
no source bind-mounts for code. The build-and-ship-the-tar pattern means a
flaky network on the homeserver doesn't break the deploy.

Copy `templates/Dockerfile.service` and adapt:

- Choose an appropriate base image for the runtime.
- `COPY` only the directories that contain source — do NOT `COPY . .`. The
  `.dockerignore` is a safety net, not a strategy.
- Install dependencies in their own layer for caching.
- Expose `__PORT__`.
- Add a `HEALTHCHECK` that hits the service's own health route on
  `127.0.0.1:__PORT__`.

### Phase 3 — Compose file

Use `templates/docker-compose.homeserver.yml`:

- One service named after the image (`__SERVICE__`).
- `container_name: __CONTAINER__` so NPM has a stable forward hostname.
- `env_file: ./deployments/homeserver/env.homeserver` (the deploy script
  mirrors this path on the homeserver).
- Persistent state → named docker volume, never a bind mount.
- **No host port mapping.** Traffic enters through NPM via `system_default`.
- `networks: [__SERVICE__-network, system_default]`.
- `system_default` declared `external: true` at the bottom.

### Phase 4 — Env file

`deployments/homeserver/env.homeserver` lists every runtime env var the
service needs. Rules:

- **No `INSECURE_DEV` style flags.** Production-style defaults only.
- **No secrets in plaintext** if you can avoid it. If a secret is needed
  (DB password, API key), prompt the user for it and inject it via the
  `.env` file the deploy script writes, not the committed `env.homeserver`.
- Reference paths inside the container, not on the host (`/data/...`,
  `/var/lib/...`).

### Phase 5 — `info.yml`

A small metadata file the deploy script can read (or that you, the agent,
read on the next session). See `templates/info.yml`.

### Phase 6 — Deploy script

Copy `templates/deploy-homeserver.sh` and substitute placeholders. The
script does:

1. Verify Docker is running locally.
2. `ssh homeserver "echo ok"` — fail fast on a bad SSH config.
3. `uname -m` on the homeserver, pick `linux/amd64` vs `linux/arm64`.
4. Check Docker is running on the homeserver.
5. **Verify the `system_default` network exists** on the homeserver. If
   it doesn't, fail with a helpful message — that network is owned by NPM
   and the user has to start NPM first.
6. `docker build --platform $PLATFORM -f Dockerfile.<service> -t __IMAGE__ .`
7. `docker save | gzip > $TMPDIR/<service>.tar.gz`
8. `mkdir -p ~/<service>/deployments/homeserver` on the homeserver, scp
   the compose file, `.env`, and `env.homeserver` over (preserve the
   `deployments/homeserver/` path so `env_file` resolves identically).
9. `docker compose down --remove-orphans` on the homeserver (with
   `--volumes` only when `--clean-volume` is passed).
10. `docker image prune -af` on the homeserver to reclaim disk.
11. scp the image tar, `docker load`, delete the tar.
12. `docker compose up -d`.
13. Wait up to ~120s for the healthcheck (`docker exec ... curl http://127.0.0.1:<port>/`).
14. Print the NPM configuration hint at the end, with the exact `Domain`,
    `Forward Hostname`, `Forward Port`, `Websockets: ON`.

Always make the script executable (`chmod +x`) after writing it.

### Phase 7 — Wire it into `just`

Add `just deploy-homeserver` (see snippet in “What you create”). Verify
the recipe is reachable with `just --list`.

### Phase 8 — Hand off

**Do not run `just deploy-homeserver` yourself.** The build is multi-minute
and the script will issue many `ssh homeserver ...` calls that the user
must approve in the harness. Tell the user:

```
Deployment files are ready. Run `just deploy-homeserver` to deploy.
After it finishes, configure NPM with the values printed at the end of the script:
  Domain:           __DOMAIN__
  Scheme:           http
  Forward Hostname: __CONTAINER__
  Forward Port:     __PORT__
  Websockets:       ON
SSL: Let's Encrypt cannot validate `.homeserver` because the TLD has no
public DNS. Use NPM's self-signed certificate, install a tailnet-internal
CA cert, or use Tailscale Serve for trusted HTTPS on the tailnet.
```

## Defaults the user has already chosen — do not relitigate

- **SSH alias**: `homeserver`. Never invent another one.
- **External network for NPM**: `system_default`. Don't propose a different
  name.
- **Remote dir**: `~/<service>` on the homeserver. Don't put things under
  `/opt`, `/srv`, or `/var/www`.
- **Image build target**: build on the laptop, ship a tarball. Do not push
  to a registry or pull on the homeserver.
- **Compose v2**: use `docker compose` (no hyphen).
- **No host port exposure**. NPM is the only ingress.
- **HTTP behind NPM**. NPM terminates TLS upstream; the container speaks
  plain HTTP on `__PORT__`.

## Anti-patterns

Things that look reasonable but break the user's setup — refuse them:

- **`pip install -e .` at container start** (or `npm install`, etc.). Flaky,
  and was the explicit reason for switching to self-contained images.
- **Bind-mounting source code for production**. Code lives in the image.
- **`ports: ["__PORT__:__PORT__"]` on the homeserver host**. Don't expose
  service ports to the host; NPM handles ingress.
- **Marketing pages, landing pages, "coming soon" stubs**. The user has
  explicit feedback ([[feedback_no_landing_pages]]) that UI work means
  editing the real app, not building a static site.
- **Inventing install commands or SDK URLs** for a service you haven't
  inspected. Read the project's source first.
- **Using `host.docker.internal`**. Doesn't behave the same on the
  homeserver host as on macOS Docker Desktop.
- **Auto-running the deploy** at the end of a session. The user wants to
  trigger it themselves.

## Cross-references

- The `runtime-observer-product` repo has the canonical worked example of
  this pattern at:
    - `Dockerfile.collector`
    - `docker-compose.homeserver.yml`
    - `deployments/homeserver/{env.homeserver, info.yml}`
    - `scripts/deploy-homeserver.sh`
    - `just deploy-homeserver` recipe
- The `internal-assistant` (path: `~/Work/Sela/ai_tools/interanl-assistant`)
  repo has the original implementation that this skill generalizes. Look
  there for a two-service variant (backend + client behind nginx) if the
  current project needs both an API and a SPA frontend.
