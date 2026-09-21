"""Tiny zero-dependency client for the Runtime Observer agent API.

Drop this file into any script directory and import it — it depends only
on the Python standard library. The collector's agent API lives at
`/v1/agent/*` and authenticates with a project API key.

Quick start
-----------

    from observer_client import ObserverClient

    client = ObserverClient(
        url="http://localhost:4319",
        api_key="ro_xxxxxxxx_xxxxxxxxxxxxxxxxxxxx",
    )

    apps = client.apps()
    failing = client.routes(with_errors_only=True)
    for trace in client.traces(has_error=True, limit=10):
        full = client.trace(trace["id"])
        print(full["trace_id"], len(full["events"]), "events")

Every method maps 1:1 to a `/v1/agent/*` endpoint and returns parsed JSON.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ObserverError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class ObserverClient:
    """Read-only client for the Runtime Observer agent API."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        resolved_url = url or os.environ.get("RUNTIME_OBSERVER_URL") or "http://localhost:4319"
        resolved_key = api_key or os.environ.get("RUNTIME_OBSERVER_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Runtime Observer project API key is required. "
                "Pass api_key=... or set RUNTIME_OBSERVER_API_KEY."
            )
        self.url = resolved_url.rstrip("/")
        self.api_key = resolved_key
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = ""
        if params:
            filtered = {key: value for key, value in params.items() if value is not None}
            if filtered:
                query = "?" + urllib.parse.urlencode(filtered, doseq=True)
        request = urllib.request.Request(
            self.url + path + query,
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(detail)
                detail = str(payload.get("detail") or detail)
            except json.JSONDecodeError:
                pass
            raise ObserverError(exc.code, detail) from exc

    # ------------ Project / discovery ------------
    def info(self) -> dict[str, Any]:
        """Project name, apps, server time. Cheapest health probe."""
        return self._get("/v1/agent/info")

    def apps(self) -> list[dict[str, Any]]:
        """Every app (service) reporting to this project."""
        return self._get("/v1/agent/apps")

    def overview(self, *, window_minutes: int = 60, log_limit: int = 100) -> dict[str, Any]:
        """High-level snapshot: totals, recent errors, recent logs, hot routes."""
        return self._get(
            "/v1/agent/overview",
            {"log_window_minutes": window_minutes, "log_limit": log_limit},
        )

    # ------------ Routes ------------
    def routes(
        self,
        *,
        app_id: str | None = None,
        with_errors_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/routes",
            {"app_id": app_id, "with_errors_only": with_errors_only, "limit": limit},
        )

    # ------------ Traces ------------
    def traces(
        self,
        *,
        app_id: str | None = None,
        route_id: str | None = None,
        has_error: bool | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/traces",
            {
                "app_id": app_id,
                "route_id": route_id,
                "has_error": has_error,
                "start": start,
                "end": end,
                "limit": limit,
            },
        )

    def trace(self, trace_id: str, *, slim: bool = False) -> dict[str, Any]:
        return self._get(f"/v1/agent/traces/{trace_id}", {"slim": slim})

    def trace_context(self, trace_id: str, *, format: str = "markdown") -> dict[str, Any]:
        return self._get(f"/v1/agent/traces/{trace_id}/context", {"format": format})

    # ------------ Logs ------------
    def logs(
        self,
        *,
        app_id: str | None = None,
        trace_id: str | None = None,
        route_id: str | None = None,
        level: str | None = None,
        logger: str | None = None,
        text: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/logs",
            {
                "app_id": app_id,
                "trace_id": trace_id,
                "route_id": route_id,
                "level": level,
                "logger": logger,
                "text": text,
                "start": start,
                "end": end,
                "limit": limit,
            },
        )

    def log(
        self,
        log_id: str,
        *,
        window_seconds: int = 60,
        nearby_limit: int = 50,
    ) -> dict[str, Any]:
        return self._get(
            f"/v1/agent/logs/{log_id}",
            {"window_seconds": window_seconds, "nearby_limit": nearby_limit},
        )

    def search(
        self,
        query: str,
        *,
        level: str | None = None,
        app_id: str | None = None,
        window_minutes: int = 1440,
        limit: int = 200,
    ) -> dict[str, Any]:
        return self._get(
            "/v1/agent/search",
            {
                "q": query,
                "level": level,
                "app_id": app_id,
                "window_minutes": window_minutes,
                "limit": limit,
            },
        )

    # ------------ Exceptions ------------
    def exceptions(
        self,
        *,
        app_id: str | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/exceptions",
            {"app_id": app_id, "type": type, "limit": limit},
        )

    def exception(self, exception_id: str, *, include_trace: bool = True) -> dict[str, Any]:
        return self._get(
            f"/v1/agent/exceptions/{exception_id}",
            {"include_trace": include_trace},
        )

    def errors_summary(
        self,
        *,
        app_id: str | None = None,
        window_minutes: int = 60,
    ) -> dict[str, Any]:
        return self._get(
            "/v1/agent/errors/summary",
            {"app_id": app_id, "window_minutes": window_minutes},
        )

    def errors_timeline(
        self,
        *,
        app_id: str | None = None,
        window_minutes: int = 1440,
        bucket_minutes: int = 15,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/errors/timeline",
            {
                "app_id": app_id,
                "window_minutes": window_minutes,
                "bucket_minutes": bucket_minutes,
            },
        )

    # ------------ Dependencies / LLM ------------
    def dependencies(
        self,
        *,
        app_id: str | None = None,
        dependency_type: str | None = None,
        target: str | None = None,
        with_errors_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/dependencies",
            {
                "app_id": app_id,
                "dependency_type": dependency_type,
                "target": target,
                "with_errors_only": with_errors_only,
                "limit": limit,
            },
        )

    def dependency(self, dependency_id: str, *, sample_limit: int = 20) -> dict[str, Any]:
        return self._get(
            f"/v1/agent/dependencies/{dependency_id}",
            {"sample_limit": sample_limit},
        )

    def llm_usage(
        self,
        *,
        app_id: str | None = None,
        group_by: str = "model",
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/llm-usage",
            {"app_id": app_id, "group_by": group_by},
        )

    def metrics(
        self,
        *,
        app_id: str | None = None,
        window_minutes: int = 1440,
        bucket_minutes: int = 15,
    ) -> list[dict[str, Any]]:
        return self._get(
            "/v1/agent/metrics/timeseries",
            {
                "app_id": app_id,
                "window_minutes": window_minutes,
                "bucket_minutes": bucket_minutes,
            },
        )
