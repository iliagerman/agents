#!/usr/bin/env python3
"""Runtime Observer agent client.

A tiny CLI that wraps the Runtime Observer agent API. Pure standard library —
no `pip install` required. Uses `urllib.request` for HTTP and prints JSON.

Authentication
--------------
Every call needs a project API key. The script reads it from, in order:
    1. The `--api-key` flag
    2. The `RUNTIME_OBSERVER_API_KEY` env var

Collector URL (default `http://localhost:4319`) can be overridden with:
    --url <http://host:port>
    or RUNTIME_OBSERVER_URL=<http://host:port>

Subcommands
-----------
General
    info                                       project + apps the key can see
    overview [--window-minutes N] [--log-limit N]

Apps & routes
    apps
    routes [--app-id ID] [--with-errors]

Traces
    traces [--app-id ID] [--route-id ID] [--has-error true|false]
           [--start ISO] [--end ISO] [--limit N]
    trace <trace-id> [--slim]
    trace-context <trace-id> [--format markdown|json]

Logs
    logs [--app-id ID] [--trace-id ID] [--route-id ID]
         [--level LEVEL] [--logger NAME] [--text SUBSTR]
         [--start ISO] [--end ISO] [--limit N]
    log <log-id> [--window-seconds N] [--nearby-limit N]
    search <query> [--level LEVEL] [--app-id ID]
                   [--window-minutes N] [--limit N]

Errors / exceptions
    exceptions [--app-id ID] [--type NAME] [--limit N]
    exception <id> [--no-trace]
    errors-summary [--app-id ID] [--window-minutes N]
    errors-timeline [--app-id ID] [--window-minutes N] [--bucket-minutes N]

Dependencies & LLM
    dependencies [--app-id ID] [--type db|http|llm]
                 [--target SUBSTR] [--with-errors] [--limit N]
    dependency <id> [--sample-limit N]
    llm-usage [--app-id ID] [--group-by model|provider]

Metrics
    metrics [--app-id ID] [--window-minutes N] [--bucket-minutes N]

Output is raw JSON on stdout (pretty when run from a TTY).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_URL = "http://localhost:4319"


def _resolve_auth(args: argparse.Namespace) -> tuple[str, str]:
    url = (args.url or os.environ.get("RUNTIME_OBSERVER_URL") or DEFAULT_URL).rstrip("/")
    api_key = args.api_key or os.environ.get("RUNTIME_OBSERVER_API_KEY")
    if not api_key:
        sys.exit(
            "error: project API key required — pass --api-key or set RUNTIME_OBSERVER_API_KEY.\n"
            "       Generate one in the dashboard under Projects → API keys."
        )
    return url, api_key


def _get(url: str, api_key: str, path: str, params: dict[str, object] | None = None) -> object:
    query = ""
    if params:
        filtered = {key: value for key, value in params.items() if value is not None}
        if filtered:
            query = "?" + urllib.parse.urlencode(filtered, doseq=True)
    request = urllib.request.Request(
        url + path + query,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
            detail = payload.get("detail") or detail
        except json.JSONDecodeError:
            pass
        sys.exit(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"network error: {exc.reason}")


def _print(value: object) -> None:
    indent = 2 if sys.stdout.isatty() else None
    json.dump(value, sys.stdout, indent=indent, ensure_ascii=False)
    sys.stdout.write("\n")


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {value!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="observer", description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", help=f"Collector base URL (default {DEFAULT_URL})")
    parser.add_argument("--api-key", help="Project API key (or set RUNTIME_OBSERVER_API_KEY)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Project + apps the key can see")

    overview = sub.add_parser("overview", help="Project-wide overview")
    overview.add_argument("--window-minutes", type=int, default=60)
    overview.add_argument("--log-limit", type=int, default=100)

    sub.add_parser("apps", help="List apps in the project")

    routes = sub.add_parser("routes", help="List HTTP routes")
    routes.add_argument("--app-id")
    routes.add_argument("--with-errors", action="store_true")
    routes.add_argument("--limit", type=int, default=100)

    traces = sub.add_parser("traces", help="List recent traces")
    traces.add_argument("--app-id")
    traces.add_argument("--route-id")
    traces.add_argument("--has-error", type=_bool)
    traces.add_argument("--start", help="ISO timestamp lower bound")
    traces.add_argument("--end", help="ISO timestamp upper bound")
    traces.add_argument("--limit", type=int, default=50)

    trace = sub.add_parser("trace", help="Get full trace detail")
    trace.add_argument("trace_id")
    trace.add_argument("--slim", action="store_true", help="Skip events/timeline/dependencies")

    trace_context = sub.add_parser("trace-context", help="Markdown context for an LLM")
    trace_context.add_argument("trace_id")
    trace_context.add_argument("--format", choices=["markdown", "json"], default="markdown")

    logs = sub.add_parser("logs", help="Search logs")
    logs.add_argument("--app-id")
    logs.add_argument("--trace-id")
    logs.add_argument("--route-id")
    logs.add_argument("--level")
    logs.add_argument("--logger")
    logs.add_argument("--text", help="Substring match on message")
    logs.add_argument("--start")
    logs.add_argument("--end")
    logs.add_argument("--limit", type=int, default=200)

    log_detail = sub.add_parser("log", help="Single log + nearby context")
    log_detail.add_argument("log_id")
    log_detail.add_argument("--window-seconds", type=int, default=60)
    log_detail.add_argument("--nearby-limit", type=int, default=50)

    search = sub.add_parser("search", help="Free-text search across logs (+ exceptions)")
    search.add_argument("query")
    search.add_argument("--level")
    search.add_argument("--app-id")
    search.add_argument("--window-minutes", type=int, default=1440)
    search.add_argument("--limit", type=int, default=200)

    exceptions = sub.add_parser("exceptions", help="List exception clusters")
    exceptions.add_argument("--app-id")
    exceptions.add_argument("--type")
    exceptions.add_argument("--limit", type=int, default=50)

    exception = sub.add_parser("exception", help="Single exception cluster with trace")
    exception.add_argument("exception_id")
    exception.add_argument("--no-trace", action="store_true")

    errors_summary = sub.add_parser("errors-summary", help="Aggregated error counts")
    errors_summary.add_argument("--app-id")
    errors_summary.add_argument("--window-minutes", type=int, default=60)

    errors_timeline = sub.add_parser("errors-timeline", help="Exception count per time bucket")
    errors_timeline.add_argument("--app-id")
    errors_timeline.add_argument("--window-minutes", type=int, default=1440)
    errors_timeline.add_argument("--bucket-minutes", type=int, default=15)

    deps = sub.add_parser("dependencies", help="DB / HTTP / LLM dependency map")
    deps.add_argument("--app-id")
    deps.add_argument("--type", dest="dependency_type", choices=["db", "http", "llm"])
    deps.add_argument("--target", help="Substring match on target")
    deps.add_argument("--with-errors", action="store_true")
    deps.add_argument("--limit", type=int, default=100)

    dep = sub.add_parser("dependency", help="Sample calls for a single dependency")
    dep.add_argument("dependency_id")
    dep.add_argument("--sample-limit", type=int, default=20)

    llm = sub.add_parser("llm-usage", help="LLM token / call usage")
    llm.add_argument("--app-id")
    llm.add_argument("--group-by", choices=["model", "provider"], default="model")

    metrics = sub.add_parser("metrics", help="Time-bucketed request / log / exception counts")
    metrics.add_argument("--app-id")
    metrics.add_argument("--window-minutes", type=int, default=1440)
    metrics.add_argument("--bucket-minutes", type=int, default=15)

    return parser


def dispatch(args: argparse.Namespace) -> object:
    url, api_key = _resolve_auth(args)
    cmd = args.cmd
    if cmd == "info":
        return _get(url, api_key, "/v1/agent/info")
    if cmd == "overview":
        return _get(url, api_key, "/v1/agent/overview", {"log_window_minutes": args.window_minutes, "log_limit": args.log_limit})
    if cmd == "apps":
        return _get(url, api_key, "/v1/agent/apps")
    if cmd == "routes":
        return _get(url, api_key, "/v1/agent/routes", {"app_id": args.app_id, "with_errors_only": args.with_errors, "limit": args.limit})
    if cmd == "traces":
        return _get(url, api_key, "/v1/agent/traces", {"app_id": args.app_id, "route_id": args.route_id, "has_error": args.has_error, "start": args.start, "end": args.end, "limit": args.limit})
    if cmd == "trace":
        return _get(url, api_key, f"/v1/agent/traces/{args.trace_id}", {"slim": args.slim})
    if cmd == "trace-context":
        return _get(url, api_key, f"/v1/agent/traces/{args.trace_id}/context", {"format": args.format})
    if cmd == "logs":
        return _get(url, api_key, "/v1/agent/logs", {"app_id": args.app_id, "trace_id": args.trace_id, "route_id": args.route_id, "level": args.level, "logger": args.logger, "text": args.text, "start": args.start, "end": args.end, "limit": args.limit})
    if cmd == "log":
        return _get(url, api_key, f"/v1/agent/logs/{args.log_id}", {"window_seconds": args.window_seconds, "nearby_limit": args.nearby_limit})
    if cmd == "search":
        return _get(url, api_key, "/v1/agent/search", {"q": args.query, "level": args.level, "app_id": args.app_id, "window_minutes": args.window_minutes, "limit": args.limit})
    if cmd == "exceptions":
        return _get(url, api_key, "/v1/agent/exceptions", {"app_id": args.app_id, "type": args.type, "limit": args.limit})
    if cmd == "exception":
        return _get(url, api_key, f"/v1/agent/exceptions/{args.exception_id}", {"include_trace": not args.no_trace})
    if cmd == "errors-summary":
        return _get(url, api_key, "/v1/agent/errors/summary", {"app_id": args.app_id, "window_minutes": args.window_minutes})
    if cmd == "errors-timeline":
        return _get(url, api_key, "/v1/agent/errors/timeline", {"app_id": args.app_id, "window_minutes": args.window_minutes, "bucket_minutes": args.bucket_minutes})
    if cmd == "dependencies":
        return _get(url, api_key, "/v1/agent/dependencies", {"app_id": args.app_id, "dependency_type": args.dependency_type, "target": args.target, "with_errors_only": args.with_errors, "limit": args.limit})
    if cmd == "dependency":
        return _get(url, api_key, f"/v1/agent/dependencies/{args.dependency_id}", {"sample_limit": args.sample_limit})
    if cmd == "llm-usage":
        return _get(url, api_key, "/v1/agent/llm-usage", {"app_id": args.app_id, "group_by": args.group_by})
    if cmd == "metrics":
        return _get(url, api_key, "/v1/agent/metrics/timeseries", {"app_id": args.app_id, "window_minutes": args.window_minutes, "bucket_minutes": args.bucket_minutes})
    raise SystemExit(f"unknown command: {cmd}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _print(dispatch(args))


if __name__ == "__main__":
    main()
