---
name: calendar
description: "List, search, create, update, delete, and RSVP to Google Calendar events, and check free/busy, from the command line. Use when the user wants to see their schedule, find time, book or change a meeting, add an event, cancel an event, accept/decline an invite, or check availability ('what's on my calendar', 'am I free Thursday', 'schedule a meeting with X', 'move my 3pm', 'cancel that event', 'block focus time', 'when is everyone free'). Headless: authenticates from a pre-supplied credential in the GOOGLE_CREDENTIALS_JSON env var with no interactive login. Triggers on: calendar, schedule, event, meeting, agenda, availability, free/busy, invite, RSVP, book time."
version: 1.0.0
requires:
  bins:
    - python3
  env:
    - name: GOOGLE_CREDENTIALS_JSON
      required: true
      prompt: "Inline authorized-user credentials JSON (with a refresh token) produced once by scripts/authorize.py. See the Authentication section of SKILL.md."
---

# calendar

Headless Google Calendar access via the official Google API client. Every
command is `python3 scripts/gcal.py [--calendar ID] <subcommand> [flags]` and
prints JSON to stdout.

Authentication is non-interactive: the skill reads a ready-to-use credential
from `GOOGLE_CREDENTIALS_JSON` and refreshes access tokens itself. The agent
never logs in. If that env var is missing or holds the wrong kind of JSON, the
scripts exit with an explanation — see **Authentication** below.

> The CLI script is `gcal.py` (NOT `calendar.py` — that name would shadow
> Python's stdlib `calendar` module and break imports).
>
> Shares its auth layer (`scripts/google_client.py`, `scripts/authorize.py`)
> and the single `GOOGLE_CREDENTIALS_JSON` credential with the **gmail** skill.
> Authorize once and both skills work.

## Setup

```bash
pip install -r requirements.txt   # google-api-python-client, google-auth, ...
```

## Commands

`--calendar <ID>` is a **global** flag (before the subcommand) and defaults to
`primary`. Run from this skill's directory so `gcal.py` finds `google_client.py`.

| Command | Purpose |
|---------|---------|
| `python3 scripts/gcal.py calendars` | List calendars on the user's list (with IDs + access role). |
| `python3 scripts/gcal.py agenda [--days 7] [--query Q]` | Upcoming events from now (expands recurring, ordered by start). |
| `python3 scripts/gcal.py agenda --time-min <RFC3339> --time-max <RFC3339>` | Events in an explicit window. |
| `python3 scripts/gcal.py get --id <ID>` | Full details of one event. |
| `python3 scripts/gcal.py create --summary S --start T --end T [...]` | **Create** an event. |
| `python3 scripts/gcal.py quickadd --text "Lunch with Sam tomorrow 12pm"` | Create from natural language. |
| `python3 scripts/gcal.py update --id <ID> [fields]` | Patch any field(s) of an event. |
| `python3 scripts/gcal.py delete --id <ID>` | Delete an event. |
| `python3 scripts/gcal.py respond --id <ID> --response accepted\|declined\|tentative` | RSVP to an invite. |
| `python3 scripts/gcal.py freebusy --time-min <RFC3339> --time-max <RFC3339> [--calendar-list ID ...]` | Busy intervals across calendars. |

### Time formats

- **Timed event:** RFC3339 with offset — `2026-06-20T09:00:00-07:00`. Add
  `--timezone America/New_York` to attach an IANA zone.
- **All-day event:** a bare date — `2026-06-20`.

### `create` / `update` flags

`--summary`, `--start`, `--end`, `--description`, `--location`,
`--attendee <email>` (repeatable), `--timezone`, `--meet` (attach a Google Meet
link, create only), `--send-updates all|externalOnly|none` (whether attendees
are emailed; default `none`).

### Examples

```bash
# Am I free this week? (agenda) + raw busy blocks (freebusy)
python3 scripts/gcal.py agenda --days 7
python3 scripts/gcal.py freebusy --time-min 2026-06-22T00:00:00-07:00 --time-max 2026-06-27T00:00:00-07:00

# Book a 30-min meeting with a Meet link and email the attendee
python3 scripts/gcal.py create --summary "Sync" \
  --start 2026-06-23T15:00:00-07:00 --end 2026-06-23T15:30:00-07:00 \
  --attendee alice@example.com --meet --send-updates all

# Move an event (patch start/end)
python3 scripts/gcal.py update --id <ID> --start 2026-06-23T16:00:00-07:00 --end 2026-06-23T16:30:00-07:00 --send-updates all

# Decline an invite
python3 scripts/gcal.py respond --id <ID> --response declined

# Block all-day focus time on a secondary calendar
python3 scripts/gcal.py --calendar work@group.calendar.google.com create --summary "Focus" --start 2026-06-24 --end 2026-06-25
```

## Safety

`create`, `quickadd`, `update`, `delete`, `respond` **write** to the calendar
and, with `--send-updates all`, **email attendees**. Confirm details with the
user before creating, changing, or deleting events that notify others.

## Authentication

The scope (`calendar`) is granted **once** by you and stored as an
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
