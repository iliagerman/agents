---
name: gmail
description: "Read, search, send, reply to, draft, and label Gmail messages from the command line. Use when the user wants to check, find, summarize, send, reply to, forward, draft, label, archive, or triage email ('check my inbox', 'any new emails from X', 'reply to that', 'send an email to…', 'draft a message', 'mark as read', 'archive these'). Headless: authenticates from a pre-supplied credential in the GOOGLE_CREDENTIALS_JSON env var with no interactive login. Triggers on: gmail, email, inbox, unread, send mail, reply, draft, forward, label, archive."
version: 1.0.0
requires:
  bins:
    - python3
  env:
    - name: GOOGLE_CREDENTIALS_JSON
      required: true
      prompt: "Inline authorized-user credentials JSON (with a refresh token) produced once by scripts/authorize.py. See the Authentication section of SKILL.md."
---

# gmail

Headless Gmail access via the official Google API client. Every command is
`python3 scripts/gmail.py <subcommand> [flags]` and prints JSON to stdout.

Authentication is non-interactive: the skill reads a ready-to-use credential
from `GOOGLE_CREDENTIALS_JSON` and refreshes access tokens itself. The agent
never logs in. If that env var is missing or holds the wrong kind of JSON, the
scripts exit with an explanation — see **Authentication** below.

> Shares its auth layer (`scripts/google_client.py`, `scripts/authorize.py`)
> and the single `GOOGLE_CREDENTIALS_JSON` credential with the **calendar**
> skill. Authorize once and both skills work.

## Setup

```bash
pip install -r requirements.txt   # google-api-python-client, google-auth, ...
```

## Commands

Run from this skill's directory (so `gmail.py` finds `google_client.py`):

| Command | Purpose |
|---------|---------|
| `python3 scripts/gmail.py profile` | Show the signed-in address — use as an auth smoke test. |
| `python3 scripts/gmail.py search --query "is:unread" [--max 20]` | List messages matching a [Gmail search query](https://support.google.com/mail/answer/7190) (metadata only, no body). |
| `python3 scripts/gmail.py read --id <ID> [--html]` | Read one message: headers + decoded plain-text (or HTML) body. |
| `python3 scripts/gmail.py thread --id <ID> [--html]` | Read every message in a thread. |
| `python3 scripts/gmail.py send --to a@b.com --subject S --body B [...]` | **Send** an email. |
| `python3 scripts/gmail.py draft --to a@b.com --subject S --body B [...]` | Save a draft instead of sending. |
| `python3 scripts/gmail.py reply --id <ID> --body B [--to ..] [--cc ..]` | Reply in-thread (sets `In-Reply-To`/`References`, `Re:` subject, threadId). |
| `python3 scripts/gmail.py labels` | List labels and their IDs. |
| `python3 scripts/gmail.py modify --id <ID> [--add L] [--remove L]` | Add/remove labels. Mark read: `--remove UNREAD`. Archive: `--remove INBOX`. Star: `--add STARRED`. |
| `python3 scripts/gmail.py trash --id <ID>` / `untrash --id <ID>` | Move to / restore from Trash. |

`send`/`draft` extra flags: `--cc`, `--bcc`, `--from <alias>`, `--html` (treat
`--body` as HTML), `--attach <file>` (repeatable). To **forward**, `read` the
original then `send` a new message with the quoted body to the new recipients.

### Examples

```bash
# Triage: what's unread from the last 3 days?
python3 scripts/gmail.py search --query "is:unread newer_than:3d" --max 30

# Read a specific message
python3 scripts/gmail.py read --id 18f1a2b3c4d

# Reply
python3 scripts/gmail.py reply --id 18f1a2b3c4d --body "Sounds good — Thursday works."

# Send with an attachment
python3 scripts/gmail.py send --to alice@example.com --subject "Report" \
  --body "See attached." --attach ./report.pdf

# Archive and mark read
python3 scripts/gmail.py modify --id 18f1a2b3c4d --remove INBOX --remove UNREAD
```

## Safety

`send`, `reply`, `draft`, `modify`, `trash`, `untrash` **write** to the mailbox.
Confirm recipients/content with the user before running a `send` or `reply`.
The granted scope (`gmail.modify`) cannot permanently delete mail — `trash` only
moves to Trash.

## Authentication

The scopes (`gmail.modify`) are granted **once** by you and stored as an
authorized-user credential in `GOOGLE_CREDENTIALS_JSON`. Full step-by-step setup
(Google Cloud project, OAuth client, running `authorize.py`, and putting the
result in the env var) is in **[references/AUTH.md](references/AUTH.md)** — it is
identical for the gmail and calendar skills, and one consent covers both.

Quick version, run on a machine with a browser:

```bash
python3 scripts/authorize.py --client client.json   # prints authorized_user JSON
```

Then on the home server set `GOOGLE_CREDENTIALS_JSON` to that JSON. The scripts
also accept a service-account key (set `GOOGLE_DELEGATED_SUBJECT` for Workspace
domain-wide delegation).
