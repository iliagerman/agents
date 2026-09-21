#!/usr/bin/env python3
"""
Shared Google auth + service builder for the `gmail` and `calendar` skills.

Authentication is FULLY HEADLESS. There is no interactive auth at runtime — the
agent never logs in. Credentials are supplied INLINE via the
GOOGLE_CREDENTIALS_JSON env var (a raw JSON string, or a path to a JSON file).

Supported credential shapes (auto-detected by the JSON's "type" field):

  * authorized_user  -> produced once by authorize.py, after a human completes
                        the OAuth consent on a machine with a browser. Contains a
                        refresh_token, so access tokens are minted/refreshed at
                        runtime with zero user interaction. Use this for personal
                        Gmail / Calendar.
  * service_account  -> a service-account key. Headless, but only reaches a
                        user's Gmail/Calendar data through Google Workspace
                        domain-wide delegation. Set GOOGLE_DELEGATED_SUBJECT to
                        the email address to impersonate.

Raw OAuth *client* secrets (an "installed"/"web" key, no refresh token) cannot
authenticate headlessly -> a clear error tells you to run authorize.py first.

This file is intentionally identical in both skills so each stays self-contained.
"""
from __future__ import annotations

import json
import os
import sys

from google.auth.transport.requests import Request

ENV_VAR = "GOOGLE_CREDENTIALS_JSON"
SUBJECT_ENV = "GOOGLE_DELEGATED_SUBJECT"

# Scopes. A single consent over ALL_SCOPES authorizes both skills at once.
# gmail.modify = read + send + drafts + labels + trash (not permanent delete).
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
ALL_SCOPES = GMAIL_SCOPES + CALENDAR_SCOPES


def _raw_credentials() -> str:
    val = os.environ.get(ENV_VAR)
    if not val:
        sys.exit(
            f"{ENV_VAR} is not set.\n"
            f"Put the authorized-user credentials JSON produced by authorize.py "
            f"into this env var (inline JSON or a file path). See SKILL.md."
        )
    val = val.strip()
    if not val.startswith("{"):
        if os.path.isfile(val):
            with open(val, "r", encoding="utf-8") as fh:
                return fh.read()
        sys.exit(
            f"{ENV_VAR} is neither inline JSON (must start with '{{') nor a path "
            f"to an existing file: {val!r}"
        )
    return val


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"{ENV_VAR} does not contain valid JSON: {exc}")


def load_credentials(scopes):
    """Return refreshed google.auth credentials for the given scopes."""
    info = _parse(_raw_credentials())
    cred_type = info.get("type")

    is_authorized_user = cred_type == "authorized_user" or (
        cred_type is None and info.get("refresh_token") and info.get("client_id")
    )
    if is_authorized_user:
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_info(info, scopes)
    elif cred_type == "service_account":
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(
            info, scopes=scopes
        )
        subject = os.environ.get(SUBJECT_ENV)
        if subject:
            creds = creds.with_subject(subject)
    elif "installed" in info or "web" in info:
        sys.exit(
            f"{ENV_VAR} holds raw OAuth *client* secrets, which cannot "
            f"authenticate without a one-time consent.\n"
            f"Run authorize.py once on a machine with a browser, then put its "
            f"output JSON in {ENV_VAR}."
        )
    else:
        sys.exit(
            f"{ENV_VAR} JSON has an unrecognized shape (expected a 'type' of "
            f"'authorized_user' or 'service_account').\n"
            f"Run authorize.py to mint a valid authorized-user credential."
        )

    # Mint/refresh an access token now — headless, no user interaction.
    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - surface any refresh failure clearly
            sys.exit(
                f"Failed to obtain an access token: {exc}\n"
                f"For an authorized_user credential this usually means the "
                f"refresh token was revoked or expired — re-run authorize.py."
            )
    return creds


def get_service(api: str, version: str, scopes):
    """Build an authenticated Google API client (discovery cache disabled)."""
    from googleapiclient.discovery import build

    creds = load_credentials(scopes)
    return build(api, version, credentials=creds, cache_discovery=False)
