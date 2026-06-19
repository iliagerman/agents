#!/usr/bin/env python3
"""
ONE-TIME bootstrap — YOU run this, not the agent.

Run it on a machine with a browser (e.g. your laptop). It performs the Google
OAuth consent for BOTH the gmail and calendar skills and prints an
"authorized_user" credentials JSON that contains a refresh token. Copy that JSON
into the GOOGLE_CREDENTIALS_JSON env var on your home server — the skills then
run fully headless, refreshing access tokens on their own.

Prerequisite: an OAuth *client* secrets JSON of type "Desktop app", downloaded
from Google Cloud Console (APIs & Services -> Credentials). Pass it with
--client <path>, --client-json '<json>', or pipe it via --client -.

Examples:
    python3 authorize.py --client client.json
    python3 authorize.py --client client.json --no-browser   # print URL to open
    cat client.json | python3 authorize.py --client -
    python3 authorize.py --client-json "$(cat client.json)"

The printed JSON is a secret (it grants access to your mailbox and calendar).
Treat it like a password.
"""
import argparse
import json
import os
import sys

from google_client import ALL_SCOPES


def _read_client(args) -> str:
    if args.client_json:
        return args.client_json
    if args.client == "-":
        return sys.stdin.read()
    with open(args.client, "r", encoding="utf-8") as fh:
        return fh.read()


# Loopback redirect used by the manual flow. The browser will try to load this
# (and fail harmlessly if nothing is listening) — the code is in its URL bar.
MANUAL_REDIRECT = "http://localhost:8765/"
STATE_FILE = "/tmp/google-skills-authorize-state.json"


def _extract_code(response: str) -> str:
    """Accept a full redirect URL (…/?code=XYZ&…) or a bare code."""
    response = response.strip()
    if "code=" in response:
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(response).query)
        if qs.get("code"):
            return qs["code"][0]
    return response


def _run_manual_start(config) -> None:
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(config, scopes=ALL_SCOPES, redirect_uri=MANUAL_REDIRECT)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump({"config": config, "code_verifier": flow.code_verifier}, fh)
    print(auth_url)
    print(
        "\n# Open the URL above, approve, then re-run with:\n"
        f"#   authorize.py --manual-finish '<pasted redirect URL or code>'",
        file=sys.stderr,
    )


def _run_manual_finish(response: str) -> None:
    from google_auth_oauthlib.flow import Flow

    with open(STATE_FILE, "r", encoding="utf-8") as fh:
        state = json.load(fh)
    flow = Flow.from_client_config(state["config"], scopes=ALL_SCOPES, redirect_uri=MANUAL_REDIRECT)
    flow.code_verifier = state["code_verifier"]
    flow.fetch_token(code=_extract_code(response))
    os.unlink(STATE_FILE)  # contains a secret — remove once consumed
    _print_credential(flow.credentials)


def _print_credential(creds) -> None:
    # Credentials.to_json() omits "type"; add it so the output is the canonical
    # authorized_user shape (matches gcloud's application_default_credentials).
    data = json.loads(creds.to_json())
    data.setdefault("type", "authorized_user")
    print(json.dumps(data))
    print(
        "\n# ^ Set the JSON above as GOOGLE_CREDENTIALS_JSON on your home server.",
        file=sys.stderr,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate an authorized_user credential for the Google skills.")
    ap.add_argument("--client", help="Path to OAuth client secrets JSON, or '-' for stdin")
    ap.add_argument("--client-json", help="OAuth client secrets JSON passed inline as a string")
    ap.add_argument("--no-browser", action="store_true", help="Do not open a browser; print the URL to visit instead")
    ap.add_argument("--port", type=int, default=0, help="Local redirect server port (default: random free port)")
    ap.add_argument("--manual", action="store_true",
                    help="Manual paste flow (no local listener): print the auth URL, save state, then use --manual-finish. Use this when the browser is on a different machine than this one (e.g. SSH).")
    ap.add_argument("--manual-finish", metavar="RESPONSE",
                    help="Finish the manual flow: pass the pasted redirect URL (or bare code) from the browser.")
    args = ap.parse_args()

    # Phase 2 of the manual flow — needs only the saved state + the pasted code.
    if args.manual_finish:
        _run_manual_finish(args.manual_finish)
        return

    if not args.client and not args.client_json:
        ap.error("provide --client <path|-> or --client-json '<json>'")

    config = json.loads(_read_client(args))

    if args.manual:
        _run_manual_start(config)
        return

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(config, ALL_SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh_token is returned.
    creds = flow.run_local_server(
        port=args.port,
        open_browser=not args.no_browser,
        access_type="offline",
        prompt="consent",
    )

    _print_credential(creds)


if __name__ == "__main__":
    main()
