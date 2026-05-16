---
name: runtime-observer
description: Inspect logs, traces, errors, dependencies, and metrics from a Runtime Observer collector using a project API key. Use when debugging a running application that ships telemetry to a Runtime Observer collector, investigating an incident, hunting a slow route, finding a failing dependency, or building a postmortem from production data.
version: 1.0.0
requires:
  bins:
    - python3
  env:
    - name: RUNTIME_OBSERVER_API_KEY
      prompt: "Provide a Runtime Observer **project** API key (generated in the dashboard under Projects → API keys). The legacy collector-wide admin key is rejected by the agent API on purpose — agents are always project-scoped."
      example: "ro_a1b2c3d4_abcdefghijklmnopqrstuvwx"
    - name: RUNTIME_OBSERVER_URL
      prompt: "Collector base URL. Default is http://localhost:4319 when running locally; in deployed environments use the public host (e.g. https://observer.acme.com)."
      example: "http://localhost:4319"
---

# Runtime Observer Agent Skill

This skill lets an autonomous agent debug an application by reading from a
Runtime Observer collector. The agent uses the same authentication model as
the SDK — a **project API key** generated in the dashboard — and is scoped
to that single project. No SDK install is required; everything goes over
HTTP with the standard library.

## When to use

Use this skill whenever you need to inspect what a running application is
actually doing. Concretely:

- A user says "the app is broken / slow / returning 500s" and you have a
  Runtime Observer collector that ingests its telemetry.
- You want to chase down a specific trace, log line, or exception.
- You're auditing dependencies (database queries, HTTP clients, LLM calls)
  for errors, slowness, or N+1 patterns.
- You're building a postmortem / writing a fix and need primary evidence
  (real traces and logs) instead of guessing.

## Setup checklist

Before issuing any command:

1. **Get a project API key.** In the dashboard go to Projects → pick a
   project → API keys → Generate. Copy the `ro_...` token immediately
   (it is shown once). Set it as `RUNTIME_OBSERVER_API_KEY`.
2. **Set the collector URL.** Local dev defaults to `http://localhost:4319`.
   Override with `RUNTIME_OBSERVER_URL` for staging / production.
3. **Confirm connectivity.** Run the `info` command — it returns the
   project name and the apps reporting into it. A 401 means the key is
   wrong, revoked, or you accidentally pasted the legacy admin key (the
   agent API rejects that key on purpose).

The two helper scripts live under this skill's `scripts/` directory:

- `observer.py` — single-file CLI wrapping every endpoint.
- `observer_client.py` — importable Python class (`ObserverClient`) for
  use inside your own scripts.

Both are pure stdlib (`urllib.request`, `argparse`, `json`). No `pip
install` step.

## How to run the CLI

Locate the attached absolute path that ends in `/scripts/observer.py` and
run it with the system Python:

```bash
export RUNTIME_OBSERVER_URL="http://localhost:4319"
export RUNTIME_OBSERVER_API_KEY="ro_xxxxxxxx_xxxxxxxxxxxxxxxxxxxx"

OBSERVER="/absolute/path/from-attached-files/scripts/observer.py"

python3 "$OBSERVER" info
python3 "$OBSERVER" overview --window-minutes 30
python3 "$OBSERVER" traces --has-error true --limit 5
python3 "$OBSERVER" trace <trace-id>
python3 "$OBSERVER" trace-context <trace-id>            # markdown for an LLM
python3 "$OBSERVER" logs --level ERROR --text "timeout"
python3 "$OBSERVER" exceptions --limit 10
python3 "$OBSERVER" exception <exception-id>
python3 "$OBSERVER" dependencies --type db --with-errors
python3 "$OBSERVER" dependency <dependency-id>
python3 "$OBSERVER" llm-usage --group-by model
python3 "$OBSERVER" metrics --window-minutes 360 --bucket-minutes 5
python3 "$OBSERVER" search "NullPointer" --window-minutes 4320
```

Output is JSON on stdout. Pretty-printed when stdout is a TTY, compact
otherwise — pipe it into `jq` or `python3 -c '…'` for further filtering.

## How to use as a library

For multi-step investigations (correlate a log → its trace → upstream
dependencies → similar errors elsewhere) the library form is friendlier
than chaining CLI calls.

```python
import sys
sys.path.insert(0, "/absolute/path/from-attached-files/scripts")
from observer_client import ObserverClient, ObserverError

client = ObserverClient()  # reads RUNTIME_OBSERVER_URL + RUNTIME_OBSERVER_API_KEY

# 1. What apps are in this project?
info = client.info()
print(info["project_name"], [app["service_name"] for app in info["apps"]])

# 2. Which routes are erroring right now?
broken = client.routes(with_errors_only=True)
for route in broken[:5]:
    print(route["method"], route["route_pattern"], "errors:", route["error_count"])

# 3. Pull a failing trace end to end.
failing_traces = client.traces(has_error=True, limit=3)
for trace in failing_traces:
    full = client.trace(trace["id"])
    print(trace["id"], full["trace"]["status_code"], len(full["events"]), "events")

# 4. Hand a single trace to an LLM as markdown context.
context = client.trace_context(failing_traces[0]["id"], format="markdown")
prompt = context["text"]
```

`ObserverClient` raises `ObserverError` on HTTP failures so your script
can handle 401/404 explicitly.

## Endpoint reference

All endpoints are `GET` under `/v1/agent/*`, project-scoped by the API
key. CamelCase / snake_case: query parameters are `snake_case`.

### Discovery

| Command | Endpoint | Notes |
|---|---|---|
| `info` | `/v1/agent/info` | Project name, apps, server time. |
| `apps` | `/v1/agent/apps` | All apps in the project. |
| `overview` | `/v1/agent/overview` | Totals + recent errors/logs + hot routes. `--window-minutes` (default 60), `--log-limit` (default 100). |

### Routes & traces

| Command | Endpoint | Useful parameters |
|---|---|---|
| `routes` | `/v1/agent/routes` | `--app-id`, `--with-errors`, `--limit`. |
| `traces` | `/v1/agent/traces` | `--app-id`, `--route-id`, `--has-error`, `--start`, `--end`, `--limit`. |
| `trace <id>` | `/v1/agent/traces/{trace_id}` | Full trace: events, spans, logs, exceptions, timeline, dependency groups, slow-gap markers, duplicate candidates. Add `--slim` to skip event/timeline payloads. |
| `trace-context <id>` | `/v1/agent/traces/{trace_id}/context` | Markdown summary (default) or raw JSON (`--format json`) for LLM consumption. |

### Logs

| Command | Endpoint | Useful parameters |
|---|---|---|
| `logs` | `/v1/agent/logs` | `--app-id`, `--trace-id`, `--route-id`, `--level INFO/WARN/ERROR/...`, `--logger`, `--text` (substring), `--start`, `--end`, `--limit` (default 200, max 1000). |
| `log <id>` | `/v1/agent/logs/{log_id}` | Single log + same-project nearby logs (`--window-seconds`, `--nearby-limit`) + slim trace context if the log has a `trace_id`. |
| `search <q>` | `/v1/agent/search` | Free-text search across log `message` (and exception `normalized_message`). `--window-minutes` defaults to 1440 — bump it for older incidents. |

### Errors

| Command | Endpoint | Useful parameters |
|---|---|---|
| `exceptions` | `/v1/agent/exceptions` | Clusters (deduped by fingerprint). `--app-id`, `--type ValueError`, `--limit`. |
| `exception <id>` | `/v1/agent/exceptions/{id}` | Cluster + sample trace + same-trace logs. `--no-trace` to skip the trace body. |
| `errors-summary` | `/v1/agent/errors/summary` | Totals, top types, top services. `--window-minutes`. |
| `errors-timeline` | `/v1/agent/errors/timeline` | Time-bucketed exception counts. `--window-minutes`, `--bucket-minutes`. |

### Dependencies & LLM

| Command | Endpoint | Useful parameters |
|---|---|---|
| `dependencies` | `/v1/agent/dependencies` | `--type db/http/llm`, `--target` (substring), `--with-errors`, `--limit`. |
| `dependency <id>` | `/v1/agent/dependencies/{id}` | Recent + error samples for one dependency (includes parsed payload for each call). `--sample-limit` (default 20). |
| `llm-usage` | `/v1/agent/llm-usage` | Token / call totals. `--group-by model` (default) or `provider`. |

### Metrics

| Command | Endpoint | Useful parameters |
|---|---|---|
| `metrics` | `/v1/agent/metrics/timeseries` | Per-bucket request counts, request errors, average duration, log totals, error log totals, exception count. `--window-minutes`, `--bucket-minutes`. |

## Common debugging recipes

### A. "What broke in the last hour?"

```bash
python3 "$OBSERVER" overview --window-minutes 60
python3 "$OBSERVER" errors-summary --window-minutes 60
python3 "$OBSERVER" exceptions --limit 5
```

Read `overview.totals` for shape, then `errors-summary.by_type` and
`by_service` to see what's loudest, then `exceptions` to drill into a
specific cluster.

### B. "Diagnose this failing HTTP request"

If the user gives you a trace id (visible in the dashboard, response
headers, or log lines):

```bash
python3 "$OBSERVER" trace <trace-id>
python3 "$OBSERVER" trace-context <trace-id>          # markdown for prompting
```

The trace response includes `events`, `spans`, `dependencies`,
`exceptions`, `timeline`, plus pre-computed analyses:

- `dependency_groups` — how many DB / HTTP / LLM calls per signature.
- `duplicate_candidates` — same dependency invoked >1 time (cheap N+1 hint).
- `relationship_loader_groups` — ORM lazy-load patterns.
- `slow_gap_markers` — time gaps between events that exceed the slow
  threshold for this trace (good for spotting "blocked on something
  external").

### C. "Find the trace for a log line"

Logs include their `trace_id`. Once you have a log id (e.g. from search
results or recent_logs), fetch the log with nearby context — it bundles
the trace and surrounding logs automatically:

```bash
python3 "$OBSERVER" search "OperationalError" --window-minutes 4320
# pick a log id from the response, then:
python3 "$OBSERVER" log <log-id>
```

### D. "Is the database slow?"

```bash
python3 "$OBSERVER" dependencies --type db --with-errors
python3 "$OBSERVER" dependency <dependency-id> --sample-limit 30
```

`dependency` returns parsed payloads with `duration_ms`, `operation`,
`statement_fingerprint`, etc. The `error_samples` list filters to calls
with errors / 4xx-5xx status / `error_type` populated.

### E. "Why did this exception happen?"

```bash
python3 "$OBSERVER" exceptions --type "ValueError"
# pick an exception id, then:
python3 "$OBSERVER" exception <exception-id>
```

The response embeds the sampled trace and same-trace logs so you can
read the full failure path in one call.

### F. "Is LLM cost / latency drifting?"

```bash
python3 "$OBSERVER" llm-usage --group-by model
python3 "$OBSERVER" metrics --window-minutes 1440 --bucket-minutes 60
```

`llm-usage` rolls up `call_count`, `input_tokens`, `output_tokens`, and
`error_count` per model (or provider). `metrics` gives time-bucketed
request volume / errors / avg duration alongside log + exception counts.

### G. "Run a Python investigation script"

A complete example you can adapt verbatim:

```python
#!/usr/bin/env python3
"""Quick triage: list the 5 worst routes and surface a recent failing trace for each."""
import sys
sys.path.insert(0, "/absolute/path/from-attached-files/scripts")
from observer_client import ObserverClient

client = ObserverClient()

for route in client.routes(with_errors_only=True, limit=5):
    print(f"\n# {route['method']} {route['route_pattern']}")
    print(f"  calls={route['call_count']} errors={route['error_count']} p95={route['p95_ms']}ms")
    failing = client.traces(route_id=route["id"], has_error=True, limit=1)
    if not failing:
        print("  (no failing trace currently retained)")
        continue
    trace = client.trace(failing[0]["id"])
    print(f"  trace {trace['trace_id']} status={trace['trace']['status_code']}")
    for exc in trace.get("exceptions", []):
        print(f"    ✗ {exc['type']}: {exc['normalized_message']}")
    for log in trace.get("logs", [])[-3:]:
        print(f"    log [{log['level']}] {log['message']}")
```

## Authentication & scope

- The agent API requires `Authorization: Bearer <project-api-key>`. The
  key is hashed at rest and the `last_used_at` timestamp is updated on
  every call so you can audit usage from the dashboard.
- Every endpoint is **scoped to one project** — there is no way to read
  data from another project with the same key.
- The collector-wide admin key (the one passed via `--api-key` to the
  collector itself, used historically for cross-project ingest) is
  rejected on the agent API with HTTP 401. Always use a project key.

## Limits & defaults

- `logs` default `limit=200`, max `1000`.
- `traces` default `limit=50`, max `500`.
- `search` defaults to a 24h window — bump `--window-minutes` for older
  incidents (max 30 days, `43200`).
- `errors-timeline` / `metrics` allow up to `bucket_minutes=1440` and
  `window_minutes=43200`.

## Failure modes & troubleshooting

| Symptom | Likely cause |
|---|---|
| `HTTP 401: Missing 'Authorization: Bearer …'` | The `RUNTIME_OBSERVER_API_KEY` env var is empty. |
| `HTTP 401: Invalid Runtime Observer API key` | Key revoked or wrong project key copied. Regenerate from the dashboard. |
| `HTTP 401: The collector-wide admin key cannot be used …` | You used the collector's ingest admin key; create a project key instead. |
| `HTTP 404` on `trace <id>` or `exception <id>` | Either the id doesn't exist, retention purged it, or it belongs to a different project. |
| Empty `logs` / `traces` response | Retention window probably trimmed older data. Widen `--window-minutes` (search) or check the collector's retention settings. |
| `network error: Connection refused` | Collector not running, or wrong `RUNTIME_OBSERVER_URL`. |

## Notes

- All timestamps are ISO 8601 UTC (`2026-05-09T20:00:00.000Z`).
- Telemetry payloads have already been redacted by the SDK and collector
  (bearer tokens, JWTs, AWS keys, password / secret / api_key fields).
  Treat residual values as low-trust but generally safe to include in
  agent context.
- These endpoints are **read-only**. The skill cannot modify anything in
  the collector, so it is safe to call freely during investigations.
