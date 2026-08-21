#!/usr/bin/env python3
"""Generate an image with Atlas Cloud and save it atomically."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


API_BASE = "https://api.atlascloud.ai/api/v1"
DEFAULT_MODEL = "google/nano-banana-pro/text-to-image"
SUCCESS_STATUSES = {"completed", "succeeded"}
FAILURE_STATUSES = {"failed", "canceled", "cancelled", "timeout"}


class AtlasError(RuntimeError):
    """Raised when Atlas Cloud cannot produce a usable image."""


def _request_json(
    url: str,
    *,
    method: str = "GET",
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Request JSON. GET retries are bounded; POST is always attempted once."""
    attempts = 3 if method == "GET" else 1
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "web-art/atlas"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if body is not None:
        headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.load(response)
            if not isinstance(result, dict):
                raise AtlasError("Atlas Cloud returned non-object JSON")
            code = result.get("code")
            if isinstance(code, int) and code not in {0, 200}:
                detail = result.get("message") or result.get("msg") or "request failed"
                raise AtlasError(f"Atlas Cloud returned code {code}: {detail}")
            return result
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = AtlasError(f"Atlas Cloud returned HTTP {exc.code}: {detail}")
            retryable = exc.code == 429 or exc.code >= 500
            if method != "GET" or not retryable:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = AtlasError(f"Atlas Cloud request failed: {exc.reason}")

        if attempt < attempts - 1:
            sleep(2**attempt)

    assert last_error is not None
    raise last_error


def _unwrap(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _model_schema(
    model_id: str,
    *,
    request_json: Callable[..., dict[str, Any]] = _request_json,
) -> dict[str, Any]:
    catalog = request_json(f"{API_BASE}/models")
    models = catalog.get("data")
    if not isinstance(models, list):
        raise AtlasError("Atlas Cloud model catalog did not return a data array")

    model = next(
        (
            item
            for item in models
            if item.get("model") == model_id and item.get("display_console") is not False
        ),
        None,
    )
    if not model:
        raise AtlasError(f"Model is unavailable in the live Atlas Cloud catalog: {model_id}")
    if str(model.get("type", "")).lower() != "image":
        raise AtlasError(f"Model is not an image model: {model_id}")

    schema_url = model.get("schema")
    if not isinstance(schema_url, str) or not schema_url.startswith("https://"):
        raise AtlasError(f"Model has no HTTPS schema URL: {model_id}")
    schema_document = request_json(schema_url)
    try:
        schema = schema_document["components"]["schemas"]["Input"]
    except (KeyError, TypeError) as exc:
        raise AtlasError(f"Model schema has no Input object: {model_id}") from exc
    if not isinstance(schema.get("properties"), dict):
        raise AtlasError(f"Model schema has no input properties: {model_id}")
    return schema


def _validate_payload(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    properties = schema["properties"]
    unknown = sorted(set(payload) - set(properties))
    if unknown:
        raise AtlasError(f"Parameters absent from the live model schema: {', '.join(unknown)}")
    for name in schema.get("required", []):
        if payload.get(name) in (None, ""):
            raise AtlasError(f"Missing required parameter: {name}")
    for name, value in payload.items():
        allowed = properties[name].get("enum")
        if allowed and value not in allowed:
            raise AtlasError(f"Invalid {name}: {value}; expected one of {', '.join(allowed)}")


def _poll(
    prediction_id: str,
    api_key: str,
    *,
    attempts: int,
    interval: float,
    request_json: Callable[..., dict[str, Any]] = _request_json,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    url = f"{API_BASE}/model/prediction/{urllib.parse.quote(prediction_id, safe='')}"
    for attempt in range(attempts):
        prediction = _unwrap(request_json(url, api_key=api_key))
        status = str(prediction.get("status", "")).lower()
        outputs = prediction.get("outputs")
        if status in SUCCESS_STATUSES and isinstance(outputs, list) and outputs:
            return prediction
        if status in FAILURE_STATUSES:
            detail = prediction.get("error") or prediction.get("message") or status
            raise AtlasError(f"Atlas Cloud prediction {status}: {detail}")
        if attempt < attempts - 1:
            sleep(interval)
    raise AtlasError(f"Atlas Cloud prediction did not complete after {attempts} polls")


def _download(url: str, destination: Path, *, timeout: float = 120) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise AtlasError("Atlas Cloud output must be a credential-free HTTPS URL")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "web-art/atlas"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
            ) as temp:
                temp_path = Path(temp.name)
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
                temp.flush()
                os.fsync(temp.fileno())
        if temp_path.stat().st_size == 0:
            raise AtlasError("Atlas Cloud returned an empty image")
        os.replace(temp_path, destination)
        temp_path = None
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise AtlasError(f"Could not download the generated image: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def generate(
    prompt: str,
    destination: Path,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    aspect_ratio: str = "1:1",
    resolution: str = "1k",
    output_format: str = "png",
    poll_attempts: int = 120,
    poll_interval: float = 2,
    request_json: Callable[..., dict[str, Any]] = _request_json,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Validate live schema, submit once, poll, then save the first output."""
    schema = _model_schema(model, request_json=request_json)
    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "output_format": output_format,
        "enable_sync_mode": False,
        "enable_base64_output": False,
    }
    _validate_payload(payload, schema)

    submitted = _unwrap(
        request_json(
            f"{API_BASE}/model/generateImage",
            method="POST",
            api_key=api_key,
            payload=payload,
        )
    )
    outputs = submitted.get("outputs")
    if str(submitted.get("status", "")).lower() in SUCCESS_STATUSES and isinstance(outputs, list) and outputs:
        result = submitted
    else:
        prediction_id = submitted.get("id")
        if not isinstance(prediction_id, str) or not prediction_id:
            raise AtlasError("Atlas Cloud response did not include a prediction id")
        result = _poll(
            prediction_id,
            api_key,
            attempts=poll_attempts,
            interval=poll_interval,
            request_json=request_json,
            sleep=sleep,
        )

    output_url = result["outputs"][0]
    if not isinstance(output_url, str):
        raise AtlasError("Atlas Cloud returned an invalid image URL")
    _download(output_url, destination)
    return destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate web art with Atlas Cloud")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--filename", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--aspect-ratio", default="1:1")
    parser.add_argument("--resolution", default="1K", choices=("1K", "2K", "4K"))
    parser.add_argument("--output-format", default="png", choices=("png", "jpeg"))
    parser.add_argument("--poll-attempts", type=int, default=120, help=argparse.SUPPRESS)
    parser.add_argument("--poll-interval", type=float, default=2, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    api_key = os.environ.get("ATLASCLOUD_API_KEY") or os.environ.get("ATLAS_CLOUD_API_KEY")
    if not api_key:
        print("Set ATLASCLOUD_API_KEY before using the Atlas provider.", file=sys.stderr)
        return 2
    try:
        output = generate(
            args.prompt,
            args.filename.expanduser().resolve(),
            api_key=api_key,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution.lower(),
            output_format=args.output_format,
            poll_attempts=args.poll_attempts,
            poll_interval=args.poll_interval,
        )
    except (AtlasError, OSError) as exc:
        print(f"web-art: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
