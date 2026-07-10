#!/usr/bin/env python3
"""Save refreshed Google authorized_user credentials into this platform user profile.

Reads the credential JSON from --credential-json, --credential-file, or stdin and
stores it as GOOGLE_CREDENTIALS_JSON for the gmail and calendar skills by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _base_url() -> str:
    configured = (
        os.environ.get("APP_BASE_URL")
        or os.environ.get("BACKEND_API_BASE_URL")
        or os.environ.get("TRIGGER_CHECKER_API_BASE_URL")
    )
    if configured:
        return configured.rstrip("/")
    return f"http://127.0.0.1:{os.environ.get('PORT', '9020')}"


def _headers() -> dict[str, str]:
    api_key = os.environ.get("AGENT_API_KEY", "").strip()
    user_id = os.environ.get("USER_ID", "").strip()
    tenant_id = os.environ.get("TENANT_ID", "").strip()
    if not api_key:
        raise SystemExit("AGENT_API_KEY is not configured")
    if not user_id:
        raise SystemExit("USER_ID is not configured")
    headers = {
        "Content-Type": "application/json",
        "X-Agent-API-Key": api_key,
        "X-Agent-Execution-User-Id": user_id,
    }
    if tenant_id and tenant_id.lower() != "none":
        headers["X-Agent-Execution-Tenant-Id"] = tenant_id
    return headers


def _read_credential(args: argparse.Namespace) -> str:
    if args.credential_json:
        raw = args.credential_json
    elif args.credential_file:
        with open(args.credential_file, "r", encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()
    credential = json.loads(raw)
    if credential.get("type") != "authorized_user" or not credential.get("refresh_token"):
        raise SystemExit("Expected authorized_user JSON with a refresh_token")
    return json.dumps(credential, separators=(",", ":"))


def _request_json(method: str, path: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{_base_url()}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {details}") from exc


def _save(slug: str, credential_json: str) -> Any:
    quoted_slug = urllib.parse.quote(slug, safe="")
    return _request_json(
        "PUT",
        f"/api/v1/user-skills/skill-slug/{quoted_slug}/credentials",
        {"GOOGLE_CREDENTIALS_JSON": credential_json},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist refreshed Google skill credentials")
    parser.add_argument("--credential-json", help="authorized_user JSON string")
    parser.add_argument("--credential-file", help="file containing authorized_user JSON")
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        default=[],
        help="skill slug to update; repeatable. Defaults to gmail and calendar",
    )
    args = parser.parse_args()

    credential_json = _read_credential(args)
    skills = args.skills or ["gmail", "calendar"]
    saved = [_save(slug, credential_json) for slug in skills]
    print(json.dumps({"savedSkills": [item["skillId"] for item in saved]}, indent=2))


if __name__ == "__main__":
    main()
