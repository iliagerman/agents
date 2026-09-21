#!/usr/bin/env python3
"""
Gmail CLI for the `gmail` skill. Headless auth via GOOGLE_CREDENTIALS_JSON
(see google_client.py). All output is JSON on stdout.

Subcommands:
    profile                      Show the authenticated account (auth smoke test)
    search   --query Q [--max N] List messages matching a Gmail search query
    read     --id ID             Read one message (headers + plain-text body)
    thread   --id ID             Read every message in a thread
    send     --to .. --subject ..--body ..   Send an email (write)
    draft    --to .. --subject ..--body ..   Create a draft (write)
    reply    --id ID --body ..   Reply in-thread to a message (write)
    labels                       List all labels
    modify   --id ID [--add ..] [--remove ..]   Add/remove labels (write)
    trash    --id ID             Move a message to Trash (write)
    untrash  --id ID             Restore a message from Trash (write)

Gmail search examples for --query: 'is:unread', 'from:alice@x.com newer_than:7d',
'subject:invoice has:attachment', 'in:inbox -category:promotions'.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from email.message import EmailMessage

from google_client import GMAIL_SCOPES, get_service

USER = "me"


def _svc():
    return get_service("gmail", "v1", GMAIL_SCOPES)


def _emit(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


# --------------------------------------------------------------------------- #
# message parsing
# --------------------------------------------------------------------------- #
def _headers_map(payload) -> dict:
    return {h["name"].lower(): h["value"] for h in payload.get("headers", [])}


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")


def _extract_body(payload, prefer: str) -> str:
    """Depth-first search for the preferred MIME type; fall back to any text."""
    want = f"text/{prefer}"
    stack = [payload]
    fallback = ""
    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and mime == want:
            return _decode(data)
        if data and mime.startswith("text/") and not fallback:
            fallback = _decode(data)
        stack.extend(part.get("parts", []) or [])
    return fallback


def _summarize(msg, prefer="plain", include_body=True) -> dict:
    payload = msg.get("payload", {})
    h = _headers_map(payload)
    out = {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "labelIds": msg.get("labelIds", []),
        "snippet": msg.get("snippet"),
        "from": h.get("from"),
        "to": h.get("to"),
        "cc": h.get("cc"),
        "subject": h.get("subject"),
        "date": h.get("date"),
    }
    if include_body:
        out["body"] = _extract_body(payload, prefer)
    return out


# --------------------------------------------------------------------------- #
# message building
# --------------------------------------------------------------------------- #
def _build_mime(args) -> EmailMessage:
    mime = EmailMessage()
    mime["To"] = args.to
    mime["Subject"] = args.subject or ""
    if args.cc:
        mime["Cc"] = args.cc
    if args.bcc:
        mime["Bcc"] = args.bcc
    if getattr(args, "sender", None):
        mime["From"] = args.sender
    if getattr(args, "html", False):
        mime.set_content("This message requires an HTML-capable client.")
        mime.add_alternative(args.body or "", subtype="html")
    else:
        mime.set_content(args.body or "")
    for path in getattr(args, "attach", None) or []:
        with open(path, "rb") as fh:
            data = fh.read()
        name = path.rsplit("/", 1)[-1]
        mime.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    return mime


def _raw(mime: EmailMessage) -> str:
    return base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_profile(_args) -> None:
    _emit(_svc().users().getProfile(userId=USER).execute())


def cmd_search(args) -> None:
    svc = _svc()
    resp = svc.users().messages().list(userId=USER, q=args.query, maxResults=args.max).execute()
    ids = [m["id"] for m in resp.get("messages", [])]
    results = []
    for mid in ids:
        msg = svc.users().messages().get(
            userId=USER, id=mid, format="metadata",
            metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
        ).execute()
        results.append(_summarize(msg, include_body=False))
    _emit({"query": args.query, "count": len(results), "messages": results})


def cmd_read(args) -> None:
    msg = _svc().users().messages().get(userId=USER, id=args.id, format="full").execute()
    _emit(_summarize(msg, prefer="html" if args.html else "plain"))


def cmd_thread(args) -> None:
    thread = _svc().users().threads().get(userId=USER, id=args.id, format="full").execute()
    msgs = [_summarize(m, prefer="html" if args.html else "plain") for m in thread.get("messages", [])]
    _emit({"id": thread.get("id"), "count": len(msgs), "messages": msgs})


def cmd_send(args) -> None:
    body = {"raw": _raw(_build_mime(args))}
    _emit(_svc().users().messages().send(userId=USER, body=body).execute())


def cmd_draft(args) -> None:
    body = {"message": {"raw": _raw(_build_mime(args))}}
    _emit(_svc().users().drafts().create(userId=USER, body=body).execute())


def cmd_reply(args) -> None:
    svc = _svc()
    orig = svc.users().messages().get(
        userId=USER, id=args.id, format="metadata",
        metadataHeaders=["From", "To", "Cc", "Subject", "Message-ID", "References"],
    ).execute()
    h = _headers_map(orig.get("payload", {}))
    mime = EmailMessage()
    mime["To"] = args.to or h.get("from", "")
    if args.cc:
        mime["Cc"] = args.cc
    subject = h.get("subject", "")
    mime["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    msg_id = h.get("message-id")
    if msg_id:
        mime["In-Reply-To"] = msg_id
        mime["References"] = f"{h.get('references', '')} {msg_id}".strip()
    if getattr(args, "html", False):
        mime.add_alternative(args.body or "", subtype="html")
    else:
        mime.set_content(args.body or "")
    body = {"raw": _raw(mime), "threadId": orig.get("threadId")}
    _emit(svc.users().messages().send(userId=USER, body=body).execute())


def cmd_labels(_args) -> None:
    _emit(_svc().users().labels().list(userId=USER).execute().get("labels", []))


def cmd_modify(args) -> None:
    body = {"addLabelIds": args.add or [], "removeLabelIds": args.remove or []}
    _emit(_svc().users().messages().modify(userId=USER, id=args.id, body=body).execute())


def cmd_trash(args) -> None:
    _emit(_svc().users().messages().trash(userId=USER, id=args.id).execute())


def cmd_untrash(args) -> None:
    _emit(_svc().users().messages().untrash(userId=USER, id=args.id).execute())


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gmail CLI (headless auth via GOOGLE_CREDENTIALS_JSON).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("profile").set_defaults(func=cmd_profile)

    s = sub.add_parser("search")
    s.add_argument("--query", required=True, help="Gmail search query, e.g. 'is:unread from:x@y.com'")
    s.add_argument("--max", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("read")
    s.add_argument("--id", required=True)
    s.add_argument("--html", action="store_true", help="Prefer the HTML body")
    s.set_defaults(func=cmd_read)

    s = sub.add_parser("thread")
    s.add_argument("--id", required=True)
    s.add_argument("--html", action="store_true")
    s.set_defaults(func=cmd_thread)

    for name, fn in (("send", cmd_send), ("draft", cmd_draft)):
        s = sub.add_parser(name)
        s.add_argument("--to", required=True, help="Comma-separated recipients")
        s.add_argument("--subject", required=True)
        s.add_argument("--body", required=True)
        s.add_argument("--cc")
        s.add_argument("--bcc")
        s.add_argument("--from", dest="sender", help="Send-as alias")
        s.add_argument("--html", action="store_true", help="Treat --body as HTML")
        s.add_argument("--attach", action="append", help="File to attach (repeatable)")
        s.set_defaults(func=fn)

    s = sub.add_parser("reply")
    s.add_argument("--id", required=True, help="Message ID to reply to")
    s.add_argument("--body", required=True)
    s.add_argument("--to", help="Override recipient (default: original sender)")
    s.add_argument("--cc")
    s.add_argument("--html", action="store_true")
    s.set_defaults(func=cmd_reply)

    sub.add_parser("labels").set_defaults(func=cmd_labels)

    s = sub.add_parser("modify")
    s.add_argument("--id", required=True)
    s.add_argument("--add", action="append", help="Label ID to add (repeatable). Use UNREAD/INBOX/STARRED etc.")
    s.add_argument("--remove", action="append", help="Label ID to remove (repeatable)")
    s.set_defaults(func=cmd_modify)

    s = sub.add_parser("trash")
    s.add_argument("--id", required=True)
    s.set_defaults(func=cmd_trash)

    s = sub.add_parser("untrash")
    s.add_argument("--id", required=True)
    s.set_defaults(func=cmd_untrash)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
