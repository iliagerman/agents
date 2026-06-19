#!/usr/bin/env python3
"""
Google Calendar CLI for the `calendar` skill. Headless auth via
GOOGLE_CREDENTIALS_JSON (see google_client.py). All output is JSON on stdout.

Subcommands:
    calendars                         List calendars on the user's list
    agenda  [--days N | --time-min .. --time-max ..]   List upcoming events
    get      --id ID                  Get one event
    create   --summary .. --start .. --end ..          Create an event (write)
    quickadd --text ".."              Create an event from natural language (write)
    update   --id ID [fields]         Patch an event (write)
    delete   --id ID                  Delete an event (write)
    respond  --id ID --response accepted|declined|tentative   RSVP (write)
    freebusy --time-min .. --time-max .. [--calendar ..]      Free/busy query

Times: pass RFC3339 for timed events (2026-06-20T09:00:00-07:00) or a bare date
(2026-06-20) for all-day events. --calendar defaults to 'primary'.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from google_client import CALENDAR_SCOPES, get_service


def _svc():
    return get_service("calendar", "v3", CALENDAR_SCOPES)


def _emit(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")


def _now_rfc3339() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _time_field(value: str) -> dict:
    """Bare date -> all-day ('date'); otherwise a timed event ('dateTime')."""
    if len(value) == 10 and value.count("-") == 2:
        return {"date": value}
    return {"dateTime": value}


def _slim_event(ev) -> dict:
    return {
        "id": ev.get("id"),
        "status": ev.get("status"),
        "summary": ev.get("summary"),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "location": ev.get("location"),
        "attendees": [a.get("email") for a in ev.get("attendees", [])],
        "hangoutLink": ev.get("hangoutLink"),
        "htmlLink": ev.get("htmlLink"),
        "organizer": (ev.get("organizer") or {}).get("email"),
    }


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_calendars(_args) -> None:
    items = _svc().calendarList().list().execute().get("items", [])
    _emit([{"id": c["id"], "summary": c.get("summary"), "primary": c.get("primary", False),
            "accessRole": c.get("accessRole")} for c in items])


def cmd_agenda(args) -> None:
    time_min = args.time_min or _now_rfc3339()
    if args.time_max:
        time_max = args.time_max
    else:
        end = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=args.days)
        time_max = end.replace(microsecond=0).isoformat()
    resp = _svc().events().list(
        calendarId=args.calendar, timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime", maxResults=args.max, q=args.query,
    ).execute()
    items = [_slim_event(e) for e in resp.get("items", [])]
    _emit({"calendar": args.calendar, "timeMin": time_min, "timeMax": time_max,
           "count": len(items), "events": items})


def cmd_get(args) -> None:
    _emit(_svc().events().get(calendarId=args.calendar, eventId=args.id).execute())


def _event_body(args) -> dict:
    body: dict = {}
    if args.summary is not None:
        body["summary"] = args.summary
    if args.description is not None:
        body["description"] = args.description
    if args.location is not None:
        body["location"] = args.location
    if args.start:
        body["start"] = _time_field(args.start)
        if args.timezone and "dateTime" in body["start"]:
            body["start"]["timeZone"] = args.timezone
    if args.end:
        body["end"] = _time_field(args.end)
        if args.timezone and "dateTime" in body["end"]:
            body["end"]["timeZone"] = args.timezone
    if args.attendee:
        body["attendees"] = [{"email": e} for e in args.attendee]
    return body


def cmd_create(args) -> None:
    body = _event_body(args)
    kwargs = {"calendarId": args.calendar, "body": body, "sendUpdates": args.send_updates}
    if args.meet:
        body["conferenceData"] = {"createRequest": {"requestId": f"meet-{args.summary}"[:64]}}
        kwargs["conferenceDataVersion"] = 1
    _emit(_slim_event(_svc().events().insert(**kwargs).execute()))


def cmd_quickadd(args) -> None:
    ev = _svc().events().quickAdd(calendarId=args.calendar, text=args.text).execute()
    _emit(_slim_event(ev))


def cmd_update(args) -> None:
    body = _event_body(args)
    if not body:
        sys.exit("update: provide at least one field to change (--summary/--start/...).")
    ev = _svc().events().patch(
        calendarId=args.calendar, eventId=args.id, body=body, sendUpdates=args.send_updates,
    ).execute()
    _emit(_slim_event(ev))


def cmd_delete(args) -> None:
    _svc().events().delete(calendarId=args.calendar, eventId=args.id, sendUpdates=args.send_updates).execute()
    _emit({"deleted": args.id, "calendar": args.calendar})


def cmd_respond(args) -> None:
    svc = _svc()
    ev = svc.events().get(calendarId=args.calendar, eventId=args.id).execute()
    me = ev.get("organizer", {}).get("email")
    attendees = ev.get("attendees", [])
    # Mark the self attendee (or the only attendee) with the response status.
    target = next((a for a in attendees if a.get("self")), None)
    if target is None and me:
        target = next((a for a in attendees if a.get("email") == me), None)
    if target is None:
        sys.exit("respond: could not find your attendee entry on this event.")
    target["responseStatus"] = args.response
    ev = svc.events().patch(
        calendarId=args.calendar, eventId=args.id,
        body={"attendees": attendees}, sendUpdates="all",
    ).execute()
    _emit(_slim_event(ev))


def cmd_freebusy(args) -> None:
    body = {"timeMin": args.time_min, "timeMax": args.time_max,
            "items": [{"id": c} for c in (args.calendar_list or ["primary"])]}
    _emit(_svc().freebusy().query(body=body).execute())


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def _add_event_fields(s, require_core: bool) -> None:
    s.add_argument("--summary", required=require_core)
    s.add_argument("--start", required=require_core, help="RFC3339 datetime or bare YYYY-MM-DD (all-day)")
    s.add_argument("--end", required=require_core, help="RFC3339 datetime or bare YYYY-MM-DD (all-day)")
    s.add_argument("--description")
    s.add_argument("--location")
    s.add_argument("--attendee", action="append", help="Attendee email (repeatable)")
    s.add_argument("--timezone", help="IANA tz for timed events, e.g. America/New_York")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Google Calendar CLI (headless auth via GOOGLE_CREDENTIALS_JSON).")
    p.add_argument("--calendar", default="primary", help="Calendar ID (default: primary)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("calendars").set_defaults(func=cmd_calendars)

    s = sub.add_parser("agenda")
    s.add_argument("--days", type=int, default=7, help="Days ahead from now (ignored if --time-max given)")
    s.add_argument("--time-min", dest="time_min", help="RFC3339 lower bound (default: now)")
    s.add_argument("--time-max", dest="time_max", help="RFC3339 upper bound")
    s.add_argument("--query", help="Free-text event search")
    s.add_argument("--max", type=int, default=50)
    s.set_defaults(func=cmd_agenda)

    s = sub.add_parser("get")
    s.add_argument("--id", required=True)
    s.set_defaults(func=cmd_get)

    s = sub.add_parser("create")
    _add_event_fields(s, require_core=True)
    s.add_argument("--meet", action="store_true", help="Attach a Google Meet link")
    s.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    s.set_defaults(func=cmd_create)

    s = sub.add_parser("quickadd")
    s.add_argument("--text", required=True, help="e.g. 'Lunch with Sam tomorrow 12pm'")
    s.set_defaults(func=cmd_quickadd)

    s = sub.add_parser("update")
    s.add_argument("--id", required=True)
    _add_event_fields(s, require_core=False)
    s.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("delete")
    s.add_argument("--id", required=True)
    s.add_argument("--send-updates", default="none", choices=["all", "externalOnly", "none"])
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("respond")
    s.add_argument("--id", required=True)
    s.add_argument("--response", required=True, choices=["accepted", "declined", "tentative"])
    s.set_defaults(func=cmd_respond)

    s = sub.add_parser("freebusy")
    s.add_argument("--time-min", dest="time_min", required=True)
    s.add_argument("--time-max", dest="time_max", required=True)
    s.add_argument("--calendar-list", dest="calendar_list", action="append",
                   help="Calendar ID to include (repeatable; default: primary)")
    s.set_defaults(func=cmd_freebusy)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
